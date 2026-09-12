import React from 'react';
import {AbsoluteFill,interpolate,useVideoConfig} from 'remotion';
import {PunchZoom,ScreenShake,Flash,Monochrome,RedAlert} from '../components/effects/primitives';
import {ImpactCaption} from '../components/captions/ImpactCaption';
import type {EditEvent,EditorConfig} from '../timeline/schema';
import defaults from '../../config/effects.json';
export function strength(config:EditorConfig,key:string,intensity:number){
 const styles:Record<string,Record<string,number>>=defaults.styles;
 const baseline=styles.energetic[key]??1;
 return Math.max(0,Math.min(1,intensity*config.strength*(styles[config.style]?.[key]??baseline)*(config.effects[key]??baseline)/baseline));
}
type Props=React.PropsWithChildren<{event:EditEvent;frame:number;durationInFrames:number;config:EditorConfig}>;
export const ReactionEffect:React.FC<Props>=({children,event:e,frame,durationInFrames,config})=>{
 const {fps}=useVideoConfig(),name=e.effect??'',i=e.intensity;let scene=children;
 if(['punchZoom','surprise','win','funny'].includes(name))scene=<PunchZoom frame={frame} intensity={strength(config,'zoom',i)}>{scene}</PunchZoom>;
 if(['screenShake','surprise','danger'].includes(name))scene=<ScreenShake frame={frame} intensity={strength(config,'shake',i)}>{scene}</ScreenShake>;
 if(['monochrome','fail','funnyFail'].includes(name))scene=<Monochrome intensity={i*config.strength}>{scene}</Monochrome>;
 if(['fail','funnyFail'].includes(name)){
  const scale=interpolate(frame,[0,.2*fps,.6*fps],[1,1-.05*i,1],{extrapolateRight:'clamp'});
  scene=<AbsoluteFill style={{transform:`scale(${scale})`}}>{scene}</AbsoluteFill>;
 }
 const color=e.color??(name==='danger'?defaults.captions.danger:name==='win'?defaults.captions.win:name==='surprise'?defaults.captions.surprise:defaults.captions.color);
 return <AbsoluteFill>{scene}
  {['flash','surprise','win'].includes(name)&&<Flash frame={frame} intensity={strength(config,'flash',i)}/>}
  {['redAlert','danger'].includes(name)&&<RedAlert frame={frame} intensity={i*config.strength}/>}
  {e.caption&&strength(config,'captions',1)>0&&<ImpactCaption {...e} frame={frame} text={e.caption} color={color} fontSize={e.fontSize??defaults.captions.fontSize*(.85+.3*strength(config,'captions',i))} durationInFrames={durationInFrames}/>}
 </AbsoluteFill>;
};
const preset=(effect:EditEvent['effect'])=>function Preset(p:Props){return <ReactionEffect {...p} event={{...p.event,effect}}/>;};
export const SurpriseEffect=preset('surprise');
export const FailEffect=preset('fail');
export const WinEffect=preset('win');
export const DangerEffect=preset('danger');
export const FunnyEffect=preset('funny');
export const FunnyFail=preset('funnyFail');
