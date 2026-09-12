# 編集プラン生成

実行：`python3 src/build_edit_plan.py`（プロジェクトのルート）。Python標準ライブラリのみ使用する。

`work/highlights.json`、`work/transcript.json`、`work/silence.json`を読み、`work/edit_plan.json`と`work/edit_plan_validation.json`を生成する。入力JSONと元動画は変更しない。

出力はアクションの配列。`start` / `end` は**元動画の秒数**で、終了端は含まない。`output_start` / `output_end` はすべての短縮候補を採用した場合の**仮の完成動画時刻**。先頭の7秒の見どころは `instance: opening`、本編は `instance: main`。先出しした箇所も本編に残す。

先頭の `insert_highlight` 項目の `plan` に全体方針、尺の見込み、表示仕様、無言区間ごとの判断を格納する。`layer: video` の本編項目は入力全体を重複なく覆う。caption / zoom / sfx は `target_clip_id` に重ねるものであり、映像クリップとして後ろに連結しない。テロップはズーム後の画面上に置き、HUDを避ける。

cut / speed / sfx は再生確認が必要な候補。`apply_if` が成立しない場合は `fallback_action` に従って保持または省略する。確認待ちとはユーザーの承認待ちを意味せず、実編集時の素材確認条件である。候補や境界を変更したら出力時刻を再計算する。音量やASRだけでは「無言が不要」「移動が単調」「実際に失敗した」と断定しない。

今回、発言105区間、見どころ8区間、強い音量ピークをカットと倍速から保護した。話者分離と手作業による音声確認は未実施なので、テロップを焼き込む前に聞き直す。効果音のファイルは未選定。実編集時に短く控えめな素材を用意し、ゲーム音だけで十分なら省略する。このコードは動画を編集・書き出ししない。
