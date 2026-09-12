import React from 'react';
import {Video} from '@remotion/media';
// Audio is rendered separately using FFmpeg atempo to preserve pitch.
export const SlowMotion:React.FC<React.ComponentProps<typeof Video>>=p=><Video {...p} muted playbackRate={p.playbackRate??.7}/>;
export const SpeedUp:React.FC<React.ComponentProps<typeof Video>>=p=><Video {...p} muted playbackRate={p.playbackRate??2}/>;
