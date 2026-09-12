import React from 'react';
import {AbsoluteFill,Img,staticFile} from 'remotion';
import {Video} from '@remotion/media';
import type {EditEvent,MediaAsset} from '../../timeline/schema';
export const MediaOverlay:React.FC<{event:EditEvent;asset:MediaAsset}>=({event:e,asset})=>{
 const style={width:`${e.widthPercent}%`,maxHeight:'75%',objectFit:'contain' as const};
 return <AbsoluteFill style={{padding:'6%',alignItems:e.position==='top-left'?'flex-start':'center',justifyContent:e.position==='bottom'?'flex-end':e.position==='center'?'center':'flex-start',opacity:e.opacity,pointerEvents:'none'}}>{e.overlayKind==='video'?<Video src={staticFile(asset.url)} muted loop={e.loop} objectFit="contain" style={{width:style.width,maxHeight:style.maxHeight}}/>:<Img src={staticFile(asset.url)} style={style}/>}</AbsoluteFill>;
};
