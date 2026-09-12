"""Create a reviewable, source-timed edit plan. Does not edit or encode any media."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'

def load(name):
    return json.loads((WORK / name).read_text())

def write(name, value):
    (WORK/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

transcript = load('transcript.json')
highlights = load('highlights.json')
silence = load('silence.json')
duration = transcript['duration_seconds']
utterances = transcript['utterances']
u_by_id = {u['id']: u for u in utterances}
peaks = highlights['loud_reaction_candidates']

# Small removals only: leave context and the padded speech edges intact.
cuts = [
    (23.5,27.3,'プレイ開始前後の待ち時間候補。ロード完了・初期画面の説明は残す。'),
    (47.7,49.1,'次の「なんか怖い」につなぐ余白候補。'),
    (51.1,52.4,'短い発言の間の不要な待ち時間候補。'),
    (54.1,56.8,'驚きの直前は残し、待ち時間の中央のみ短縮候補。'),
    (148.0,149.3,'説明の合間の余白候補。'),
    (248.5,252.5,'次の場所へ話題が変わるまでの待ち時間候補。'),
    (265.65,267.2,'電車についての発言の間。接近・出現があれば残す。'),
    (325.0,328.2,'画面切り替え後の待ち時間候補。再開経緯は残す。'),
    (332.3,335.7,'次の実況までの余白候補。'),
    (451.1,454.6,'終盤の短い発言の間の余白候補。'),
    (477.8,duration,'バイバイの後の余韻を約0.53秒残して終了。')
]
# Motion has not been classified from continuous video: every speed item is conditional.
speeds = [
    (65.0,74.0,1.5,'次の試行までの移動・操作待ち候補'),
    (107.0,115.5,1.5,'長い無発話区間の中央。前後の大音量イベントを保護'),
    (160.6,168.0,1.75,'調べるという発言の後。探索・移動のみなら短縮'),
    (270.0,275.8,1.5,'電車への言及後の待ち・移動。電車の到来は通常速度'),
    (283.4,290.5,1.5,'次の「そういくぜ」までの移動候補'),
    (344.0,355.8,2.0,'次の会話までの長い無発話区間。単調な移動のみなら倍速'),
    (400.0,420.5,2.0,'車両を出した後の長い無発話区間。397秒の大音量は通常速度で保護'),
    (424.6,432.5,1.5,'終盤の発言間。移動のみなら軽い倍速'),
    (436.3,443.8,1.5,'終盤の発言間。新しい遊びや状況変化は通常速度'),
    (463.0,468.3,1.5,'461秒の大音量後から締めの挨拶直前まで')
]

changes = sorted([{'start':a,'end':b,'action':'cut','reason':r} for a,b,r in cuts] +
                 [{'start':a,'end':b,'action':'speed','rate':rate,'reason':r} for a,b,rate,r in speeds],
                 key=lambda c:c['start'])
for prev,nxt in zip(changes,changes[1:]):
    assert prev['end']<=nxt['start']
for c in changes:
    assert not any(u['start']<c['end'] and u['end']>c['start'] for u in utterances),c
    assert not any(h['start']<c['end'] and h['end']>c['start'] for h in highlights['highlights']),c
    assert not any(p['rms_dbfs']>=-18 and c['start']<p['end']+.5 and c['end']>p['start']-.5 for p in peaks),c
    gap=next(g for g in silence['no_speech_intervals']
             if g['start']<=c['start'] and (g['end']>=c['end'] or c['end']==duration and g['end']>duration-.02))
    assert gap['duration']>=1.2
    c['silence_evidence']={k:gap[k] for k in ['start','end','duration']}
    c['status']='candidate'
    c['fallback_action']='keep'
    c['needs_review']=True
    if c['action']=='cut':
        c['apply_if']='再生確認で発言・驚き・笑い・重要なゲーム動作がなく、前後のつながりに不要な無言と確認できた場合のみ。'
        c['transition']={'type':'straight_cut','audio_declick_ms':8,
                         'note':'音の接続だけを処理し、発言やリアクションにはフェードをかけない。'}
    else:
        c['apply_if']='再生確認で単調な移動・繰り返し操作のみと確認できた場合。失敗、発見、驚き、笑い、重要なゲーム動作は範囲から除外して通常速度を保つ。'
        c['audio']={'preserve_pitch':True,'gain_db':-3,
                    'speech_or_laughter_policy':'範囲に声や笑いがあれば、その部分の倍速を取り消す。'}
        c['nearby_audio_events']=[p['id'] for p in peaks if c['start']<=p['peak_time']<=c['end']]

hook={'id':'hook01','start':233.0,'end':240.0,'action':'insert_highlight',
      'instance':'opening','layer':'video','output_start':0.0,'output_end':7.0,
      'rate':1.0,'status':'planned','position':'before_main',
      'retain_original_occurrence':True,'source_highlight_ids':['h02'],
      'reason':'状況の前振りから「やば俺が死ぬ」までを7秒で見せる。直後の不確かな発言に入る前で終え、元動画の冒頭へ戻る。',
      'transition_to_main':'straight_cut','needs_review':True,
      'review_note':'直前の状況と発言の音声を確認し、前後を詰め直す場合も5〜8秒・文の途中で切らない条件を保つ。',
      'audio':{'use_original':True,'additional_sfx':False}}

clips=[]
source_cursor=0.0
out_cursor=7.0
for c in changes+[{'start':duration,'end':duration,'action':'sentinel'}]:
    if source_cursor<c['start']:
        clips.append({'start':source_cursor,'end':c['start'],'action':'keep','rate':1.0,
                      'status':'planned','reason':'実況・操作・リアクション・場面のつながりを通常速度で残す。'})
    if c['action']!='sentinel':
        clips.append(c)
    source_cursor=c['end']
for i,c in enumerate(clips):
    c.update(id=f'main{i+1:03}',instance='main',layer='video',output_start=round(out_cursor,3))
    out_cursor+=(c['end']-c['start'])/(c.get('rate',1)) if c['action']!='cut' else 0
    c['output_end']=round(out_cursor,3)
    if c['action']=='keep':
        c['preserve_speech']=True
        c['preserve_nonverbal_reactions']=True
        c['source_highlight_ids']=[h['id'] for h in highlights['highlights'] if h['start']<c['end'] and h['end']>c['start']]

events=[hook]+clips
def add_effect(action,a,b,instance='main',**kw):
    parent=hook if instance=='opening' else next(c for c in clips if c['action']!='cut' and c['start']<=a and b<=c['end'])
    assert parent['start']<=a<b<=parent['end']
    refs=kw.get('utterance_ids',[])
    events.append({'id':f'{action}{len(events):03}','start':a,'end':b,'action':action,
        'instance':instance,'layer':'audio_effect' if action=='sfx' else 'visual_effect',
        'target_clip_id':parent['id'],
        'output_start':round(parent['output_start']+(a-parent['start'])/parent.get('rate',1),3),
        'output_end':round(parent['output_start']+(b-parent['start'])/parent.get('rate',1),3),
        'status':'candidate' if action=='sfx' else 'planned',
        'needs_review':True,
        'transcript_needs_review':any(u_by_id[u]['needs_review'] for u in refs),**kw})

caption_style={'font_size_px_at_720p':42,'font_weight':'bold','color':'#FFFFFF',
               'stroke_color':'#151515','stroke_width_px_at_720p':3,
               'placement':'lower_safe_area_above_game_ui','max_lines':2,
               'animation':'none','respect_game_ui':True}
captions=[
    (18.4,22.66,'さっそくプレイ！',['u0008'],'condensed'),
    (31.01,32.93,'コイン15になってる',['u0012'],'punctuation_only'),
    (58.5,60.5,'声、エグい…',['u0020'],'condensed'),
    (135.57,136.57,'どこいった？',['u0032'],'punctuation_only'),
    (142.87,144.59,'なんか顔違くね？',['u0034'],'punctuation_only'),
    (181.38,183.0,'なんかバグってる',['u0041'],'punctuation_only'),
    (184.66,187.0,'助けて、バグっちゃった！',['u0042'],'condensed'),
    (210.75,212.07,'強すぎ！',['u0054'],'punctuation_only'),
    (238.1,239.6,'やば、俺が死ぬ！',['u0060'],'punctuation_only'),
    (322.5,324.06,'なんかヤバい',['u0075'],'punctuation_only'),
    (387.9,389.62,'いけー！',['u0095'],'punctuation_only'),
    (470.83,475.93,'よろしくお願いします',['u0104'],'punctuation_only')
]
for a,b,text,refs,kind in captions:
    add_effect('caption',a,b,caption=text,utterance_ids=refs,text_type=kind,style=caption_style,
               review_note='表示文は自動文字起こしに基づく案。聴き直して確定し、聞き取れない語は推測で表示しない。')
add_effect('caption',238.1,239.6,instance='opening',caption='やば、俺が死ぬ！',
           utterance_ids=['u0060'],text_type='punctuation_only',style=caption_style,
           review_note='本編と同じ発言・同じ表記を使う。')
add_effect('caption',233.0,234.4,instance='opening',caption='このあと…',utterance_ids=[],
           text_type='editorial_label',style={**caption_style,'font_size_px_at_720p':28,'placement':'top_left_safe_area'},
           review_note='実況の引用ではなく、後半からの先出しであることを示す短い案内。')

for a,b,scale,refs in [(58.5,60.5,1.15,['u0020']),
                        (194.81,197.83,1.2,['u0046']),
                        (210.75,212.15,1.18,['u0054']),
                        (238.1,239.8,1.22,['u0060'])]:
    add_effect('zoom',a,b,scale=scale,utterance_ids=refs,
        framing={'anchor':'gameplay_subject','preserve_hud':True,'fit_mode':'contain_source_before_zoom'},
        animation={'in_seconds':.1,'out_seconds':.12,'shake':False},
        apply_if='実際に強いリアクションと確認でき、重要な操作対象やHUDを隠さない場合。中心を調整しても隠れる場合はズームを省く。')
add_effect('zoom',238.1,239.8,instance='opening',scale=1.22,utterance_ids=['u0060'],
    framing={'anchor':'gameplay_subject','preserve_hud':True,'fit_mode':'contain_source_before_zoom'},
    animation={'in_seconds':.1,'out_seconds':.12,'shake':False},
    apply_if='本編と同じ画角で、重要なゲーム表示が隠れないことを確認する。')

for a,b,sound,refs,note in [
    (63.65,63.85,'soft_fail_pop',['u0021'],'発言の対象の失敗・倒れる瞬間が映像で確認できた場合だけ、発言直後に小さく1回。'),
    (183.25,183.45,'soft_error_tick',['u0041','u0042'],'操作不調がゲーム画面で確認できた場合だけ、台詞の間に小さく1回。'),
    (239.7,239.95,'short_comic_drop',['u0060'],'転落・被弾など実際の失敗が確認できた場合のみ。危機への発言だけなら追加しない。')]:
    add_effect('sfx',a,b,sound=sound,asset_path=None,asset_status='not_selected',
        utterance_ids=refs,gain_db_relative_to_local_dialogue=-12,max_peak_dbfs=-16,
        fade_out_seconds=.05,apply_if=note,
        fallback_action='omit',
        audio_policy='既存ゲーム音で失敗が十分伝わる場合は省略。実況や笑いに重ねず、実際の失敗時刻へ微調整する。')

cut_seconds=sum(b-a for a,b,_ in cuts)
speed_seconds=sum(b-a for a,b,_,_ in speeds)
speed_saved=sum((b-a)*(1-1/r) for a,b,r,_ in speeds)
qualifying_gaps=[g for g in silence['no_speech_intervals'] if g['duration']>=1.2]
silence_decisions=[]
for gap in qualifying_gaps:
    affected=[c for c in clips if c['action']!='keep' and c['start']<gap['end'] and c['end']>gap['start']]
    silence_decisions.append({'start':gap['start'],'end':gap['end'],
        'decision':'partial_cut_candidate' if any(c['action']=='cut' for c in affected)
                   else 'partial_speed_candidate' if affected else 'keep',
        'timeline_ids':[c['id'] for c in affected],
        'reason':'必要な前後を残して一部のみ短縮候補。' if affected
                 else 'リアクション、ゲーム展開、会話の間を保護。無言の長さだけでは削除しない。'})

hook['plan']={
    'schema_version':'1.0','source':transcript['source']['path'],
    'source_duration_seconds':duration,
    'timebase':'start/end are original-video seconds; end is exclusive',
    'ordering':'output_start ascending; main clips cover the original in order, opening reuses a later excerpt',
    'output_times':'provisional, calculated assuming every cut/speed candidate is accepted; recalculate if any candidate changes',
    'render_status':'plan_only_no_video_edit_performed',
    'strategy':'実況と非言語リアクションを残し、不要な間だけ短縮。単調な移動は穏やかに加速し、要所だけ強調。',
    'baseline_action':'keep at 1x; preserve original audio',
    'target_duration_guidance_seconds':[405,435],
    'target_duration_is_hard_limit':False,
    'estimated_duration_seconds':round(out_cursor,3),
    'duration_with_all_candidates_rejected_seconds':round(duration+7,3),
    'source_removed_seconds_if_candidates_accepted':round(cut_seconds,3),
    'source_content_retained_percent':round((duration-cut_seconds)/duration*100,2),
    'source_seconds_played_faster':round(speed_seconds,3),
    'speed_time_saved_seconds':round(speed_saved,3),
    'opening_duration_seconds':7,
    'caption_style':caption_style,
    'visual_output':{'width':1280,'height':720,'fps':30,
        'source_aspect_ratio_policy':'2732x2048の全画面とHUDを基本的に収める。16:9への一律トリミングはしない。余白は無地の暗色。'},
    'preservation_rules':[
        '全105区間の自動文字起こし範囲をカット・倍速対象から外す。誤認識や繰り返しでも音声を確認するまでは残す。',
        '全8見どころ候補を本編で通常速度のまま残す。冒頭の先出しでも本編からは削除しない。',
        '驚き・笑い・息をのむ声・オチ前の間を保護。ASRにない非言語音も再生確認で追加保護する。',
        '強い音量ピーク（RMS -18dBFS以上）のイベント前後0.5秒は短縮しない。音量の低い笑いも確認する。',
        'カット候補は1.2秒以上の無発話区間内のみ。不要と確認できなければ残す。',
        '単調な移動かどうかは未確定。確認後に1.5〜2倍を採用し、内容を残すため今回は3倍を使わない。',
        'ズームを連打せず、効果音は確認できた失敗にだけ最大3回。常時テロップ・揺れ・点滅・追加BGMは使わない。',
        'テロップは聞き直して確定。認識結果にない笑い声や発言を創作しない。'],
    'silence_decisions':silence_decisions,
    'input_sha256':{n:hashlib.sha256((WORK/n).read_bytes()).hexdigest()
                    for n in ['highlights.json','transcript.json','silence.json']},
    'action_semantics':{
        'keep':'通常速度で保持する本編の映像区間',
        'cut':'候補を採用した場合に省く本編区間。output_start=output_end',
        'speed':'候補を採用した場合にrate倍で再生する本編区間',
        'insert_highlight':'本編前に複製して置く見どころ映像',
        'caption':'target_clip_idの映像に重ねる表示文',
        'zoom':'target_clip_idの映像だけを拡大。テロップは拡大しない',
        'sfx':'target_clip_idの元音声に短い音を追加する条件付き候補'},
    'overlap_rule':'異なるlayerは重ねる。同じmain動画区間のcutとspeedは排他。effectsを個別の映像クリップとして連結しない。'}

events.sort(key=lambda e:(e['output_start'],0 if e['layer']=='video' else 1,e['id']))
assert events[0]['id']=='hook01'
assert clips[0]['start']==0 and clips[-1]['end']==duration
assert all(a['end']==b['start'] and a['output_end']==b['output_start'] for a,b in zip(clips,clips[1:]))
assert len({e['id'] for e in events})==len(events)
assert all(0<=e['start']<e['end']<=duration for e in events)
assert all(1.15<=e['scale']<=1.25 for e in events if e['action']=='zoom')
assert all(1.5<=e['rate']<=3 for e in events if e['action']=='speed')
assert 5<=hook['end']-hook['start']<=8
assert abs(out_cursor-(duration+7-cut_seconds-speed_saved))<1e-6
for name,digest in hook['plan']['input_sha256'].items():
    assert hashlib.sha256((WORK/name).read_bytes()).hexdigest()==digest
write('edit_plan.json',events)
summary={'passed':True,'action_counts':{a:sum(e['action']==a for e in events) for a in sorted({e['action'] for e in events})},
         'estimated_output_duration_seconds':round(out_cursor,3),
         'cut_candidate_seconds':round(cut_seconds,3),'speed_time_saved_seconds':round(speed_saved,3),
         'source_content_retained_percent':hook['plan']['source_content_retained_percent'],
         'all_transcript_intervals_preserved_at_1x':True,'all_highlight_intervals_preserved_at_1x':True,
         'strong_audio_events_protected':True,'main_source_timeline_has_no_gaps_or_overlaps':True,
         'source_json_files_unchanged':True,'video_edited':False}
write('edit_plan_validation.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
