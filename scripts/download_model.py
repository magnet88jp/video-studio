#!/usr/bin/env python3
"""Explicit opt-in download: model files only; no user media is uploaded."""
import json
from pathlib import Path
from huggingface_hub import snapshot_download
ROOT=Path(__file__).resolve().parents[1]
repository=json.loads((ROOT/'config/editing.json').read_text())['whisperModel']
p=snapshot_download(repository,cache_dir=str(ROOT/'work/model-cache'))
(ROOT/'work/model_path.json').write_text(json.dumps({'repository':repository,'path':p},indent=2)+'\n')
print(p)
