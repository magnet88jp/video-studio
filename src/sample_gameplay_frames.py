"""Extract only still frames for candidate review; do not encode a video."""
import json
import subprocess
from analyze_gameplay import ROOT, WORK, SOURCE, save

selection=json.loads((ROOT/'src/gameplay_highlight_selection.json').read_text())
times=sorted({t for h in selection for t in h['visual_frames']})
folder=WORK/'gameplay_review_frames'
folder.mkdir(exist_ok=True)
for i,t in enumerate(times):
    subprocess.run(['ffmpeg','-hide_banner','-v','error','-nostdin','-y','-ss',str(t),
        '-i',str(SOURCE),'-frames:v','1','-vf','scale=410:-1',str(folder/f'{i:02}.jpg')],check=True)
subprocess.run(['ffmpeg','-hide_banner','-v','error','-nostdin','-y',
    '-i',str(folder/'%02d.jpg'),'-vf',f'tile=4x{(len(times)+3)//4}:nb_frames={len(times)}',
    '-frames:v','1',str(WORK/'gameplay_highlights_contact.jpg')],check=True)
save('gameplay_frame_index.json',{'order':'left to right, top to bottom','times':times})
print(times)
