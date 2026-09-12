"""Read-only preflight evidence for conditional actions in the edit plan."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'work/edit_review'
W.mkdir(exist_ok=True)
plan=json.loads((ROOT/'work/edit_plan.json').read_text())
source=ROOT/plan[0]['plan']['source']

def frames():
    from PIL import Image,ImageDraw,ImageFont
    font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',19)
    sets={kind:[x for x in plan if x['action']==kind] for kind in ['cut','speed','sfx','zoom']}
    for kind,events in sets.items():
        for page in range(0,len(events),4):
            rows=events[page:page+4]
            canvas=Image.new('RGB',(1440,300*len(rows)), '#16191e')
            draw=ImageDraw.Draw(canvas)
            for row,e in enumerate(rows):
                if kind in ['sfx','zoom']:
                    start,end=max(0,e['start']-1.5),min(479.365,e['end']+1)
                else:start,end=e['start'],e['end']
                for col,f in enumerate([.05,.35,.65,.95]):
                    t=start+(end-start)*f
                    path=W/f"{e['id']}_{col}.jpg"
                    subprocess.run(['ffmpeg','-hide_banner','-v','error','-nostdin','-y','-ss',str(t),
                        '-i',str(source),'-frames:v','1','-vf','scale=360:270',str(path)],check=True)
                    canvas.paste(Image.open(path),(col*360,row*300+30))
                    draw.text((col*360+5,row*300+5),f"{e['id']} {kind} {t:.2f}s",font=font,fill='white')
            out=W/f'{kind}_{page//4}.jpg'
            canvas.save(out,quality=88)
            print(out,flush=True)

def speech():
    import numpy as np
    from scipy.io import wavfile
    from faster_whisper import WhisperModel
    sr,pcm=wavfile.read(ROOT/'work/gameplay0307-1.analysis.wav')
    audio=pcm.astype(np.float32)/32768
    modelpath=json.loads((ROOT/'work/model_path.json').read_text())['path']
    model=WhisperModel(modelpath,device='cpu',compute_type='int8',cpu_threads=8)
    events=[e for e in plan if e['instance']=='main' and e['action'] in ['cut','speed','caption']]
    result=[]
    for e in events:
        # Captions need surrounding context; silence candidates are inspected alone.
        pad=1.5 if e['action']=='caption' else 0
        a=max(0,e['start']-pad);b=min(len(audio)/sr,e['end']+pad)
        segments,_=model.transcribe(audio[int(a*sr):int(b*sr)],language='ja',beam_size=5,
            vad_filter=False,condition_on_previous_text=False,word_timestamps=True,
            hallucination_silence_threshold=1)
        texts=[{'start':round(a+s.start,3),'end':round(a+s.end,3),'text':s.text,
                'avg_logprob':s.avg_logprob,'no_speech_probability':s.no_speech_prob} for s in segments]
        result.append({'id':e['id'],'action':e['action'],'start':a,'end':b,'recognition':texts})
        (W/'speech_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(e['id'],e['action'],json.dumps(texts,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['frames','speech'])
    globals()[p.parse_args().mode]()
