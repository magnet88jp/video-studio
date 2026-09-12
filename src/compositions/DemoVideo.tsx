import React from 'react';
import {AbsoluteFill,Sequence,staticFile} from 'remotion';
import {Video} from '@remotion/media';
import {ImpactCaption} from '../components/captions/ImpactCaption';
import {PunchZoom,ScreenShake,Flash} from '../components/effects/primitives';
import type {EditorProps} from '../timeline/schema';

// Minimal 30-second milestone; full timeline composition replaces this after demo verification.
export const DemoVideo:React.FC<EditorProps>=({plan,media})=>{
 const fps=plan.settings.fps;const src=staticFile(media[plan.source].url);
 return <AbsoluteFill style={{background:'#111318',overflow:'hidden'}}>
   <Video src={src} style={{width:'100%',height:'100%'}} objectFit="contain"/>
   <Sequence from={Math.round(3*fps)} durationInFrames={Math.round(3*fps)}><ImpactCaption text="テロップのデモ" durationInFrames={3*fps}/></Sequence>
   <Sequence from={Math.round(9*fps)} durationInFrames={Math.round(.5*fps)}>
    <PunchZoom intensity={.8}><Video muted src={src} trimBefore={Math.round(9*fps)} style={{width:'100%',height:'100%'}} objectFit="contain"/></PunchZoom>
   </Sequence>
   <Sequence from={Math.round(15*fps)} durationInFrames={Math.round(.6*fps)}>
    <ScreenShake intensity={.6}><Video muted src={src} trimBefore={Math.round(15*fps)} style={{width:'100%',height:'100%'}} objectFit="contain"/></ScreenShake>
   </Sequence>
   <Sequence from={Math.round(21*fps)} durationInFrames={Math.round(.15*fps)}><Flash intensity={.5}/></Sequence>
 </AbsoluteFill>;
};
