#!/usr/bin/env python3
"""Local transcription only. python scripts/transcribe.py input/gameplay.mp4

Defaults: small / ja / full duration. --duration 30 is a partial smoke test.
Whisper word boundaries are preferred; an indivisible long word is not cut.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
OUTPUT = WORK / 'transcript.json'
AUDIO = WORK / 'audio/commentary.wav'
META = WORK / 'transcribe_cache.json'


def load(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, data):
    # Atomic replacement leaves the previous result intact on failure.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def run(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed: {result.stderr.strip()[-600:]}')
    return result.stdout


def valid(rows):
    return isinstance(rows, list) and all(
        isinstance(row, dict) and isinstance(row.get('start'), (int, float))
        and isinstance(row.get('end'), (int, float))
        and 0 <= row['start'] < row['end']
        and isinstance(row.get('text'), str) and row['text'].strip()
        for row in rows)


def suspicious(segment):
    text = re.sub(r'\s+', '', segment.text)
    # Do not discard normal stutters, fillers or a short repeated reaction.
    repeated = bool(re.search(r'(.{2,15}?)\1{5,}', text))
    return (segment.no_speech_prob > .7 and segment.avg_logprob < -.6) or (
        segment.avg_logprob < -1.2 and (segment.compression_ratio > 2.8 or repeated))


def captions(segment, offset, limit):
    words = [(w.word, offset + w.start, offset + w.end) for w in (segment.words or []) if w.word.strip()]
    if not words:
        # Fallback retains lexical runs and uses proportional timestamps.
        text = segment.text.strip()
        tokens = re.findall(r'[A-Za-z0-9_\-\']+|[^A-Za-z0-9_\-\']+?(?:[、。！？!?]|$)', text)
        if not tokens:
            tokens = [text]
        cursor = offset + segment.start
        for token in tokens:
            end = cursor + (segment.end - segment.start) * len(token) / max(1, len(text))
            words.append((token, cursor, end))
            cursor = end
    rows, group = [], []

    def emit():
        if not group:
            return
        text = ''.join(w[0] for w in group).strip()
        start, end = round(max(0, group[0][1]), 3), round(min(limit, group[-1][2]), 3)
        if text and start < end:
            rows.append({'start': start, 'end': end, 'text': text})
        group.clear()

    for word in words:
        existing = ''.join(w[0] for w in group)
        if group and (len(existing + word[0]) > 35 or word[1] - group[-1][2] > .8):
            emit()
        group.append(word)
        text = ''.join(w[0] for w in group).strip()
        if len(text) >= 10 and re.search(r'[。！？!?、,]$', text):
            emit()
        elif len(text) >= 25 and re.search(r'(です|ます|でした|ました|けど|から|ので|って|ね|よ|が|を|に|で|と)$', text):
            emit()
    emit()
    return rows


def main():
    parser = argparse.ArgumentParser(description='ローカルWhisperで日本語実況を文字起こしし、work/transcript.jsonへ保存します。')
    parser.add_argument('input', nargs='?', help='input/内の動画。省略時はMP4を名前順で選択')
    parser.add_argument('--model', default='small', help='tiny/base/small/medium、または既存モデルのローカルディレクトリ (default: small)')
    parser.add_argument('--language', default='ja', help='認識言語 (default: ja)')
    parser.add_argument('--duration', type=float, help='冒頭N秒だけの動作確認。省略時は全音声')
    parser.add_argument('--force', action='store_true', help='文字起こし結果のキャッシュを使わない')
    parser.add_argument('--local-files-only', action='store_true', help='モデルをダウンロードせずローカルキャッシュだけ使う')
    args = parser.parse_args()
    if args.duration is not None and not 0 < args.duration < float('inf'):
        raise ValueError('--duration は正の有限秒数にしてください。')
    candidates = sorted((ROOT / 'input').glob('*'))
    candidates = [p for p in candidates if p.is_file() and p.suffix.lower() == '.mp4']
    source = Path(args.input).expanduser().resolve() if args.input else (candidates[0].resolve() if candidates else None)
    if source is None or not source.is_file():
        raise ValueError('入力動画が存在しません。python scripts/transcribe.py input/動画名.mp4 を指定してください。')
    if not source.is_relative_to((ROOT / 'input').resolve()):
        raise ValueError('入力動画はこのプロジェクトの input/ 内を指定してください。')
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            raise RuntimeError(f'{tool} が見つかりません。インストールとPATHを確認してください。')
    if importlib.util.find_spec('faster_whisper') is None:
        venv_python = ROOT / 'work/analysis-venv/bin/python'
        if venv_python.exists() and Path(sys.prefix).resolve() != venv_python.parent.parent.resolve():
            os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])
        raise RuntimeError('faster-whisper がありません。既存仮想環境で pip install faster-whisper を実行してください。')
    try:
        WORK.mkdir(parents=True, exist_ok=True)
        AUDIO.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise RuntimeError(f'出力ディレクトリを作成できません: {error}') from None
    before = sha256(source)
    stat = source.stat()
    identity = {'path': str(source), 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'sha256': before}
    model_path = Path(args.model).expanduser()
    model_identity = str(model_path.resolve()) if model_path.is_dir() else args.model
    key = {'version': 1, 'source': identity, 'model': model_identity, 'language': args.language, 'duration': args.duration}
    cache = load(META) or {}
    print('[1/3] Extracting audio...', flush=True)
    audio_meta_path = WORK / 'audio/transcribe_source.json'
    audio_meta = load(audio_meta_path) or {}
    legacy_meta = load(WORK / 'analysis/audio_meta.json') or {}
    reuse = False
    trusted_meta = audio_meta if audio_meta else legacy_meta
    if AUDIO.exists() and trusted_meta.get('sourceHash') == before:
        with wave.open(str(AUDIO)) as audio:
            reuse = audio.getframerate() == 16000 and audio.getnchannels() == 1 and audio.getsampwidth() == 2
        if audio_meta.get('sourceHash') == before:
            reuse = reuse and audio_meta.get('audioHash') == sha256(AUDIO)
    if not reuse:
        probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(source)]))
        if not any(s['codec_type'] == 'audio' for s in probe['streams']):
            raise ValueError('入力動画に音声トラックがありません。')
        temporary = AUDIO.with_name('commentary.transcribing.wav')
        run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(source), '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(temporary)])
        temporary.replace(AUDIO)
    else:
        print('  同一入力の16kHz mono音声を再利用します。', flush=True)
    save(audio_meta_path, {'sourceHash': before, 'audioHash': sha256(AUDIO)})
    print('[2/3] Transcribing...', flush=True)
    rows = load(OUTPUT)
    if not args.force and cache.get('key') == key and valid(rows) and cache.get('outputHash') == sha256(OUTPUT):
        print('  キャッシュを再利用します。', flush=True)
    else:
        from faster_whisper import WhisperModel
        import numpy as np
        try:
            model = WhisperModel(model_identity, device='cpu', compute_type='int8', cpu_threads=6,
                                 download_root=str(WORK / 'model-cache'), local_files_only=args.local_files_only)
        except Exception as error:
            raise RuntimeError(f'モデル {args.model} をロードできません。初回取得にはネット接続が必要です。既存モデルのパスも指定できます。詳細: {str(error)[:400]}') from None
        with wave.open(str(AUDIO)) as audio:
            frames = audio.getnframes() if args.duration is None else min(audio.getnframes(), round(args.duration * 16000))
            samples = np.frombuffer(audio.readframes(frames), dtype=np.int16).astype(np.float32) / 32768
        limit = len(samples) / 16000
        rows, left, last_progress = [], 0, -1
        while left < len(samples):
            right = min(left + 30 * 16000, len(samples))
            if right < len(samples):
                right = min(range(left + 25 * 16000, right, 1600), key=lambda n: float(np.mean(samples[n:n + 800] ** 2)))
            segments, _ = model.transcribe(samples[left:right], language=args.language, task='transcribe',
                word_timestamps=True, condition_on_previous_text=False, beam_size=5, temperature=0,
                vad_filter=True, vad_parameters={'min_silence_duration_ms': 500})
            for segment in segments:
                if not suspicious(segment):
                    rows.extend(captions(segment, left / 16000, limit))
            left = right
            progress = int(left / max(1, len(samples)) * 4) * 25
            if progress > last_progress:
                print(f'  {progress}% ({left / 16000:.0f}/{limit:.0f}秒)', flush=True)
                last_progress = progress
        if not valid(rows):
            raise RuntimeError('文字起こしの時刻またはテキストが不正なため保存を中止しました。')
    if sha256(source) != before:
        raise RuntimeError('実行中に元動画が変更されました。結果の保存を中止しました。')
    print('[3/3] Writing transcript.json...', flush=True)
    if OUTPUT.exists() and not (WORK / 'transcript.before-dedicated-script.json').exists():
        shutil.copy2(OUTPUT, WORK / 'transcript.before-dedicated-script.json')
    save(OUTPUT, rows)
    save(META, {'key': key, 'outputHash': sha256(OUTPUT), 'sourceUnchanged': True, 'partial': args.duration is not None, 'count': len(rows)})
    label = f'冒頭{args.duration:g}秒の部分結果' if args.duration is not None else '全音声'
    print(f'完了: {OUTPUT} ({len(rows)}字幕、{label})')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n中断しました。元動画は変更していません。', file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f'文字起こしエラー: {error}', file=sys.stderr)
        sys.exit(1)
