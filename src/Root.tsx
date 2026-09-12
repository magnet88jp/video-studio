import React from 'react';
import {Composition,getRemotionEnvironment} from 'remotion';
import livePlan from '../work/edit_plan.json';
import {PlanSchema} from './timeline/schema';
import {GameVideo} from './compositions/GameVideo';
import {DemoVideo} from './compositions/DemoVideo';
import {compileTimeline} from './timeline/compile';
import type {EditorProps} from './timeline/schema';
const empty:EditorProps={plan:{version:1,source:'input/gameplay.mp4',sourceDuration:30,settings:{width:1920,height:1080,fps:60},events:[],digest:{enabled:false,clips:[]},notes:[]},media:{},config:{style:'energetic',strength:.82,effects:{},bgmVolume:.045,reactionBgmMultiplier:.3}};
const currentPlan=(props:EditorProps)=>getRemotionEnvironment().isStudio?PlanSchema.parse(livePlan):props.plan;
const StudioGameVideo:React.FC<EditorProps>=props=><GameVideo {...props} plan={currentPlan(props)}/>;
export const RemotionRoot:React.FC=()=> <>
 <Composition id="GameVideo" component={StudioGameVideo} width={1920} height={1080} fps={60} durationInFrames={1800} defaultProps={empty} calculateMetadata={({props})=>({durationInFrames:compileTimeline(currentPlan(props)).durationInFrames,...currentPlan(props).settings})}/>
 <Composition id="DemoVideo" component={DemoVideo} width={1920} height={1080} fps={60} durationInFrames={1800} defaultProps={empty} calculateMetadata={({props})=>({durationInFrames:Math.round(Math.min(30,props.plan.sourceDuration)*props.plan.settings.fps),...props.plan.settings})}/>
 </>;
