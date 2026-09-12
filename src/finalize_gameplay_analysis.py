"""Attach reviewable editorial candidates to the measured evidence; never edit media."""
import json
import re
from pathlib import Path
from analyze_gameplay import WORK, ROOT, read, save, interval, fingerprint

transcript = read('transcript.json')
highlights = read('highlights.json')
highlights['highlights']=[]
for u in transcript['utterances']:
    reasons=[]
    if u['mean_word_probability']<.65 or u['avg_logprob']<-.7:
        reasons.append('ASR confidence below review threshold')
    if re.search(r'(.{1,5})\1{2,}',u['text']):
        reasons.append('Repeated syllables: possible vocalization, effect sound, or ASR repetition')
    if any(w['end']-w['start']>1.5 for w in u['words']):
        reasons.append('Long word alignment: verify utterance boundaries')
    if any(v in u['text'] for v in ['アマキン','キューチ','ボーイナー','こっちば','きそきそ','より食べたい','風呂も入った']):
        reasons.append('Name or contextually uncertain wording flagged during text review; not corrected without listening')
    u['review_reasons']=reasons
    u['needs_review']=bool(reasons)
note='needs_review=falseでも正確性を保証しない。発話に似た効果音や非言語音がテキスト化される場合がある。'
if note not in transcript['limitations']:
    transcript['limitations'].append(note)
save('transcript.json',transcript)
visual_notes={
    1:'184秒では板状オブジェクト、193秒では壁に近い視点を確認。バグ発生の断定は実況の自動認識に基づく候補。',
    2:'235.5秒では板状オブジェクト、238.75秒と241秒では空と灰色のオブジェクトが画面を占め、視点が大きく変わっている。',
    3:'211秒では箱状オブジェクト、215.15秒では黄色い顔のオブジェクトを確認。',
    4:'224.45秒では空を見上げる視点を確認。',
    5:'311.35秒ではゲーム内の警告文、320.95秒ではゲーム紹介画面を確認。画面の切り替わりを伴う候補。',
    6:'59.05秒・62.65秒では黄色い顔と鎖でつながれた灰色のオブジェクトを確認。',
    7:'136秒では広場と動物状オブジェクト、140秒では建物の外側を確認。対象の発見は静止画だけでは確定できない。',
    8:'381.25秒ではおもちゃの選択画面、389秒では複数の車両を確認。'}
selection = json.loads((ROOT/'src/gameplay_highlight_selection.json').read_text())
for choice in selection:
    a,b = choice['start'],choice['end']
    utterances = [u for u in transcript['utterances'] if u['start']<b and u['end']>a]
    peaks = [r for r in highlights['loud_reaction_candidates'] if a<=r['peak_time']<=b]
    strongest = max(peaks,key=lambda r:r['rms_dbfs']) if peaks else None
    highlights['highlights'].append(interval(a,b,id=f"h{choice['priority']:02}",
        priority=choice['priority'],title=choice['title'],reason=choice['reason'],
        selection_basis=choice['basis'],utterance_ids=[u['id'] for u in utterances],
        transcript_excerpt=' / '.join(u['text'] for u in utterances),
        low_confidence_utterance_ids=[u['id'] for u in utterances if u['needs_review']],
        loud_event_ids=[p['id'] for p in peaks],
        strongest_audio_peak=strongest,
        visual_check_sample_times=choice['visual_frames'],
        visual_observation=visual_notes[choice['priority']],
        needs_review=True,review_note='音声の自動認識と音量を基にした候補。試写と発言の聴き直しで採否・境界を決める。'))
highlights['status']='candidate_analysis_complete_not_an_edit_decision_list'
highlights['highlight_count']=len(highlights['highlights'])
highlights['method']['selection']='Transcript context and measured mixed-track loudness, editorial priority 1 is highest; sampled still frames for visual context only'
highlights['method']['minimum_peak_prominence_db']=3
highlights['method']['vocal_candidate_rule']='ASR utterance within +/-0.6s of peak; VAD overlap is recorded separately, no voice isolation'
highlights['review_status']={'full_video_review':False,'manual_audio_verification':False,
    'sampled_still_frames_reviewed':True,'automatic_asr':True}
highlights['loud_event_count']=len(highlights['loud_reaction_candidates'])
highlights['possible_vocal_reaction_count']=sum(r['classification']=='possible_vocal_reaction' for r in highlights['loud_reaction_candidates'])
save('highlights.json',highlights)

silence=read('silence.json')
checks=[]
for name,groups in [('transcript',[transcript['utterances']]),
                    ('silence',[silence['no_speech_intervals'],silence['acoustic_silence_intervals']]),
                    ('highlights',[highlights['loud_reaction_candidates'],highlights['highlights']])]:
    for group in groups:
        for entry in group:
            assert 0<=entry['start']<entry['end']<=transcript['duration_seconds']+.001,(name,entry)
            assert abs(entry['duration']-(entry['end']-entry['start']))<.002
    checks.append(name+': intervals valid')
utterances=transcript['utterances']
assert all(a['start']<=b['start'] for a,b in zip(utterances,utterances[1:]))
for gap in silence['no_speech_intervals']:
    assert not any(u['start']<gap['end'] and u['end']>gap['start'] for u in utterances)
ids={u['id'] for u in utterances}
for h in highlights['highlights']:
    assert set(h['utterance_ids'])<=ids
assert fingerprint()==read('source_before.json')
save('analysis_validation.json',{'passed':True,'checks':checks+['ASR start order valid',
    'No-speech candidates do not overlap transcript','Highlight references valid','Source SHA-256, size and mtime unchanged'],
    'utterance_count':len(utterances),'needs_review_utterance_count':sum(u['needs_review'] for u in utterances),
    'no_speech_count':len(silence['no_speech_intervals']),
    'no_speech_total_seconds':silence['no_speech_total_seconds'],
    'acoustic_silence_count':len(silence['acoustic_silence_intervals']),
    'highlight_count':len(selection),'loud_event_count':highlights['loud_event_count'],
    'possible_vocal_reaction_count':highlights['possible_vocal_reaction_count']})
print(json.dumps(read('analysis_validation.json'),ensure_ascii=False,indent=2))
