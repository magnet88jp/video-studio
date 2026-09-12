# ゲーム実況・半自動動画エディター

元動画を守りながら、音声解析 → JSON編集計画 → Remotionプレビュー → MP4書き出しを行います。自動判定は候補です。実況とゲームの内容を残すため、カット・倍速・自動字幕は確認後に有効化します。

## 初回セットアップ

Node.js 22以上、npm、Python 3.10以上、FFmpeg / ffprobe、Chromeが必要です。

```sh
npm ci
python3 -m venv work/analysis-venv
work/analysis-venv/bin/python -m pip install -r requirements-analysis.txt
```

既存の仮想環境がある場合、作り直す必要はありません。OS全体へのインストールや管理者権限は不要です。`EDITOR_PYTHON` でPythonを指定できます。通常は `work/analysis-venv/bin/python` を自動使用します。

文字起こしモデルは初回だけダウンロードします（動画は送信しません）。

```sh
work/analysis-venv/bin/python scripts/download_model.py
```

ダウンロードができなくても、音量・無言解析と編集機能は利用できます。`work/analysis/transcript.json` を手入力する場合は、`[{"id":"u1","start":1.0,"end":2.5,"text":"セリフ","needs_review":false}]` の配列にします。自動再解析で置き換わる前に別名で保存してください。

## 元動画の置き場所

MP4を `input/` に置きます。拡張子は `.MP4` でも構いません。複数ある場合は一覧を表示し、名前順の最初を選びます。対象を明示するには以下を使います。

```sh
npm run analyze -- --input input/gameplay0307-1.MP4
npm run plan -- --input input/gameplay0307-1.MP4
```

`input/` と既存 `assets/` は書き換えません。元動画のSHA-256を解析時・レンダリング前後に確認します。ブラウザ再生用H.264コピーや音声は `work/`、新しい完成動画は **`output/`** に保存します。旧FFmpeg版の `outputs/` は保持しています。

## 動画解析方法

```sh
npm run analyze
```

`work/analysis/` に `video_info.json`、`silence.json`、`transcript.json`、`reactions.json`、`highlights.json` と根拠・原本照合のメタデータを保存します。解析音声は `work/audio/commentary.wav` です。元動画と同じハッシュの文字起こしキャッシュだけを再利用します。再認識は `npm run analyze -- --force-transcribe`。

音声はゲーム音と実況の混合です。話者分離・ゲーム内の失敗判定・移動判定は自動確定しません。叫び声、笑い、ゲーム効果音、固有名詞は聞いて確認してください。

## 編集プラン作成方法

```sh
npm run plan
```

`work/edit_plan.json` を作成します。既存プランは `work/plan_history/` にバックアップします。再実行すると手修正を含むプランが再生成されるため、必要な版を別名で保管してください。解析対象と異なる動画からプランを生成しようとすると停止します。

## Remotion Studioで確認する方法

```sh
npm run studio
```

表示されたローカルURL（通常 `http://localhost:3333`）をブラウザで開き、`GameVideo` を選びます。初回はHEVCなどから作業用動画を生成するため時間がかかります。`DemoVideo` は冒頭30秒の動作見本です。

JSONを変更したらStudioを停止して同じコマンドで再起動してください。起動時にプランを検証してpropsに変換します。ブラウザの手動再読込だけではJSONの変更が反映されません。

## edit_plan.jsonを手修正する方法

`start` / `end` は**編集前の元動画の秒数**です。終了時刻は含みません。`enabled:false` は候補を残すだけで動画に適用しません。

```json
{"id":"my-surprise","start":238.5,"end":239.8,"type":"effect","effect":"surprise","intensity":0.8,"caption":"えっ！？","enabled":true}
```

これは形式例です。実際の発言を確認して文言と時刻を置き換えてください。ルートの `events` 配列に追加します。`id` は重複不可です。

- カット：`type:"cut"`。無言候補でもゲーム内容が重要なら無効のまま残します。
- 倍速・スロー：`type:"speed", rate:2` または `rate:0.7`。
- 字幕：`type:"caption", caption:"確認済みの発言"`。
- 静止：`type:"freeze", freezeAt:12.3, holdSeconds:0.3`。
- 冒頭：`digest.enabled:true`。`clips` に合計5〜8秒、最大3区間を指定します。本編の同じ場面も残ります。

詳細・全フィールド・時間変換の注意点は [編集ガイド](docs/editing-guide.md) を参照してください。

## SEの追加方法

利用権限のある音声を `assets/se/` に置きます。イベント例：

```json
{"id":"se1","start":238.5,"end":239.0,"type":"se","asset":"assets/se/surprise.mp3","volume":0.4}
```

指定素材がなくても警告だけで書き出しを続行します。標準プランは `config/effects.json` の対応表に従ってSEイベントを作ります。自動でネットから素材を取得しません。

## BGMの追加方法

利用権限のあるBGMを `assets/bgm/` に置き、プランを再生成すると先頭の音声素材を低音量で追加します。手修正で追加する場合：

```json
{"id":"bgm1","start":0,"end":479.365,"type":"bgm","asset":"assets/bgm/music.mp3","loop":true,"volume":0.045}
```

`end` は入力の尺に合わせてください。リアクション付近ではBGMを下げます。SE・BGMを追加したら必ず音量バランスをプレビューしてください。

## エフェクト強度の変更方法

`config/editing.json` の `style` を `subtle` / `balanced` / `energetic` / `chaotic` から選びます。初期値は `energetic` と全体係数 `strength:0.82` で、balancedより少し派手です。`effects` の `zoom` / `shake` / `flash` / `captions` / `soundEffects` を0〜1で調整できます。0で該当要素を無効化します。

色、フォント、縁取り、プリセット係数は `config/effects.json`。個々のイベントでは `intensity:0〜1` を指定します。[エフェクト一覧](docs/effects.md) を参照してください。

## プレビュー作成方法

```sh
npm run preview
npm run preview -- --start 230 --seconds 15
```

通常は先頭30秒を960×540で `output/preview.mp4` に保存します。`--start` は**完成タイムラインの秒数**です。上の部分プレビューは230秒から15秒。最初の4エフェクト見本は `npm run demo` → `output/demo.mp4`。

別のプラン：`npm run preview -- --plan work/my_plan.json --seconds 15`。

## 最終レンダリング方法

プレビューで内容・字幕・音声を確認してから実行します。

```sh
npm run render
```

`output/final.mp4` に1920×1080、H.264 / AACを出力します。今回の入力は可変FPS・実質60fpsのため60fps。通常は入力平均FPSを尊重します。新しいプラン・設定・コードのプレビューがない場合、先に短いプレビューを作成します。最終ファイルは書き出し完了後に置き換えます。途中ファイルは `work/` です。

全編は短いプレビューより時間と空き容量が必要です。素材の作業コピーは再利用します。レンダリング時に `--plan` で別JSONも指定できます。

## 検証コマンド

```sh
npm run typecheck
npm run check:python
npm test
npm run validate
```

`validate` はJSONとComposition読み込み、`test` は時間変換と境界条件を検証します。書き出し後の形式・尺・原本ハッシュは `work/analysis/*_validation.json`、主要フレームは `work/previews/` に保存されます。

## よくあるエラー

- `ffmpeg` / `ffprobe` が見つからない：実行環境のPATHを確認してください。
- ローカルモデルがない：モデル取得コマンドを実行してください。解析のメタデータに利用不可の理由を保存します。
- `source hash` の不一致：対象動画を指定して `analyze` → `plan` を実行してください。
- `Enabled cut/speed/freeze intervals must not overlap`：同じ区間の構造イベントを同時に有効化しないでください。
- 文字化け・豆腐：日本語フォントをOSで利用可能にし、`config/effects.json` の `fontFamily` を変更してください。今回のmacOSではヒラギノを使用します。
- Chromeが見つからない：`REMOTION_BROWSER` にChromeの実行ファイルを指定してください。なければRemotionがブラウザ取得を試みるためネット接続が必要です。
- `EPERM` / ローカル通信が禁止：エージェントの実行サンドボックスでは、Studio・レンダラー・tsx用のローカル通信許可が必要な場合があります。
- メモリ不足：`config/editing.json` の `render.concurrency` を1に下げてください。
- SE/BGMが鳴らない：`work/analysis/media_warnings.json` と素材パス、enabled、音量を確認してください。

旧版FFmpeg編集は `python3 scripts/edit.py`。既定プランを `work/legacy/edit_plan_ffmpeg.json` に固定し、新しいオブジェクト形式と分離しています。旧成果物は `outputs/final.mp4` です。

設計の正本は [architecture.md](docs/architecture.md)、[editing-guide.md](docs/editing-guide.md)、[effects.md](docs/effects.md)。

## 文字起こしのみ

`npm run transcribe`（既定small/ja）または `python scripts/transcribe.py input/gameplay0307-1.MP4 --model small --language ja` で `work/transcript.json` を生成します。`--duration 30` は冒頭30秒だけの確認用です。編集プランやRemotionは変更しません。初回モデル取得にはネット接続が必要です。
