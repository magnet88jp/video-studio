"""Local, source-hash-bound analysis; candidates are never approval decisions."""
import argparse, hashlib, json, math, re, subprocess, sys, wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'work'; ANALYSIS=WORK/'analysis'; AUDIO=WORK/'audio/commentary.wav'
def read(p): return json.loads(Path(p).read_text())
def save(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def source_path(value=None):
 candidates=sorted(p for p in (ROOT/'input').iterdir() if p.suffix.lower()=='.mp4')
 if not candidates: raise SystemExit('input/ にMP4がありません。')
 print('Input candidates:',*[str(p.relative_to(ROOT)) for p in candidates],sep='\n  ')
 p=(ROOT/value).resolve() if value else candidates[0].resolve()
 if not p.is_relative_to((ROOT/'input').resolve()):raise ValueError('Source must be inside input/')
 return p

def video_info(source):
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)]))
 v=next(s for s in probe['streams'] if s['codec_type']=='video');a=next((s for s in probe['streams'] if s['codec_type']=='audio'),{})
 num,den=map(float,v['avg_frame_rate'].split('/'));fps=num/den
 result={'source':str(source.relative_to(ROOT)),'sha256':digest(source),'duration':float(probe['format']['duration']),'width':v['width'],'height':v['height'],'fps':fps,'fpsRational':v['avg_frame_rate'],'suggestedFps':60 if 55<fps<=61 else fps,'videoCodec':v['codec_name'],'audioCodec':a.get('codec_name'),'audioChannels':a.get('channels'),'audioSampleRate':a.get('sample_rate'),'bitrate':probe['format'].get('bit_rate'),'probe':probe}
 save(ANALYSIS/'video_info.json',result);return result

def extract(source,info):
 meta=ANALYSIS/'audio_meta.json'
 dedicated=WORK/'audio/transcribe_source.json'
 if AUDIO.exists() and dedicated.exists():
  d=read(dedicated)
  if d.get('sourceHash')==info['sha256'] and d.get('audioHash')==digest(AUDIO):
   save(meta,{'sourceHash':info['sha256'],'sampleRate':16000,'channels':1});return
 elif AUDIO.exists() and meta.exists() and read(meta).get('sourceHash')==info['sha256']:return
 AUDIO.parent.mkdir(parents=True,exist_ok=True)
 subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(AUDIO)],check=True)
 save(meta,{'sourceHash':info['sha256'],'sampleRate':16000,'channels':1,'note':'Mixed track, not isolated commentary'})
 save(dedicated,{'sourceHash':info['sha256'],'audioHash':digest(AUDIO)})

def dedicated_transcript(info):
 path=WORK/'transcript.json';meta_path=WORK/'transcribe_cache.json'
 if not path.exists() or not meta_path.exists():return None
 meta=read(meta_path)
 if meta.get('partial') or meta.get('key',{}).get('duration') is not None:return None
 if meta.get('key',{}).get('source',{}).get('sha256')!=info['sha256']:return None
 if meta.get('outputHash')!=digest(path):return None
 rows=read(path)
 if not isinstance(rows,list):return None
 return [{**u,'id':f'u{i+1:04}','needs_review':True} for i,u in enumerate(rows)]

def transcribe(info,force=False,reuse_only=False):
 target=ANALYSIS/'transcript.json';meta=ANALYSIS/'transcript_meta.json'
 dedicated=dedicated_transcript(info)
 if not force and dedicated is not None:
  save(target,dedicated);save(meta,{'sourceHash':info['sha256'],'status':'automatic_not_manually_verified','method':'scripts/transcribe.py; full-length hash-verified cache'})
  return dedicated
 if reuse_only:raise SystemExit('Run scripts/transcribe.py for this complete input first (without --duration). Partial, edited or mismatched caches cannot be reused automatically.')
 if not force and target.exists() and meta.exists() and read(meta).get('sourceHash')==info['sha256'] and read(meta).get('status')!='unavailable':return read(target)
 legacy=WORK/'transcript.json'
 if not force and legacy.exists() and isinstance(read(legacy),dict) and read(legacy).get('source',{}).get('sha256')==info['sha256']:
  data=read(legacy);result=data['utterances'];method=data['method'];status=data['status']
 else:
  result=[];method='faster-whisper int8, independent <=30s windows, word timestamps';status='automatic_not_manually_verified'
  try:
   import numpy as np
   from faster_whisper import WhisperModel
   config=read(ROOT/'config/editing.json');modelpath=WORK/'model_path.json'
   model=WhisperModel(read(modelpath)['path'] if modelpath.exists() else config['whisperModel'],device='cpu',compute_type='int8',cpu_threads=6,local_files_only=True,download_root=str(WORK/'model-cache'))
   with wave.open(str(AUDIO)) as f:audio=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
   left=0
   while left<len(audio):
    right=min(left+30*16000,len(audio))
    if right<len(audio):
     choices=range(left+25*16000,right,1600)
     right=min(choices,key=lambda x:float(np.mean(audio[x:x+800]**2)))
    segments,_=model.transcribe(audio[left:right],language=config.get('language','ja'),beam_size=5,word_timestamps=True,condition_on_previous_text=False,vad_filter=False)
    for s in segments:
     words=[{'start':w.start+left/16000,'end':w.end+left/16000,'word':w.word,'probability':w.probability} for w in (s.words or [])]
     if not words or s.no_speech_prob>.7:continue
     start,end=words[0]['start'],min(info['duration'],words[-1]['end'])
     if end<=start:continue
     confidence=sum(w['probability'] for w in words)/len(words)
     result.append({'start':round(start,3),'end':round(end,3),'text':s.text.strip(),'words':words,'confidence':confidence,'needs_review':confidence<.8,'id':f'u{len(result)+1:04}'})
    print(f'Transcribe {right/16000:.1f}/{info["duration"]:.1f}s',flush=True);left=right
  except (ImportError,OSError,ValueError,RuntimeError) as e:
   status='unavailable';method=str(e);print(f'Transcription unavailable: {e}',file=sys.stderr)
 save(target,result);save(meta,{'sourceHash':info['sha256'],'status':status,'method':method,'limitations':['Mixed game/commentary track; no speaker separation.','Automatic words and timings require listening review.']});return result

def detect_silence(info,utterances):
 config=read(ROOT/'config/editing.json');threshold=config['silenceThresholdSeconds'];padding=config['speechPaddingSeconds'];speech=[]
 try:
  import numpy as np
  from faster_whisper.vad import get_speech_timestamps,VadOptions
  with wave.open(str(AUDIO)) as f:audio=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
  speech=[(s['start']/16000,s['end']/16000) for s in get_speech_timestamps(audio,VadOptions(threshold=.5,min_silence_duration_ms=300))]
 except ImportError:pass
 speech += [(max(0,u['start']-padding),min(info['duration'],u['end']+padding)) for u in utterances]
 merged=[]
 for a,b in sorted(speech):
  if merged and a<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],b)
  else:merged.append([a,b])
 proc=subprocess.run(['ffmpeg','-hide_banner','-nostdin','-i',str(AUDIO),'-af',f'silencedetect=noise={config["silenceDbfs"]}dB:d={threshold}','-f','null','-'],capture_output=True,text=True,check=True)
 acoustic=[];a=None
 for line in proc.stderr.splitlines():
  m=re.search(r'silence_start: ([\d.]+)',line)
  if m:a=float(m[1])
  m=re.search(r'silence_end: ([\d.]+)',line)
  if m and a is not None:acoustic.append((a,min(float(m[1]),info['duration'])));a=None
 if a is not None:acoustic.append((a,info['duration']))
 result=[];cursor=0
 if speech:
  for a,b in merged+[[info['duration'],info['duration']]]:
   if a-cursor>=threshold:result.append({'start':round(cursor,3),'end':round(a,3),'duration':round(a-cursor,3),'confidence':.8 if any(x<=cursor+.1 and y>=a-.1 for x,y in acoustic) else .55,'kind':'no_detected_speech','needsReview':True})
   cursor=max(cursor,b)
 else:
  result=[{'start':a,'end':b,'duration':b-a,'confidence':.8,'kind':'acoustic_silence','needsReview':True} for a,b in acoustic]
 save(ANALYSIS/'silence.json',result);save(ANALYSIS/'silence_meta.json',{'sourceHash':info['sha256'],'thresholdSeconds':threshold,'speechPadding':padding,'acousticIntervals':acoustic,'note':'No detected speech is not proof of unimportant gameplay.'});return result

def detect_reactions(info,utterances):
 import numpy as np
 from scipy.signal import find_peaks
 with wave.open(str(AUDIO)) as f:audio=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
 windows=audio[:len(audio)//1600*1600].reshape(-1,1600);rms=20*np.log10(np.maximum(np.sqrt(np.mean(windows**2,axis=1)),1e-7))
 p50,p85,p98=np.percentile(rms,[50,85,98]);peaks,_=find_peaks(rms,height=p85,distance=20,prominence=3);result=[]
 groups={'surprise':['えっ','うわ','マジ','何これ','嘘'],'danger':['やば','無理','なんで','死ぬ'],'win':['よっしゃ','来た','成功'],'funny':['笑','はは','あは'],'fail':['失敗','負け','落ちた']}
 for n in peaks:
  t=n*.1+.05;near=[u for u in utterances if u['start']-.3<=t<=u['end']+.3];text=' '.join(u['text'] for u in near)
  kind=next((k for k,words in groups.items() if any(w in text for w in words)),'surprise')
  lexical=any(w in text for words in groups.values() for w in words)
  rise=float(rms[n]-np.percentile(rms[max(0,n-50):min(len(rms),n+50)],30))
  rate=sum(len(u['text']) for u in near)/max(.3,sum(u['end']-u['start'] for u in near))
  intensity=float(np.clip(.4*(rms[n]-p50)/max(1,p98-p50)+.3*rise/20+.2*lexical+.1*min(1,rate/10),0,1))
  if intensity<.45:continue
  result.append({'time':round(t,3),'start':round(max(0,t-.2),3),'end':round(min(info['duration'],t+1.1),3),'type':kind,'intensity':round(intensity,3),'text':text,'speechNearby':bool(near),'keywordEvidence':lexical,'rmsDbfs':round(float(rms[n]),2),'riseDb':round(rise,2),'speechCharactersPerSecond':round(rate,2),'needsReview':True,'utteranceIds':[u['id'] for u in near]})
 save(ANALYSIS/'reactions.json',result)
 ranked=sorted(result,key=lambda r:r['intensity']+.15*r['keywordEvidence'],reverse=True);high=[]
 for r in ranked:
  start=max(0,r['time']-2);end=min(info['duration'],start+6)
  if any(start<h['end']+3 and end>h['start']-3 for h in high):continue
  if not r['speechNearby']:continue
  high.append({**r,'start':round(start,3),'end':round(end,3),'confidence':'candidate_only','reason':'Mixed-track loudness, local rise and transcript context; gameplay not automatically classified.'})
  if len(high)==8:break
 save(ANALYSIS/'highlights.json',high);save(ANALYSIS/'reactions_meta.json',{'sourceHash':info['sha256'],'rmsWindowSeconds':.1,'loudnessP85':float(p85),'note':'Game sound can resemble a vocal reaction. Review candidates.'});return result

def build_plan(info):
 
 for name in ['transcript','silence','reactions']:
  meta=ANALYSIS/f'{name}_meta.json'
  if not meta.exists() or read(meta).get('sourceHash')!=info['sha256']:raise SystemExit('Analysis is missing or belongs to another input. Run npm run analyze first.')
 cfg=read(ROOT/'config/editing.json');reactions=read(ANALYSIS/'reactions.json');silence=read(ANALYSIS/'silence.json');transcript=read(ANALYSIS/'transcript.json');high=read(ANALYSIS/'highlights.json');events=[]
 def add(e):e['id']=f'e{len(events)+1:04}';events.append(e)
 for s in silence:
  a,b=s['start']+cfg['speechPaddingSeconds'],s['end']-cfg['speechPaddingSeconds']
  if b>a:add({'start':round(a,3),'end':round(b,3),'type':'cut','enabled':False,'needsReview':True,'scope':'main','reason':'1.2秒以上の無言候補。ゲーム内容と非言語リアクションを確認してから有効化。','evidence':s})
 selected=[];last_effect=None
 for r in sorted(reactions,key=lambda x:x['intensity']+.2*x['keywordEvidence'],reverse=True):
  if not r['speechNearby'] or not r['keywordEvidence'] or any(abs(r['time']-x['time'])<cfg['reactionCooldownSeconds'] for x in selected):continue
  if sum(abs(r['time']-x['time'])<30 for x in selected)>=cfg['maxEffectsPerMinute']:continue
  selected.append(r)
 for r in sorted(selected,key=lambda x:x['time']):
  effect=r['type'] if r['intensity']>=.85 else 'punchZoom'
  if effect==last_effect:effect='funny' if effect=='punchZoom' else 'punchZoom'
  last_effect=effect
  # Do not invent captions from uncertain ASR. Reviewed text can be added in JSON.
  add({'start':r['start'],'end':r['end'],'type':'effect','effect':effect,'intensity':r['intensity'],'enabled':True,'needsReview':True,'reason':'音量急上昇とリアクション語が一致。字幕は音声確認後に追加。','evidence':r})
  asset=read(ROOT/'config/effects.json')['defaultSe'].get(effect)
  if asset:add({'start':r['start'],'end':min(info['duration'],r['start']+.5),'type':'se','asset':asset,'intensity':r['intensity'],'enabled':True,'needsReview':True})
 for u in transcript:
  if u.get('needs_review',True):continue
  if not any(r['start']<u['end'] and r['end']>u['start'] for r in selected):continue
  add({'start':u['start'],'end':u['end'],'type':'caption','caption':u['text'],'enabled':False,'needsReview':True,'reason':'自動文字起こしの字幕候補。音声と照合後 enabled=true に変更。'})
 for s in silence:
  if s['duration']>=8:add({'start':s['start'],'end':s['end'],'type':'speed','rate':2,'enabled':False,'needsReview':True,'scope':'main','reason':'無言が長い区間。単調な移動かは未判定。戦闘・失敗・重要操作なら残す。カットとの同時有効化は禁止。'})
 bgms=sorted((ROOT/'assets/bgm').glob('*'))
 bgm=next((p for p in bgms if p.suffix.lower() in ['.mp3','.wav','.m4a','.aac','.ogg']),None)
 if bgm:add({'start':0,'end':info['duration'],'type':'bgm','asset':str(bgm.relative_to(ROOT)),'loop':True,'volume':cfg['bgmVolume'],'enabled':True})
 plan={'version':1,'source':info['source'],'sourceHash':info['sha256'],'sourceDuration':info['duration'],'settings':{'width':cfg['width'],'height':cfg['height'],'fps':info['suggestedFps'] if cfg['fps']=='source' else cfg['fps']},'digest':{'enabled':cfg['digestEnabled'] and bool(high),'clips':[{'start':high[0]['start'],'end':high[0]['end']}] if high else []},'events':sorted(events,key=lambda e:e['start']),'notes':['Times are source seconds, end exclusive. enabled=false candidates do not change the video.','Audio is mixed: automatic results require review. Cuts/speed/digest and ASR captions default off to preserve content.']}
 target=WORK/'edit_plan.json'
 if target.exists():
  from datetime import datetime
  save(WORK/f'plan_history/edit_plan-{datetime.now().strftime("%Y%m%d-%H%M%S-%f")}.json',read(target))
 save(target,plan);print(f'Plan: {len(events)} events; {len(selected)} effects; duration preserved before review.');return plan

def main(mode='analyze'):
 parser=argparse.ArgumentParser();parser.add_argument('--input');parser.add_argument('--force-transcribe',action='store_true');parser.add_argument('--reuse-transcript',action='store_true',help='Require a complete verified scripts/transcribe.py result; never run another ASR');args=parser.parse_args()
 source=source_path(args.input);info=video_info(source);extract(source,info)
 if mode=='plan':build_plan(info);return
 utterances=transcribe(info,args.force_transcribe,args.reuse_transcript)
 if mode in ['analyze','silence']:detect_silence(info,utterances)
 if mode in ['analyze','reactions']:detect_reactions(info,utterances)
 after=digest(source);assert after==info['sha256'],'Source changed'
 save(ANALYSIS/'source_integrity.json',{'source':info['source'],'before':info['sha256'],'after':after,'unchanged':True})
 print('Analysis complete. Source unchanged.')
