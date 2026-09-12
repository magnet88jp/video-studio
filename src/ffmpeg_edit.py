"""Reproducible FFmpeg editor: original read only, work files isolated, final verified."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
import hashlib
from fractions import Fraction
import json
import math
from pathlib import Path
import shutil
import subprocess
import time
import unicodedata
import wave

from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/final_edit'
WIDTH,HEIGHT,FPS,SR=1920,1080,30,48000

def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(8*1024*1024),b''):h.update(data)
    return h.hexdigest()

def fingerprint(path):
    s=path.stat()
    return {'path':str(path),'size_bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256':digest(path)}

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)]))

def run(cmd,log):
    log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('w') as f:
        result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'FFmpeg failed ({result.returncode}); {log}\n'+log.read_text()[-4500:])

def font_path():
    for p in Path('/System/Library/Fonts').glob('*.ttc'):
        if unicodedata.normalize('NFC',p.name)=='ヒラギノ角ゴシック W7.ttc':return p
    raise RuntimeError('Japanese Hiragino W7 font not found; configure font_path().')

def render_caption(effect):
    size=42 if effect.get('text_type')=='editorial_label' else 63
    font=ImageFont.truetype(str(font_path()),size*2)
    text=effect['caption']
    pad=24;stroke=4 if size==42 else 5
    bb=font.getbbox(text,stroke_width=stroke*2)
    w,h=bb[2]-bb[0]+pad*4,bb[3]-bb[1]+pad*4
    im=Image.new('RGBA',(w,h),(0,0,0,0))
    d=ImageDraw.Draw(im)
    d.text((pad*2-bb[0],pad*2-bb[1]),text,font=font,fill='white',stroke_width=stroke*2,stroke_fill='#151515')
    im=im.resize((w//2,h//2),Image.Resampling.LANCZOS)
    if im.width>1300:
        im=im.resize((1300,round(im.height*1300/im.width)),Image.Resampling.LANCZOS)
    path=WORK/'captions'/f"{effect['id']}.png"
    path.parent.mkdir(exist_ok=True)
    im.save(path)
    effect['sprite_path']=str(path)
    effect['sprite_size']=list(im.size)

def generate_sfx():
    # Original synthesized 250ms downward chirp, not a downloaded licensed asset.
    path=WORK/'sfx/short_comic_drop.wav';path.parent.mkdir(exist_ok=True)
    values=[];phase=0.
    for i in range(round(.25*SR)):
        t=i/SR
        phase+=2*math.pi*(520-390*t/.25)/SR
        envelope=min(1,t/.006)*min(1,(.25-t)/.05)*math.exp(-8*t)
        v=int(.027*32767*envelope*(math.sin(phase)+.18*math.sin(2*phase))/1.18)
        values.append(v)
    import array
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes(array.array('h',values).tobytes())
    return path

def prepare(planpath):
    original=json.loads(planpath.read_text());decisions=json.loads((ROOT/'src/edit_decisions.json').read_text())
    source=(ROOT/original[0]['plan']['source']).resolve()
    assert source.is_file()
    before=fingerprint(source)
    write(WORK/'source_before.json',before)
    p=probe(source);write(WORK/'source_probe.json',p)
    clips=[];effects=[]
    for event in original:
        e=deepcopy(event);e.pop('plan',None)
        if e['layer']!='video':
            if e['id'] in decisions['omit_effects']:continue
            if e['id'] in decisions['caption_overrides']:e.update(decisions['caption_overrides'][e['id']])
            if e['action']=='caption':render_caption(e)
            effects.append(e);continue
        if e['id'] in decisions['keep_instead_of_cut'] or e['id'] in decisions['keep_instead_of_speed']:
            e['action']='keep';e['rate']=1.0
        if e['id'] in decisions['speed_overrides']:
            e.update(decisions['speed_overrides'][e['id']])
        if e['action']=='cut':continue
        e['rate']=e.get('rate',1)
        if e['id'] in decisions['speed_preserve_prefix']:
            until=decisions['speed_preserve_prefix'][e['id']]['until']
            prefix=deepcopy(e);prefix.update(id=e['id']+'_preserved',end=until,action='keep',rate=1)
            clips.append(prefix);e['start']=until
        clips.append(e)
    total_exact=0.;frames_so_far=0
    for c in clips:
        total_exact+=(c['end']-c['start'])/c['rate']
        next_frame=round(total_exact*FPS)
        c['frames']=next_frame-frames_so_far
        c['output_start']=frames_so_far/FPS;c['output_end']=next_frame/FPS
        c['render_duration']=c['frames']/FPS
        frames_so_far=next_frame
    for e in effects:
        parent=next(c for c in clips if c['id']==e['target_clip_id'])
        assert parent['start']<=e['start']<e['end']<=parent['end'],e
        e['local_start']=(e['start']-parent['start'])/parent['rate']
        e['local_end']=(e['end']-parent['start'])/parent['rate']
        e['output_start']=parent['output_start']+e['local_start']
        e['output_end']=parent['output_start']+e['local_end']
    resolved={'source':str(source),'source_sha256':before['sha256'],'input_plan_sha256':digest(planpath),'decisions':decisions,
              'video':{'width':WIDTH,'height':HEIGHT,'fps':FPS,'codec':'h264','pixel_format':'yuv420p'},
              'audio':{'codec':'aac','sample_rate':SR,'channels':2,'bitrate':'192k'},
              'duration_seconds':frames_so_far/FPS,'frame_count':frames_so_far,
              'clips':clips,'effects':effects,'sfx_path':str(generate_sfx()),
              'review_limitations':'ASRとサンプル静止画に基づく確認。音声の手動聴取は未実施。'}
    write(WORK/'resolved_plan.json',resolved)
    print(f'Prepared {len(clips)} clips, {len(effects)} effects, {frames_so_far/FPS:.3f}s',flush=True)
    return resolved,before

def render_clip(clip,resolved,preset):
    cid=clip['id'];out=WORK/'segments'/f'{cid}.mkv';out.parent.mkdir(exist_ok=True)
    effects=[e for e in resolved['effects'] if e['target_clip_id']==cid]
    key=hashlib.sha256(json.dumps({'clip':clip,'effects':effects,'preset':preset,
        'source_sha256':resolved['source_sha256'],'renderer_sha256':digest(Path(__file__))},sort_keys=True).encode()).hexdigest()
    stamp=out.with_suffix('.key')
    if out.exists() and stamp.exists() and stamp.read_text()==key:
        return cid,'cached'
    cmd=['ffmpeg','-hide_banner','-v','warning','-nostdin','-y','-threads','4',
         '-ss',f"{clip['start']:.6f}",'-t',f"{clip['end']-clip['start']:.6f}",'-i',resolved['source']]
    captions=[e for e in effects if e['action']=='caption']
    for e in captions:cmd+=['-i',e['sprite_path']]
    sound=[e for e in effects if e['action']=='sfx']
    if sound:cmd+=['-i',resolved['sfx_path']]
    d=clip['render_duration'];frames=clip['frames'];rate=clip['rate']
    f=[f"[0:v]setpts=(PTS-STARTPTS)/{rate},fps={FPS}:start_time=0,"
       f"scale=1440:1080:flags=lanczos:in_range=full:out_range=limited,setsar=1,"
       f"pad=1920:1080:240:0:color=0x101216,tpad=stop_mode=clone:stop_duration=0.1,"
       f"trim=end_frame={frames},setpts=N/({FPS}*TB)[base]"]
    current='base'
    zooms=[e for e in effects if e['action']=='zoom']
    if zooms:
        terms=[]
        for z in zooms:
            a=z['local_start']*FPS;b=z['local_end']*FPS
            zi=z.get('animation',{}).get('in_seconds',.1)*FPS
            zo=z.get('animation',{}).get('out_seconds',.12)*FPS
            terms.append(f"if(between(on,{a:.4f},{b:.4f}),{z['scale']-1:.4f}*max(0,min(1,min((on-{a:.4f})/{zi:.4f},({b:.4f}-on)/{zo:.4f}))),0)")
        zoom='1+'+'+'.join(terms)
        f.append(f"[{current}]zoompan=z='{zoom}':x='iw/2-iw/(2*zoom)':y=0:d=1:s=1920x1080:fps={FPS}[zoomed]")
        current='zoomed'
    for idx,e in enumerate(captions,1):
        x='300' if e.get('text_type')=='editorial_label' else '(W-w)/2'
        y='52' if e.get('text_type')=='editorial_label' else '868'
        label=f'cap{idx}'
        f.append(f"[{current}][{idx}:v]overlay=x={x}:y={y}:eof_action=repeat:repeatlast=1:"
                 f"enable='gte(t,{e['local_start']:.6f})*lt(t,{e['local_end']:.6f})'[{label}]")
        current=label
    f.append(f'[{current}]format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709[v]')
    audio=f'[0:a]asetpts=PTS-STARTPTS,aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo'
    if rate!=1:audio+=f',atempo={rate},volume=-3dB'
    audio+=f',apad,atrim=end_sample={frames*(SR//FPS)},asetpts=N/SR/TB'
    # 4ms ramps only de-click edits; original dynamics and voice remain unchanged.
    audio+=f',afade=t=in:st=0:d=0.004,afade=t=out:st={max(0,d-.004):.6f}:d=0.004[a0]'
    f.append(audio)
    if sound:
        assert len(sound)==1
        e=sound[0];index=1+len(captions)
        delay=round(e['local_start']*SR)
        f.append(f'[{index}:a]aformat=channel_layouts=stereo,adelay={delay}S:all=1[sound]')
        f.append('[a0][sound]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:level=0:latency=1[a]')
    else:f.append('[a0]anull[a]')
    graph=WORK/'filters'/f'{cid}.txt';graph.parent.mkdir(exist_ok=True);graph.write_text(';\n'.join(f))
    cmd+=['-filter_complex_threads','2','-filter_complex',';\n'.join(f),'-map','[v]','-map','[a]',
          '-c:v','libx264','-preset',preset,'-crf','19','-threads','4','-profile:v','high','-level:v','4.1',
          '-pix_fmt','yuv420p','-g','60','-keyint_min','30','-color_range','tv','-colorspace','bt709',
          '-color_primaries','bt709','-color_trc','bt709','-c:a','pcm_s16le','-ar',str(SR),'-ac','2',
          '-t',f'{d:.9f}',str(out)]
    commandfile=WORK/'commands'/f'{cid}.json';write(commandfile,cmd)
    run(cmd,WORK/'logs'/f'{cid}.log')
    p=probe(out)
    v=next(s for s in p['streams'] if s['codec_type']=='video')
    assert (v['width'],v['height'],v['codec_name'])==(WIDTH,HEIGHT,'h264')
    stamp.write_text(key)
    return cid,'rendered'

def assemble(resolved,output):
    listing=WORK/'concat.txt'
    listing.write_text(''.join(f"file '{WORK/'segments'/(c['id']+'.mkv')}'\n" for c in resolved['clips']))
    temp=WORK/'final.assembling.mp4'
    cmd=['ffmpeg','-hide_banner','-v','warning','-nostdin','-y','-f','concat','-safe','0','-i',str(listing),
         '-map','0:v:0','-map','0:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-ar',str(SR),'-ac','2',
         '-movflags','+faststart','-video_track_timescale','90000','-map_metadata','-1',
         '-metadata','title=Gameplay Highlights','-t',str(resolved['duration_seconds']),str(temp)]
    write(WORK/'commands/assemble.json',cmd);run(cmd,WORK/'logs/assemble.log')
    p=probe(temp)
    assert abs(float(p['format']['duration'])-resolved['duration_seconds'])<.15
    output.parent.mkdir(exist_ok=True)
    if output.exists():
        backup=WORK/f'previous_final_{time.time_ns()}.mp4';shutil.copy2(output,backup)
    shutil.copy2(temp,output)
    print(f'Assembled {output}',flush=True)

def validate(output,resolved,before):
    p=probe(output);write(WORK/'final_probe.json',p)
    v=next(s for s in p['streams'] if s['codec_type']=='video')
    a=next(s for s in p['streams'] if s['codec_type']=='audio')
    assert v['codec_name']=='h264' and a['codec_name']=='aac'
    assert (v['width'],v['height'])==(WIDTH,HEIGHT)
    # Matroska's millisecond timebase can round the final sample duration by <1ms.
    # Verify nominal cadence and actual mean, rather than exact fraction spelling.
    assert v['r_frame_rate']=='30/1' and abs(float(Fraction(v['avg_frame_rate']))-FPS)<.001
    assert int(v['nb_frames'])==resolved['frame_count'],(v['nb_frames'],resolved['frame_count'])
    assert abs(float(v['duration'])-float(a['duration']))<=.05
    assert abs(float(p['format']['duration'])-resolved['duration_seconds'])<=.05
    run(['ffmpeg','-hide_banner','-v','error','-xerror','-nostdin','-i',str(output),'-f','null','-'],WORK/'logs/full_decode.log')
    after=fingerprint(Path(resolved['source']));assert before==after,'Original source changed'
    # Sample every caption, zoom, speed midpoint, and the start/end of the program.
    points=[.7,5.8,7.3,resolved['duration_seconds']-1]
    points+=[(e['output_start']+e['output_end'])/2 for e in resolved['effects'] if e['action'] in ['caption','zoom']]
    points+=[(c['output_start']+c['output_end'])/2 for c in resolved['clips'] if c['action']=='speed']
    points=sorted(set(round(t,3) for t in points))
    folder=WORK/'validation_frames';folder.mkdir(exist_ok=True)
    font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',20)
    for i,t in enumerate(points):
        path=folder/f'{i:03}.jpg'
        run(['ffmpeg','-hide_banner','-v','error','-nostdin','-y','-ss',str(t),'-i',str(output),
             '-frames:v','1','-vf','scale=480:270',str(path)],WORK/'logs/frame.log')
    for page in range(0,len(points),12):
        rows=math.ceil(min(12,len(points)-page)/3)
        canvas=Image.new('RGB',(1440,rows*300),'#111318');draw=ImageDraw.Draw(canvas)
        for offset,t in enumerate(points[page:page+12]):
            x=(offset%3)*480;y=(offset//3)*300
            canvas.paste(Image.open(folder/f'{page+offset:03}.jpg'),(x,y+30))
            draw.text((x+8,y+4),f'Output {t:.3f}s',font=font,fill='white')
        canvas.save(WORK/f'validation_contact_{page//12}.jpg',quality=90)
    write(WORK/'validation.json',{'passed':True,'output':str(output),'duration_seconds':float(p['format']['duration']),
          'frame_count':int(v['nb_frames']),'format':'1920x1080 / 30fps / H.264 High / AAC stereo 48kHz',
          'audio_duration_seconds':float(a['duration']),'full_decode_errors':0,
          'nominal_frame_rate':v['r_frame_rate'],'mean_frame_rate':v['avg_frame_rate'],
          'source_unchanged':before==after,'source_before':before,'source_after':after,
          'review_frame_times':points,'visual_qa':'pending model inspection of contact sheets',
          'output_sha256':digest(output)})
    print(json.dumps({'validation_passed':True,'duration':p['format']['duration'],'frames':v['nb_frames'],
                      'source_unchanged':True,'review_sheets':math.ceil(len(points)/12)},ensure_ascii=False),flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',type=Path,default=ROOT/'work/legacy/edit_plan_ffmpeg.json')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/final.mp4')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--preview',action='store_true',help='Render only the opening and one ordinary caption clip')
    parser.add_argument('--validate-only',action='store_true')
    parser.add_argument('--jobs',type=int,default=2)
    parser.add_argument('--preset',default='fast')
    args=parser.parse_args();WORK.mkdir(parents=True,exist_ok=True)
    plan=json.loads(args.plan.read_text());source=(ROOT/plan[0]['plan']['source']).resolve()
    if args.output.resolve()==source or args.output.resolve().is_relative_to(ROOT/'input'):
        raise SystemExit('Refusing to write to the original/input directory.')
    if args.validate_only:
        resolved=json.loads((WORK/'resolved_plan.json').read_text());before=json.loads((WORK/'source_before.json').read_text())
    else:
        resolved,before=prepare(args.plan)
        if args.prepare_only:return
        clips=resolved['clips'][:2] if args.preview else resolved['clips']
        started=time.monotonic()
        with ThreadPoolExecutor(max_workers=max(1,args.jobs)) as pool:
            futures=[pool.submit(render_clip,c,resolved,args.preset) for c in clips]
            for n,f in enumerate(as_completed(futures),1):
                cid,status=f.result();print(f'{n}/{len(clips)} {cid} {status} elapsed={time.monotonic()-started:.1f}s',flush=True)
        assert fingerprint(source)==before,'Original source changed'
        if args.preview:return
        assemble(resolved,args.output)
    validate(args.output,resolved,before)

if __name__=='__main__':main()
