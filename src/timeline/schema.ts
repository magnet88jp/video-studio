import {z} from 'zod';

export const effectNames = ['punchZoom','screenShake','flash','monochrome','redAlert','funnyFail','surprise','fail','win','danger','funny'] as const;
export const EventSchema = z.object({
  id: z.string().min(1), start: z.number().finite().nonnegative(), end: z.number().finite().positive(),
  type: z.enum(['cut','speed','caption','effect','se','bgm','overlay','freeze']),
  enabled: z.boolean().default(true), needsReview: z.boolean().default(false),
  scope: z.enum(['main','opening','both']).default('both'),
  effect: z.enum(effectNames).optional(), intensity: z.number().min(0).max(1).default(0.65),
  caption: z.string().optional(), asset: z.string().optional(),
  overlayKind: z.enum(['image','video']).optional(), rate: z.number().min(0.5).max(3).optional(),
  holdSeconds: z.number().positive().max(2).optional(), freezeAt: z.number().nonnegative().optional(),
  volume: z.number().min(0).max(1).optional(), loop: z.boolean().default(false),
  position: z.enum(['bottom','center','top','top-left']).default('bottom'),
  fontSize: z.number().min(16).max(180).optional(), color: z.string().optional(),
  rotation: z.number().min(-45).max(45).default(0), scale: z.number().min(0.1).max(3).default(1),
  stroke: z.number().min(0).max(12).optional(), shadow: z.string().optional(),
  entrance: z.enum(['pop','slide','fade','none']).default('pop'), exit: z.enum(['fade','none']).default('fade'),
  widthPercent: z.number().min(1).max(100).default(30), opacity: z.number().min(0).max(1).default(1),
  reason: z.string().optional(), evidence: z.record(z.string(),z.unknown()).optional()
}).strict().superRefine((e,ctx)=>{
  if(e.end<=e.start) ctx.addIssue({code:'custom',message:'end must be after start'});
  if(e.type==='speed' && e.rate===undefined)ctx.addIssue({code:'custom',message:'speed requires rate'});
  if(e.type==='effect' && !e.effect)ctx.addIssue({code:'custom',message:'effect requires effect name'});
  if(e.type==='caption' && !e.caption?.trim())ctx.addIssue({code:'custom',message:'caption requires text'});
  if(['se','bgm','overlay'].includes(e.type) && !e.asset)ctx.addIssue({code:'custom',message:'media event requires asset'});
});
export const PlanSchema = z.object({
  version:z.literal(1), source:z.string().min(1), sourceHash:z.string().optional(),
  sourceDuration:z.number().positive(),
  settings:z.object({width:z.number().int().positive(),height:z.number().int().positive(),fps:z.number().positive().max(120)}),
  digest:z.object({enabled:z.boolean(),clips:z.array(z.object({start:z.number().nonnegative(),end:z.number().positive()})).max(3)}),
  events:z.array(EventSchema), notes:z.array(z.string()).default([])
}).strict().superRefine((p,ctx)=>{
  const ids=new Set<string>();
  for(const e of p.events){
    if(ids.has(e.id))ctx.addIssue({code:'custom',message:`Duplicate event id ${e.id}`});ids.add(e.id);
    if(e.end>p.sourceDuration+.001)ctx.addIssue({code:'custom',message:`Event ${e.id} exceeds source`});
    if(e.freezeAt!==undefined && e.freezeAt>=p.sourceDuration)ctx.addIssue({code:'custom',message:'freezeAt exceeds source'});
  }
  const structural=p.events.filter(e=>e.enabled&&['cut','speed','freeze'].includes(e.type)).sort((a,b)=>a.start-b.start);
  for(let i=1;i<structural.length;i++)if(structural[i].start<structural[i-1].end)ctx.addIssue({code:'custom',message:'Enabled cut/speed/freeze intervals must not overlap'});
  const d=p.digest.clips.reduce((s,c)=>s+c.end-c.start,0);
  if(p.digest.enabled && (d<5||d>8))ctx.addIssue({code:'custom',message:'Enabled digest must total 5–8 seconds'});
  if(p.digest.clips.some(c=>c.end<=c.start||c.end>p.sourceDuration))ctx.addIssue({code:'custom',message:'Invalid digest range'});
});
export type EditEvent=z.infer<typeof EventSchema>;
export type EditPlan=z.infer<typeof PlanSchema>;
export type EditorConfig={style:string;strength:number;effects:Record<string,number>;bgmVolume:number;reactionBgmMultiplier:number};
export type MediaAsset={url:string;duration?:number;kind?:string};
export const TranscriptSchema=z.array(z.object({start:z.number().finite().nonnegative(),end:z.number().finite().positive(),text:z.string().trim().min(1)}).refine(row=>row.start<row.end,'Subtitle end must be after start'));
export type Transcript=z.infer<typeof TranscriptSchema>;
export type EditorProps={transcript?:Transcript;plan:EditPlan; media:Record<string,MediaAsset>; config:EditorConfig};
