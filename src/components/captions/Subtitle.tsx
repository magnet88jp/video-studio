import React from 'react';
import {useCurrentFrame,useVideoConfig} from 'remotion';
import defaults from '../../../config/effects.json';

type Props={text:string;start:number;end:number;fontSize?:number;maxWidth?:number;bottom?:number;strokeWidth?:number};
/** start/end are seconds within the enclosing source clip. No entrance animation. */
export const Subtitle:React.FC<Props>=({text,start,end,fontSize=48,maxWidth=1320,bottom=64,strokeWidth=3})=>{
 const frame=useCurrentFrame(),{fps}=useVideoConfig();
 if(frame<Math.round(start*fps)||frame>=Math.round(end*fps)||!text.trim())return null;
 return <div data-subtitle="normal" style={{position:'absolute',left:'50%',bottom,transform:'translateX(-50%)',width:'84%',maxWidth,pointerEvents:'none',textAlign:'center',fontFamily:defaults.captions.fontFamily,fontSize,fontWeight:800,lineHeight:1.3,color:'#fff',WebkitTextStroke:`${strokeWidth}px #111`,paintOrder:'stroke fill',textShadow:'0 2px 4px #000',whiteSpace:'pre-wrap',overflowWrap:'break-word'}}>{text}</div>;
};
