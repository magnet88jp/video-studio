#!/usr/bin/env python3
"""Reuse fixed tools for transcription + analysis + initial plan. Never render."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def main():
    parser=argparse.ArgumentParser(description='編集準備のみ。専用文字起こし→解析→初期プラン。動画は編集しません。')
    parser.add_argument('input',help='input/ 内のMP4')
    parser.add_argument('--model',help='Whisperモデル。省略時は保存済みローカルモデル、なければsmall')
    parser.add_argument('--replan',action='store_true',help='既存プランをバックアップして再生成')
    parser.add_argument('--check',action='store_true',help='対象・モデル・実行予定のみ表示。ファイル変更なし')
    args=parser.parse_args()
    source=(ROOT/args.input).resolve()
    if not source.is_file() or not source.is_relative_to((ROOT/'input').resolve()):
        raise ValueError('input/ 内の既存動画を指定してください。')
    model=args.model
    model_meta=ROOT/'work/model_path.json'
    if not model and model_meta.exists():
        cached=read(model_meta).get('path','')
        if (Path(cached)/'model.bin').is_file():model=cached
    model=model or 'small'
    relative=str(source.relative_to(ROOT))
    commands=[['node','scripts/python.mjs','scripts/transcribe.py',relative,'--model',model],
              ['node','scripts/python.mjs','scripts/analyze_video.py','--input',relative,'--reuse-transcript']]
    plan_path=ROOT/'work/edit_plan.json'
    if plan_path.exists() and not args.replan:
        plan=read(plan_path)
        if not isinstance(plan,dict) or (ROOT/plan.get('source','')).resolve()!=source:
            raise ValueError('別動画または旧形式のプランがあります。--replan でバックアップ後に再生成してください。')
    else:
        commands.append(['node','scripts/python.mjs','scripts/build_edit_plan.py','--input',relative])
    if args.check:
        print(json.dumps({'input':relative,'model':model,'commands':commands,'preserveExistingPlan':len(commands)==2},ensure_ascii=False,indent=2));return
    for command in commands:
        subprocess.run(command,cwd=ROOT,check=True)
    # Compact review material avoids loading whole transcripts into agent context.
    work=ROOT/'work';analysis=work/'analysis'
    info=read(analysis/'video_info.json');transcript=read(work/'transcript.json')
    brief={'source':relative,'sourceHash':info['sha256'],'duration':info['duration'],
           'transcriptCount':len(transcript),'silenceCandidates':len(read(analysis/'silence.json')),
           'highlights':read(analysis/'highlights.json')[:8],
           'assets':{kind:[str(p.relative_to(ROOT)) for p in (ROOT/'assets'/kind).glob('*') if p.is_file()] for kind in ['se','bgm','images','videos']},
           'planPreserved':len(commands)==2,'next':'Review candidate intervals, update edit_plan.json, preview before rendering. Do not retain unrelated demo events.'}
    (work/'edit_brief.json').write_text(json.dumps(brief,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'準備完了: {len(transcript)}字幕。候補要約: work/edit_brief.json。映像・音声の確認後に編集判断してください。')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        print(f'編集準備エラー: {error}',file=sys.stderr);sys.exit(1)
