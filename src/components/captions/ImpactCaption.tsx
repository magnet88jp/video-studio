import React from 'react';
import {AbsoluteFill,interpolate,spring,useCurrentFrame,useVideoConfig} from 'remotion';
import defaults from '../../../config/effects.json';
import type {EditEvent} from '../../timeline/schema';
type Props=Partial<Pick<EditEvent,'fontSize'|'position'|'rotation'|'scale'|'stroke'|'shadow'|'entrance'|'exit'|'color'>>&{text:string;durationInFrames:number;frame?:number};
export const ImpactCaption:React.FC<Props>=({text,durationInFrames,fontSize=defaults.captions.fontSize,position='bottom',rotation=0,scale=1,stroke=defaults.captions.strokeWidth,shadow=defaults.captions.shadow,entrance='pop',exit='fade',color=defaults.captions.color,frame:explicitFrame})=>{
 const current=useCurrentFrame();const frame=explicitFrame??current;const {fps}=useVideoConfig();
 const progress=entrance==='none'?1:spring({frame,fps,config:{damping:18,stiffness:220,mass:.6}});
 const fade=exit==='none'?1:interpolate(frame,[Math.max(0,durationInFrames-fps*.12),durationInFrames],[1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
 const pop=entrance==='pop'?0.8+0.2*progress:1;
 return <AbsoluteFill style={{justifyContent:position==='bottom'?'flex-end':position==='center'?'center':'flex-start',alignItems:position==='top-left'?'flex-start':'center',padding:position==='bottom'?`0 12% ${defaults.captions.bottomPercent}%`:'6% 12%',pointerEvents:'none'}}>
   <div style={{fontFamily:defaults.captions.fontFamily,fontSize,fontWeight:900,lineHeight:1.25,maxWidth:'100%',textAlign:'center',whiteSpace:'pre-wrap',overflowWrap:'anywhere',color,WebkitTextStroke:`${stroke}px ${defaults.captions.strokeColor}`,paintOrder:'stroke fill',textShadow:shadow,opacity:fade*(entrance==='fade'?progress:1),transform:`translateY(${entrance==='slide'?(1-progress)*35:0}px) rotate(${rotation}deg) scale(${scale*pop})`}}>{text}</div>
 </AbsoluteFill>;
};
