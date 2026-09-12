"""Numerically verify preserved voice timing after the FFmpeg edit (no ASR claim)."""
import json
from pathlib import Path
import subprocess
import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate

ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'work/final_edit'
r=json.loads((W/'resolved_plan.json').read_text())
decoded=W/'final_audio_check.wav'
subprocess.run(['ffmpeg','-hide_banner','-v','error','-nostdin','-y','-i',str(ROOT/'outputs/final.mp4'),
    '-map','0:a:0','-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(decoded)],check=True)
sr,source=wavfile.read(ROOT/'work/gameplay0307-1.analysis.wav')
sr2,output=wavfile.read(decoded);assert sr==sr2==16000
source=source.astype(np.float64)/32768;output=output.astype(np.float64)/32768
results=[]
for t,length in [(5.0,1.6),(31.1,1.5),(58.7,1.2),(143.,1.2),(192.,1.),
                 (238.15,1.1),(322.65,1.2),(367.,1.5),(474.9,.8)]:
    for c in r['clips']:
        if c['rate']!=1 or not c['start']<=t<t+length<=c['end']:continue
        out_t=c['output_start']+t-c['start']
        x=source[round(t*sr):round((t+length)*sr)]
        start=round((out_t-.2)*sr)
        y=output[start:round((out_t+length+.2)*sr)]
        x=x-x.mean()
        corr=correlate(y,x,mode='valid',method='fft')
        cumulative=np.concatenate(([0.],np.cumsum(y*y)))
        norms=np.sqrt(np.maximum((cumulative[len(x):]-cumulative[:-len(x)])*np.sum(x*x),1e-20))
        coeff=corr/norms
        k=int(np.argmax(coeff));best=float(coeff[k])
        offset=(start+k)/sr-out_t
        results.append({'clip':c['id'],'source_time':t,'output_time':round(out_t,6),
                        'correlation':round(best,5),'offset_ms':round(offset*1000,3)})
report={'passed':all(x['correlation']>.85 and abs(x['offset_ms'])<50 for x in results),
        'method':'Cross-correlation of original and rendered mono 16kHz waveforms at preserved speech locations; ±200ms search',
        'checks':results,'max_abs_offset_ms':max(abs(x['offset_ms']) for x in results),
        'output_mono_sample_peak_dbfs':round(20*np.log10(max(np.abs(output))),3),
        'output_audio_seconds':len(output)/sr}
(W/'audio_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
assert report['passed'],'Audio timing mismatch'
