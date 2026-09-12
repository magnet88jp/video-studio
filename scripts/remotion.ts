import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawn,spawnSync} from 'node:child_process';
import {bundle} from '@remotion/bundler';
import {getCompositions,renderMedia,renderStill} from '@remotion/renderer';
import {PlanSchema,TranscriptSchema,type EditorProps,type EditPlan} from '../src/timeline/schema';
import {compileTimeline} from '../src/timeline/compile';
import editing from '../config/editing.json';

const ROOT=process.cwd(),WORK=path.join(ROOT,'work'),PUBLIC=path.join(WORK,'public');
function json(p:string){return JSON.parse(fs.readFileSync(p,'utf8'));}
function readTranscript(){const p=path.join(WORK,'transcript.json');return fs.existsSync(p)?TranscriptSchema.parse(json(p)):[];}
function save(p:string,x:unknown){fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n');}
function command(cmd:string,args:string[]){const r=spawnSync(cmd,args,{cwd:ROOT,stdio:'inherit'});if(r.status!==0)throw new Error(`${cmd} failed: ${r.status}`);}
async function hash(p:string){const h=createHash('sha256');for await(const chunk of fs.createReadStream(p))h.update(chunk);return h.digest('hex');}
function safeSource(s:string){const p=fs.realpathSync(path.resolve(ROOT,s));if(!p.startsWith(path.join(ROOT,'input')+path.sep))throw new Error('source must be a file inside input/');return p;}
function info(source:string){return JSON.parse(spawnSync('ffprobe',['-v','error','-show_format','-show_streams','-of','json',source],{encoding:'utf8'}).stdout);}
function fpsOf(i:any){const v=i.streams.find((s:any)=>s.codec_type==='video');const [a,b]=v.avg_frame_rate.split('/').map(Number);const n=a/b;return n>55&&n<=61?60:n>28&&n<=31?30:n>23&&n<25?24:Math.max(1,Math.round(n));}
async function demoProps():Promise<EditorProps>{
 const files=fs.readdirSync(path.join(ROOT,'input')).filter(p=>/\.mp4$/i.test(p)).sort();if(!files.length)throw new Error('Put an MP4 into input/');
 const source=`input/${files[0]}`;const p=safeSource(source),i=info(p);const sourceHash=await hash(p);
 const plan=PlanSchema.parse({version:1,source,sourceHash,sourceDuration:Math.min(30,Number(i.format.duration)),settings:{width:1920,height:1080,fps:fpsOf(i)},digest:{enabled:false,clips:[]},events:[],notes:['First 30 seconds effect demonstration']});
 save(path.join(WORK,'demo_plan.json'),plan);
 const filename=`media/demo-${sourceHash.slice(0,12)}.mp4`,target=path.join(PUBLIC,filename);
 fs.mkdirSync(path.dirname(target),{recursive:true});
 if(!fs.existsSync(target))command('ffmpeg',['-hide_banner','-v','warning','-nostdin','-n','-i',p,'-t',String(plan.sourceDuration),'-vf',`fps=${plan.settings.fps},scale=-2:1080:flags=lanczos:in_range=full:out_range=limited`,'-c:v','libx264','-crf','18','-preset','fast','-threads','6','-pix_fmt','yuv420p','-c:a','aac','-b:a','256k','-ar','48000','-movflags','+faststart',target]);
 return {plan,media:{[source]:{url:filename}},config:editing};
}
async function planProps(planPath:string):Promise<EditorProps>{
 const plan=PlanSchema.parse(json(planPath));const source=safeSource(plan.source),sourceHash=await hash(source),probe=info(source);
 if(plan.sourceHash&&plan.sourceHash!==sourceHash)throw new Error('Plan belongs to a different source hash. Run analyze and plan.');
 if(Math.abs(Number(probe.format.duration)-plan.sourceDuration)>.1)throw new Error('sourceDuration differs from input');
 const filename=`media/source-${sourceHash.slice(0,12)}-${plan.settings.fps}-${plan.settings.height}.mp4`,target=path.join(PUBLIC,filename);
 fs.mkdirSync(path.dirname(target),{recursive:true});
 if(!fs.existsSync(target)){
  console.log('Preparing H.264 browser copy (original is read-only)...');
  const partial=target.replace('.mp4','.partial.mp4');
  command('ffmpeg',['-hide_banner','-v','warning','-nostdin','-y','-i',source,'-vf',`fps=${plan.settings.fps},scale=-2:${plan.settings.height}:flags=lanczos:out_range=limited`,'-c:v','libx264','-crf','18','-preset','fast','-threads','6','-pix_fmt','yuv420p','-c:a','aac','-b:a','256k','-ar','48000','-movflags','+faststart',partial]);
  fs.renameSync(partial,target);
 }
 const media:EditorProps['media']={[plan.source]:{url:filename}};const warnings:string[]=[];
 for(const e of plan.events.filter(e=>e.enabled&&e.asset)){
  const asset=e.asset!;const requested=path.resolve(ROOT,asset);
  if(!requested.startsWith(path.join(ROOT,'assets')+path.sep)&&!requested.startsWith(path.join(WORK,'fixtures')+path.sep))throw new Error(`Asset must be inside assets/ (or work/fixtures for tests): ${asset}`);
  if(!fs.existsSync(requested)){warnings.push(`Optional asset missing, skipped: ${asset}`);continue;}
  const resolved=fs.realpathSync(requested);if(!resolved.startsWith(path.join(ROOT,'assets')+path.sep)&&!resolved.startsWith(path.join(WORK,'fixtures')+path.sep))throw new Error('Asset symlink escapes allowed folder');
  const digest=await hash(resolved),dest=`assets/${digest.slice(0,16)}${path.extname(resolved)}`;
  fs.mkdirSync(path.dirname(path.join(PUBLIC,dest)),{recursive:true});if(!fs.existsSync(path.join(PUBLIC,dest)))fs.copyFileSync(resolved,path.join(PUBLIC,dest));
  const p=spawnSync('ffprobe',['-v','error','-show_format','-of','json',resolved],{encoding:'utf8'});
  media[asset]={url:dest,duration:p.status===0?Number(JSON.parse(p.stdout).format.duration)||undefined:undefined};
 }
 for(const s of compileTimeline(plan).segments.filter(s=>s.rate!==1&&s.freezeAt===undefined)){
  const key=createHash('sha256').update(JSON.stringify([sourceHash,s.sourceStart,s.sourceEnd,s.rate])).digest('hex').slice(0,16);
  const filename=`audio/tempo-${key}.wav`,target=path.join(PUBLIC,filename);fs.mkdirSync(path.dirname(target),{recursive:true});
  if(!fs.existsSync(target))command('ffmpeg',['-v','error','-nostdin','-y','-ss',String(s.sourceStart),'-i',source,'-vn','-af',`atrim=duration=${s.sourceEnd-s.sourceStart},asetpts=PTS-STARTPTS,atempo=${s.rate}`,'-ar','48000','-c:a','pcm_s16le',target]);
  media[`audio:${s.id}`]={url:filename};
 }
 save(path.join(WORK,'analysis/media_warnings.json'),warnings);for(const warning of warnings)console.warn(warning);
 save(path.join(WORK,'resolved_timeline.json'),compileTimeline(plan));return {plan,media,config:editing};
}
async function main(){
 const mode=process.argv[2]??'preview';if(!['studio','render','preview','demo','validate'].includes(mode))throw new Error('Unknown mode');
 const args=process.argv.slice(3);function arg(name:string){const i=args.indexOf(name);return i<0?undefined:args[i+1];}
 fs.mkdirSync(PUBLIC,{recursive:true});fs.mkdirSync(path.join(ROOT,'output'),{recursive:true});
 const props:EditorProps={...(mode==='demo'?await demoProps():await planProps(path.resolve(ROOT,arg('--plan')??'work/edit_plan.json'))),transcript:readTranscript()};
 const source=safeSource(props.plan.source),before=await hash(source);
 const propsPath=path.join(WORK,'studio_props.json');save(propsPath,props);
 if(mode==='studio'){
  fs.watchFile(path.join(WORK,'transcript.json'),{interval:500},()=>{try{props.transcript=readTranscript();save(propsPath,props);}catch(error){console.error('Invalid transcript; keeping last valid subtitles:',error);}});
  const child=spawn(path.join(ROOT,'node_modules/.bin/remotion'),['studio','src/index.ts','--props',propsPath,'--public-dir',PUBLIC,'--port','3333','--no-open'],{stdio:'inherit',env:{...process.env,BROWSER:'none'}});
  child.on('exit',code=>process.exit(code??1));return;
 }
 const serveUrl=await bundle({entryPoint:path.join(ROOT,'src/index.ts'),outDir:path.join(WORK,'remotion-bundle'),publicDir:PUBLIC,enableCaching:false});
 const browserExecutable=process.env.REMOTION_BROWSER??(fs.existsSync('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')?'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome':null);
 const comps=await getCompositions(serveUrl,{inputProps:props,browserExecutable});
 save(path.join(WORK,'analysis/compositions.json'),comps.map(c=>({id:c.id,durationInFrames:c.durationInFrames,fps:c.fps,width:c.width,height:c.height})));
 const composition=comps.find(c=>c.id===(mode==='demo'?'DemoVideo':'GameVideo'));if(!composition)throw new Error('Composition missing');
 if(mode==='validate'){console.log(comps.map(c=>({id:c.id,durationInFrames:c.durationInFrames,fps:c.fps})));return;}
 const seconds=Number(arg('--seconds')??editing.render.previewSeconds);const start=Number(arg('--start')??0);
 if(!Number.isFinite(seconds)||seconds<=0||!Number.isFinite(start)||start<0)throw new Error('Invalid preview range');
 const first=Math.round(start*composition.fps),last=Math.min(composition.durationInFrames-1,first+Math.round(seconds*composition.fps)-1);
 if(first>last)throw new Error('Preview starts beyond timeline');
 const renderHash=createHash('sha256').update(JSON.stringify(props));
 for(const dir of ['src','config'])for(const file of fs.readdirSync(path.join(ROOT,dir),{recursive:true}).map(String).filter(f=>/\.(tsx?|json)$/.test(f)).sort())renderHash.update(fs.readFileSync(path.join(ROOT,dir,file)));
 const fingerprint=renderHash.digest('hex');
 async function render(kind:'preview'|'final'|'demo'){
  let lastProgress=-1;const output=path.join(ROOT,`output/${kind}.mp4`),partial=path.join(WORK,`${kind}.partial.mp4`);
  const frameRange: [number,number]|undefined=kind==='final'?undefined:[first,last];
  await renderMedia({composition:composition!,serveUrl,inputProps:props,browserExecutable,codec:'h264',audioCodec:'aac',audioBitrate:'256k',pixelFormat:'yuv420p',colorSpace:'bt709',outputLocation:partial,frameRange,scale:kind==='final'?1:editing.render.previewScale,crf:kind==='final'?editing.render.crf:25,concurrency:editing.render.concurrency,x264Preset:'veryfast',onProgress:p=>{const percent=Math.floor(p.progress*20)*5;if(percent!==lastProgress){console.log(`${kind}: ${percent}%`);lastProgress=percent;}}});
  fs.renameSync(partial,output);
  const probe=info(output),v=probe.streams.find((s:any)=>s.codec_type==='video'),a=probe.streams.find((s:any)=>s.codec_type==='audio');
  const expected=(frameRange?last-first+1:composition!.durationInFrames)/composition!.fps;
  if(v.codec_name!=='h264'||a?.codec_name!=='aac'||Math.abs(Number(v.duration)-expected)>.1)throw new Error('Output codec/duration validation failed');
  if(kind==='final'&&(v.width!==props.plan.settings.width||v.height!==props.plan.settings.height))throw new Error('Resolution mismatch');
  const after=await hash(source);if(after!==before)throw new Error('Source changed');
  save(path.join(WORK,`analysis/${kind}_validation.json`),{sourceUnchanged:true,before,after,output,fingerprint,expectedDuration:expected,probe});
  const sampleFrames=kind==='demo'?[4,9.12,15.1,21.03].map(t=>Math.round(t*composition!.fps)):kind==='final'?[0,Math.round(composition!.durationInFrames/2),composition!.durationInFrames-2]:[first,Math.min(last,first+Math.round(3*composition!.fps)),Math.max(first,last-1)];
  for(const frame of sampleFrames)await renderStill({composition:composition!,serveUrl,inputProps:props,browserExecutable,output:path.join(WORK,`previews/${kind}-${frame}.png`),frame,scale:.5});
  console.log(`${kind} ready: ${output}`);
 }
 if(mode==='render'){
  const validation=path.join(WORK,'analysis/preview_validation.json');
  if(!fs.existsSync(validation)||json(validation).fingerprint!==fingerprint)await render('preview');
  await render('final');
 }else await render(mode==='demo'?'demo':'preview');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
