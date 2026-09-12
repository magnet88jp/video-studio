"""Read-only gameplay analysis; all times are seconds on the original timeline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
SOURCE = ROOT / 'input/gameplay0307-1.MP4'
AUDIO = WORK / 'gameplay0307-1.analysis.wav'
MODEL = 'deepdml/faster-whisper-large-v3-turbo-ct2'

def save(name, data):
    (WORK / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def read(name):
    return json.loads((WORK / name).read_text())

def fingerprint():
    h = hashlib.sha256()
    with SOURCE.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return {'path': str(SOURCE.relative_to(ROOT)), 'size_bytes': SOURCE.stat().st_size,
            'mtime_ns': SOURCE.stat().st_mtime_ns, 'sha256': h.hexdigest()}

def prepare():
    WORK.mkdir(exist_ok=True)
    save('source_before.json', fingerprint())
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format',
                      '-show_streams', '-of', 'json', str(SOURCE)]))
    save('ffprobe.json', probe)
    if not AUDIO.exists():
        subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'warning', '-n',
                        '-i', str(SOURCE), '-map', '0:a:0', '-vn', '-ac', '1', '-ar',
                        '16000', '-c:a', 'pcm_s16le', str(AUDIO)], check=True)
    print('Prepared audio and ffprobe metadata', flush=True)

def download():
    from huggingface_hub import snapshot_download
    path = snapshot_download(MODEL, cache_dir=str(WORK / 'model-cache'))
    save('model_path.json', {'repository': MODEL, 'path': path})
    print(path, flush=True)

def transcribe():
    from faster_whisper import WhisperModel
    model = WhisperModel(read('model_path.json')['path'], device='cpu',
                         compute_type='int8', cpu_threads=8)
    segments, info = model.transcribe(str(AUDIO), language='ja', beam_size=5,
        word_timestamps=True, vad_filter=True, condition_on_previous_text=False,
        vad_parameters={'threshold': 0.5, 'min_silence_duration_ms': 400,
                        'speech_pad_ms': 200}, hallucination_silence_threshold=2.0)
    result = []
    for s in segments:
        data = s._asdict()
        data['words'] = [w._asdict() for w in s.words or []]
        result.append(data)
        save('whisper_raw.json', {'complete': False, 'segments': result})
        print(f'{s.start:7.2f} - {s.end:7.2f} {s.text}', flush=True)
    save('whisper_raw.json', {'complete': True, 'model': MODEL, 'language': info.language,
         'duration': info.duration, 'segments': result})

def transcribe_bounded():
    """Avoid stitching unrelated speech over long VAD gaps; decode <=30s windows."""
    import dataclasses
    import numpy as np
    from scipy.io import wavfile
    from faster_whisper import WhisperModel
    sr, pcm = wavfile.read(AUDIO)
    audio = pcm.astype(np.float32)/32768
    model = WhisperModel(read('model_path.json')['path'], device='cpu', compute_type='int8', cpu_threads=8)
    if not (WORK/'whisper_first_pass.json').exists():
        save('whisper_first_pass.json', read('whisper_raw.json'))
    bounds, start = [0], 0
    while len(audio)-start > 30*sr:
        # Place each boundary in the quietest 100ms in the last five seconds.
        lo = start+25*sr
        energy = np.mean(audio[lo:start+30*sr].reshape(50,1600)**2,axis=1)
        end = lo+int(np.argmin(energy))*1600+800
        bounds.append(end)
        start = end
    bounds.append(len(audio))
    result = []
    for left, right in zip(bounds, bounds[1:]):
        segments, _ = model.transcribe(audio[left:right], language='ja', beam_size=5,
            word_timestamps=True, vad_filter=False, condition_on_previous_text=False,
            hallucination_silence_threshold=1.0)
        for s in segments:
            d = dataclasses.asdict(s)
            d['id'] = len(result)
            d['start'] += left/sr
            d['end'] += left/sr
            d['decode_window'] = [left/sr,right/sr]
            for w in d['words'] or []:
                w['start'] += left/sr
                w['end'] += left/sr
            result.append(d)
            print(f"{d['start']:7.2f} - {d['end']:7.2f} {d['text']}", flush=True)
        save('whisper_raw.json', {'complete': False, 'segments': result})
    save('whisper_raw.json', {'complete': True, 'model': MODEL, 'language': 'ja',
        'duration': len(audio)/sr, 'decoding': 'independent <=30s windows, boundaries at low RMS, no VAD concatenation',
        'window_boundaries': [b/sr for b in bounds], 'segments': result})

def timecode(t):
    ms = round(t * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'

def interval(a, b, **kw):
    return {'start': round(a, 3), 'end': round(b, 3), 'duration': round(b-a, 3),
            'start_timecode': timecode(a), 'end_timecode': timecode(b), **kw}

def analyze():
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import butter, sosfilt, find_peaks
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    sr, pcm = wavfile.read(AUDIO)
    audio = pcm.astype(np.float32) / 32768
    duration = float(read('ffprobe.json')['format']['duration'])
    audio_end = len(audio)/sr
    raw = read('whisper_raw.json')
    assert raw['complete']
    common = {'schema_version': '1.0', 'source': read('source_before.json'),
              'timebase': 'seconds_from_original_video_start', 'duration_seconds': duration}
    utterances = []
    for s in raw['segments']:
        # Keep ASR text intact; split at actual word gaps and sentence punctuation.
        groups, current = [], []
        for w in s['words']:
            if current and w['start']-current[-1]['end'] >= 1.2:
                groups.append(current)
                current = []
            current.append(w)
            if w['word'].rstrip().endswith(('。', '！', '？', '!', '?')):
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        if not groups:
            groups = [[{'start': s['start'], 'end': s['end'], 'word': s['text'], 'probability': 0}]]
        for words in groups:
            a, b = words[0]['start'], words[-1]['end']
            if b <= a:
                continue
            prob = float(np.mean([w['probability'] for w in words]))
            utterances.append(interval(a, b, id=f'u{len(utterances)+1:04}',
                text=''.join(w['word'] for w in words).strip(), speaker='unidentified',
                asr_segment_id=s['id'], mean_word_probability=round(prob, 4),
                avg_logprob=s['avg_logprob'], no_speech_probability=s['no_speech_prob'],
                needs_review=prob < 0.65 or s['avg_logprob'] < -0.7,
                words=words))
    save('transcript.json', {**common, 'language': 'ja', 'model': MODEL,
        'method': 'faster-whisper CPU int8, beam_size=5, independent <=30s windows without VAD concatenation, word timestamps; split on punctuation or >=1.2s word gap',
        'status': 'automatic_transcription_not_manually_audio_verified',
        'limitations': ['単一の混合音声。実況者とゲーム内音声の話者分離は未実施。',
                       '日本語の固有名詞・叫び声・効果音に重なる発言は誤認識の可能性。',
                       '時刻は自動推定。要確認箇所はneeds_review=true。'],
        'utterance_count': len(utterances), 'utterances': utterances})
    vad = get_speech_timestamps(audio, VadOptions(threshold=0.5,
        min_speech_duration_ms=150, min_silence_duration_ms=300, speech_pad_ms=100), sampling_rate=sr)
    speech = [interval(v['start']/sr, v['end']/sr) for v in vad]
    # Conservative no-speech candidates: both VAD and ASR must be absent.
    # VAD alone misses short, breathy/high-pitched commentary in this recording.
    combined = [(s['start'], s['end']) for s in speech]
    combined += [(max(0,u['start']-.15),min(audio_end,u['end']+.15)) for u in utterances]
    merged = []
    for a,b in sorted(combined):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1],b)
        else:
            merged.append([a,b])
    gaps, prev = [], 0.
    for a,b in merged:
        if a-prev >= 0.6:
            gaps.append(interval(prev, a, kind='no_detected_speech'))
        prev = b
    if audio_end-prev >= 0.6:
        gaps.append(interval(prev, audio_end, kind='no_detected_speech'))
    # ffmpeg acoustic silence is a separate measurement of the mixed track.
    p = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-i', str(AUDIO),
        '-af', 'silencedetect=noise=-40dB:d=0.5', '-f', 'null', '-'], capture_output=True, text=True, check=True)
    (WORK/'silencedetect.log').write_text(p.stderr)
    import re
    quiet, start = [], None
    for line in p.stderr.splitlines():
        m = re.search(r'silence_start: ([\d.]+)', line)
        if m:
            start = float(m[1])
        m = re.search(r'silence_end: ([\d.]+)', line)
        if m and start is not None:
            quiet.append(interval(start, min(float(m[1]), audio_end), kind='acoustic_silence'))
            start = None
    if start is not None:
        quiet.append(interval(start, audio_end, kind='acoustic_silence'))
    for gap in gaps:
        overlap = [u['id'] for u in utterances if u['start'] < gap['end'] and u['end'] > gap['start']]
        gap['asr_overlap_utterance_ids'] = overlap
        gap['needs_review'] = bool(overlap)
    save('silence.json', {**common, 'analyzed_audio_end': audio_end,
        'method': {'speech_detector': 'Silero VAD bundled with faster-whisper',
                   'no_speech_rule': 'complement of union of VAD speech and all ASR utterances; ASR padded +/-0.15s',
                   'vad_threshold': 0.5, 'minimum_no_speech_seconds': 0.6,
                   'speech_padding_seconds': 0.1, 'acoustic_threshold_dbfs': -40,
                   'minimum_acoustic_silence_seconds': 0.5},
        'limitations': ['無言候補にもゲーム音・BGMが残る場合がある。',
                       'VADは話者を区別しない。ASRとの重複は要確認。'],
        'no_speech_count': len(gaps), 'no_speech_total_seconds': round(sum(g['duration'] for g in gaps), 3),
        'no_speech_intervals': gaps, 'acoustic_silence_intervals': quiet,
        'vad_speech_intervals': speech,
        'combined_speech_evidence_intervals': [interval(a,b) for a,b in merged]})
    # 100ms RMS, and 200-4000Hz band energy as a speech-oriented proxy, not separation.
    hop = 1600
    n = len(audio)//hop
    blocks = audio[:n*hop].reshape(n, hop)
    db = 20*np.log10(np.maximum(np.sqrt(np.mean(blocks**2, axis=1)), 1e-9))
    peak = 20*np.log10(np.maximum(np.max(np.abs(blocks), axis=1), 1e-9))
    band = sosfilt(butter(4, [200, 4000], btype='bandpass', fs=sr, output='sos'), audio)
    bdb = 20*np.log10(np.maximum(np.sqrt(np.mean(band[:n*hop].reshape(n,hop)**2,axis=1)),1e-9))
    baseline = np.array([np.percentile(db[max(0,i-50):min(n,i+51)], 30) for i in range(n)])
    rise = db-baseline
    threshold = float(np.percentile(db, 85))
    indexes, _ = find_peaks(db, height=threshold, distance=20, prominence=3)
    loud = []
    for i in indexes:
        if rise[i] < 4:
            continue
        t = i*.1+.05
        nearby = [u for u in utterances if u['start'] <= t+0.6 and u['end'] >= t-0.6]
        vad_overlap = any(s['start'] <= t+.2 and s['end'] >= t-.2 for s in speech)
        loud.append(interval(max(0,t-.5), min(audio_end,t+.7), id=f'r{len(loud)+1:03}',
            peak_time=round(t,3), rms_dbfs=round(float(db[i]),2), peak_dbfs=round(float(peak[i]),2),
            local_rise_db=round(float(rise[i]),2), speech_band_rms_dbfs=round(float(bdb[i]),2),
            speech_detected=vad_overlap, utterance_ids=[u['id'] for u in nearby],
            text=' / '.join(u['text'] for u in nearby),
            classification='possible_vocal_reaction' if nearby else 'mixed_audio_peak',
            needs_review=True))
    save('audio_metrics.json', {'window_seconds': .1, 'rms_dbfs_percentiles':
        {str(p): round(float(np.percentile(db,p)),2) for p in [10,30,50,75,85,90,95,99]},
        'loudness_threshold_dbfs': threshold, 'loud_events': loud})
    save('highlights.json', {**common, 'status': 'audio_candidates_pending_context_review',
        'method': {'rms_window_seconds': .1, 'loudness_percentile': 85,
                   'loudness_threshold_dbfs': threshold, 'minimum_local_rise_db': 4,
                   'local_baseline': '30th percentile within +/-5 seconds',
                   'minimum_peak_spacing_seconds': 2},
        'limitations': ['音量は混合トラックの測定値。大音量の効果音を実況の叫びと断定しない。',
                       '候補は編集前の確認用。自動カットや動画編集は実施していない。'],
        'loud_reaction_candidates': loud, 'highlights': []})
    after = fingerprint()
    assert after == read('source_before.json'), 'Source changed!'
    save('source_verification.json', {'unchanged': True, 'before': read('source_before.json'), 'after': after})
    print(json.dumps({'utterances': len(utterances), 'no_speech': len(gaps),
                      'acoustic_silence': len(quiet), 'loud_events': len(loud)}), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'download', 'transcribe', 'transcribe_bounded', 'analyze'])
    args = parser.parse_args()
    globals()[args.stage]()
