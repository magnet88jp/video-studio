import {PlanSchema,type EditPlan,type EditEvent} from './schema';
export type Segment={id:string;sourceStart:number;sourceEnd:number;from:number;durationInFrames:number;rate:number;freezeAt?:number;scope:'main'|'opening'};
export type TimedEvent={event:EditEvent;from:number;durationInFrames:number;offsetFrames:number;scope:'main'|'opening'};
export function compileTimeline(raw:EditPlan){
 const plan=PlanSchema.parse(raw),fps=plan.settings.fps,segments:Segment[]=[];let exact=0;
 const ranges=[...(plan.digest.enabled?plan.digest.clips.map(c=>({...c,scope:'opening' as const})):[]),{start:0,end:plan.sourceDuration,scope:'main' as const}];
 for(const range of ranges){
  const structures=plan.events.filter(e=>e.enabled&&(e.scope==='both'||e.scope===range.scope)&&['cut','speed','freeze'].includes(e.type));
  // Fail freezes replace only a brief source interval, never repeat a spoken syllable.
  const fails=plan.events.filter(e=>e.enabled&&(e.scope==='both'||e.scope===range.scope)&&e.type==='effect'&&['fail','funnyFail'].includes(e.effect??''));
  const implicit=fails.map(e=>({...e,type:'freeze' as const,end:Math.min(e.end,e.start+(e.holdSeconds??.25)),freezeAt:e.freezeAt??e.start})).filter(e=>!structures.some(s=>s.start<e.end&&s.end>e.start));
  const operations=[...structures,...implicit];
  const boundaries=[...new Set([range.start,range.end,...operations.flatMap(e=>[e.start,e.end]).filter(t=>t>range.start&&t<range.end)])].sort((a,b)=>a-b);
  for(let i=0;i<boundaries.length-1;i++){
   const a=boundaries[i],b=boundaries[i+1],op=operations.find(e=>e.start<=a+1e-7&&e.end>=b-1e-7);
   if(op?.type==='cut')continue;
   const rate=op?.type==='speed'?op.rate!:1;
   const seconds=op?.type==='freeze'?(op.holdSeconds??op.end-op.start)*(b-a)/(op.end-op.start):(b-a)/rate;
   const from=Math.round(exact*fps);exact+=seconds;const n=Math.round(exact*fps)-from;
   if(n>0)segments.push({id:`clip-${segments.length}`,sourceStart:a,sourceEnd:b,from,durationInFrames:n,rate,freezeAt:op?.type==='freeze'?(op.freezeAt??op.start):undefined,scope:range.scope});
  }
 }
 const events:TimedEvent[]=[];
 for(const event of plan.events.filter(e=>e.enabled&&!['cut','speed','freeze'].includes(e.type))){
  let offsetFrames=0;
  for(const s of segments){
   if(event.scope!=='both'&&event.scope!==s.scope)continue;
   const a=Math.max(event.start,s.sourceStart),b=Math.min(event.end,s.sourceEnd);if(b<=a)continue;
   if(a===event.start)offsetFrames=0;
   const ratio=s.durationInFrames/(s.sourceEnd-s.sourceStart);
   const from=s.from+Math.round((a-s.sourceStart)*ratio),end=s.from+Math.round((b-s.sourceStart)*ratio);
   if(end>from){events.push({event,from,durationInFrames:end-from,offsetFrames,scope:s.scope});offsetFrames+=end-from;}
  }
 }
 return {segments,events,durationInFrames:Math.max(1,Math.round(exact*fps))};
}
