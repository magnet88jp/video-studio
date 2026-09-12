import React from 'react';
import {AbsoluteFill,Easing,Freeze,interpolate,useCurrentFrame,useVideoConfig} from 'remotion';
import effects from '../../../config/effects.json';
export const clamp=(n:number)=>Math.max(0,Math.min(1,n));
export const punchScale=(frame:number,fps:number,intensity:number)=>interpolate(frame,[0,.09*fps,.22*fps,effects.punchZoom.durationSeconds*fps],[1,1+(effects.punchZoom.maxScale-1)*clamp(intensity),1+.15*clamp(intensity),1],{easing:Easing.out(Easing.cubic),extrapolateLeft:'clamp',extrapolateRight:'clamp'});
export const shakeOffset=(frame:number,fps:number,intensity:number)=>{
 const amp=(intensity<=0?0:effects.shake.minPixels+(effects.shake.maxPixels-effects.shake.minPixels)*clamp(intensity))*Math.exp(-Math.max(0,frame)/fps*6);
 return {x:Math.sin(frame*2.31)*amp,y:Math.sin(frame*3.47+1)*amp*.7,padding:24};
};
export const PunchZoom:React.FC<React.PropsWithChildren<{intensity:number;frame?:number}>>=({children,intensity,frame})=>{
 const current=useCurrentFrame();const f=frame??current;const {fps}=useVideoConfig();return <AbsoluteFill style={{transform:`scale(${punchScale(f,fps,intensity)})`,transformOrigin:'50% 20%'}}>{children}</AbsoluteFill>;
};
export const ScreenShake:React.FC<React.PropsWithChildren<{intensity:number;frame?:number}>>=({children,intensity,frame})=>{
 const current=useCurrentFrame();const f=frame??current;const {fps,width,height}=useVideoConfig();const s=shakeOffset(f,fps,intensity);
 return <AbsoluteFill style={{transform:`translate(${s.x}px,${s.y}px) scale(${1+48/Math.min(width,height)})`}}>{children}</AbsoluteFill>;
};
export const Flash:React.FC<{intensity:number;frame?:number}>=({intensity,frame})=>{
 const current=useCurrentFrame();const f=frame??current;const {fps}=useVideoConfig();const opacity=effects.flash.maxOpacity*clamp(intensity)*Math.max(0,1-f/(fps*effects.flash.durationSeconds));
 return <AbsoluteFill style={{background:'white',opacity,pointerEvents:'none'}}/>;
};
export const FreezeFrame:React.FC<React.PropsWithChildren<{frame?:number;active?:boolean}>>=({children,frame=0,active=true})=><Freeze frame={frame} active={active}>{children}</Freeze>;
export const Monochrome:React.FC<React.PropsWithChildren<{intensity:number;frame?:number}>>=({children,intensity,frame})=><AbsoluteFill style={{filter:`grayscale(${clamp(intensity)})`}}>{children}</AbsoluteFill>;
export const RedAlert:React.FC<{intensity:number;frame?:number}>=({intensity,frame})=>{
 const current=useCurrentFrame();const f=frame??current;const {fps}=useVideoConfig();return <AbsoluteFill style={{pointerEvents:'none',background:`radial-gradient(ellipse,transparent 48%,rgba(240,30,40,${effects.redAlert.maxOpacity*clamp(intensity)*(.8+.2*Math.sin(f/fps*8))}) 100%)`}}/>;
};
