import React from 'react';
import {AbsoluteFill,Sequence,staticFile,useCurrentFrame,useVideoConfig,Audio,Loop} from 'remotion';
import {Video} from '@remotion/media';
import {compileTimeline,type Segment,type TimedEvent} from '../timeline/compile';
import type {EditorProps} from '../timeline/schema';
import {ReactionEffect,strength} from '../effects/presets';
import {FreezeFrame} from '../components/effects/primitives';
import {SlowMotion,SpeedUp} from '../components/effects/Playback';
import {ImpactCaption} from '../components/captions/ImpactCaption';
import {MediaOverlay} from '../components/overlays/MediaOverlay';
import {Subtitle} from '../components/captions/Subtitle';
import defaults from '../../config/effects.json';
const Clip:React.FC<EditorProps&{segment:Segment;events:TimedEvent[]}>=p=>{
 const frame=useCurrentFrame(),{fps}=useVideoConfig(),s=p.segment,global=frame+s.from;
 const url=staticFile(p.media[p.plan.source].url);
 const videoProps={src:url,muted:true,trimBefore:Math.round((s.freezeAt??s.sourceStart)*fps),playbackRate:s.rate,objectFit:'contain' as const,style:{width:'100%',height:'100%'}};
 let scene:React.ReactNode=s.freezeAt!==undefined?<FreezeFrame frame={0}><Video {...videoProps}/></FreezeFrame>:s.rate<1?<SlowMotion {...videoProps}/>:s.rate>1?<SpeedUp {...videoProps}/>:<Video {...videoProps}/>;
 for(const t of p.events.filter(t=>t.event.type==='effect'&&global>=t.from&&global<t.from+t.durationInFrames))scene=<ReactionEffect key={t.event.id} event={t.event} frame={global-t.from+t.offsetFrames} durationInFrames={t.durationInFrames+t.offsetFrames} config={p.config}>{scene}</ReactionEffect>;
 const audio=p.media[`audio:${s.id}`];
 const subtitles=s.freezeAt===undefined?(p.transcript??[]).filter(u=>frame>=Math.round((u.start-s.sourceStart)/s.rate*fps)&&frame<Math.round((u.end-s.sourceStart)/s.rate*fps)):[];
 return <AbsoluteFill style={{overflow:'hidden'}}>{scene}{subtitles.slice(-1).map((u,index)=><Subtitle key={`${u.start}-${index}`} text={u.text} start={(u.start-s.sourceStart)/s.rate} end={(u.end-s.sourceStart)/s.rate}/>)}{s.freezeAt===undefined&&(audio?<Audio src={staticFile(audio.url)}/>:<Audio src={url} trimBefore={Math.round(s.sourceStart*fps)} volume={1}/>)}</AbsoluteFill>;
};
const Sound:React.FC<{t:TimedEvent;props:EditorProps;reactions:TimedEvent[]}>=({t,props:p,reactions})=>{
 const frame=useCurrentFrame(),{fps}=useVideoConfig(),e=t.event,asset=p.media[e.asset!];if(!asset)return null;
 const bgm=e.type==='bgm';const global=t.from+frame;
 const duck=reactions.reduce((v,r)=>Math.min(v,global>=r.from-fps*.15&&global<r.from+r.durationInFrames+fps*.25?p.config.reactionBgmMultiplier:1),1);
 const volume=(e.volume??(bgm?p.config.bgmVolume:.5))*(bgm?duck:strength(p.config,'soundEffects',e.intensity));
 const audio=<Audio src={staticFile(asset.url)} volume={volume}/>;
 return <Sequence from={-t.offsetFrames} layout="none">{e.loop&&asset.duration?<Loop durationInFrames={Math.max(1,Math.floor(asset.duration*fps))}>{audio}</Loop>:audio}</Sequence>;
};
export const GameVideo:React.FC<EditorProps>=p=>{
 const timeline=compileTimeline(p.plan),reactions=timeline.events.filter(t=>t.event.type==='effect');
 if(!p.media[p.plan.source])return <AbsoluteFill style={{background:'#101216',color:'white',fontSize:50,padding:80}}>npm run analyze → npm run plan → npm run studio</AbsoluteFill>;
 return <AbsoluteFill style={{background:'#101216'}}>
  {timeline.segments.map(s=><Sequence key={s.id} from={s.from} durationInFrames={s.durationInFrames}><Clip {...p} segment={s} events={timeline.events}/></Sequence>)}
  {timeline.events.filter(t=>['caption','overlay','se','bgm'].includes(t.event.type)).map((t,index)=>{
   const e=t.event;return <Sequence key={`${e.id}-${index}`} from={t.from} durationInFrames={t.durationInFrames} layout={e.type==='se'||e.type==='bgm'?'none':'absolute-fill'}>
    {e.type==='caption'&&strength(p.config,'captions',1)>0&&<ImpactCaption {...e} text={e.caption!} fontSize={e.fontSize??defaults.captions.fontSize} durationInFrames={t.durationInFrames}/>}
    {e.type==='overlay'&&p.media[e.asset!]&&<MediaOverlay event={e} asset={p.media[e.asset!]}/>}
    {(e.type==='se'||e.type==='bgm')&&<Sound t={t} props={p} reactions={reactions}/>}
   </Sequence>;
  })}
 </AbsoluteFill>;
};
