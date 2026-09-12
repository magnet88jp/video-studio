# ゲーム実況・半自動動画エディター

ゲーム実況動画を、次の役割分担で編集するプロジェクトです。

- **固定スクリプト**: 文字起こし、解析、素材準備、レンダリング
- **Codex**: 小さいJSONを見て編集判断・`edit_plan.json`更新
- **Remotion**: 字幕・ズーム・シェイク・フラッシュなどの映像表現
- **FFmpeg**: 音声抽出、作業用動画生成、メディア処理

大容量動画をCodexのターン内で処理させないことで、Codexの利用量と無駄な長時間ツール実行を抑えます。

---

## 1. なぜこの運用にするのか

907MBのような大容量動画では、以下をCodexから繰り返し実行すると非効率です。

- 元動画全体のSHA-256計算
- Whisper文字起こし
- 音声・リアクション解析
- H.264作業用動画の全編生成
- Remotionプレビュー
- 全編レンダリング

この版では、元動画のSHA-256を`size + mtime`が同じ間は再利用し、重い動画処理はCodexから自動実行しない設計にしています。

Codexには主に次の小さいファイルだけを扱わせます。

```text
work/edit_brief.json
work/edit_plan.json
work/transcript.json の必要な区間だけ
```

---

## 2. 必要環境

- Node.js 22以上
- npm
- Python 3.10以上
- FFmpeg / ffprobe
- Chrome（Remotion Studio / Render用）

初回セットアップ:

```sh
npm ci
python3 -m venv work/analysis-venv
work/analysis-venv/bin/python -m pip install -r requirements-analysis.txt
```

文字起こしモデルを事前取得する場合:

```sh
work/analysis-venv/bin/python scripts/download_model.py
```

---

## 3. 元動画を配置

動画は`input/`に置きます。

```text
input/gameplay.mp4
```

`input/`は読み取り専用として扱います。元動画を上書きしません。

---

## 4. Codexへ渡す前の前処理

### 基本

Codexを起動する前に、自分のターミナルで実行します。

```sh
./scripts/preprocess.sh input/gameplay.mp4
```

このコマンドは次を行います。

```text
input/gameplay.mp4
       ↓
Whisper文字起こし
       ↓
work/transcript.json
       ↓
無言・リアクション・ハイライト解析
       ↓
work/analysis/*
       ↓
初期編集プラン
       ↓
work/edit_plan.json
       ↓
Codex向け要約
       ↓
work/edit_brief.json
```

動画のレンダリングは行いません。

### モデルを指定

```sh
./scripts/preprocess.sh input/gameplay.mp4 --model small
```

### 編集プランを作り直す

```sh
./scripts/preprocess.sh input/gameplay.mp4 --replan
```

既存の手修正済み`edit_plan.json`を不用意に消さないよう、通常は`--replan`を付けないでください。

---

## 5. Remotion用の作業動画を準備

Remotion Studioやプレビューを初めて使う前に、必要な場合だけ実行します。

```sh
./scripts/preprocess.sh input/gameplay.mp4 --prepare-media
```

または前処理済みなら:

```sh
./node_modules/.bin/tsx scripts/remotion.ts prepare-media
```

これにより、ブラウザで安定して再生するためのH.264コピーを`work/public/media/`へ作成します。

### 重要

`npm run preview`や`npm run studio`は、作業用H.264コピーが存在しない場合に**勝手に907MBの動画全編を再エンコードしません**。

未準備の場合は停止して`prepare-media`を案内します。

これにより、Codexのツール実行中に予期せぬ重い変換が始まることを防ぎます。

---

## 6. Codexへ依頼する

前処理後、Codexには次のように依頼します。

```text
このゲーム実況動画の編集プランを調整してください。

重要:
- transcribeを実行しない
- analyzeを実行しない
- prepare-mediaを実行しない
- previewを実行しない
- renderを実行しない
- input/*.mp4を直接解析しない

まず work/edit_brief.json と work/edit_plan.json を確認してください。
字幕が必要な場合だけ work/transcript.json の必要時間帯を確認してください。

通常字幕は work/transcript.json を使用し、
演出だけ work/edit_plan.json へ追加・修正してください。

作業後は work/edit_plan.json の変更内容と、
私が確認すべき時間帯だけ教えてください。
```

`AGENTS.md`にも同じ原則を記載しているため、Codexが重い処理を勝手に連鎖実行しにくくなっています。

---

## 7. 字幕の扱い

ゲーム実況なので、通常字幕は可能な限り表示します。

通常字幕の正本:

```text
work/transcript.json
```

例:

```json
[
  {
    "start": 12.1,
    "end": 14.4,
    "text": "この先たぶん敵いるんだよね"
  },
  {
    "start": 14.5,
    "end": 15.4,
    "text": "うわっ！"
  }
]
```

演出の正本:

```text
work/edit_plan.json
```

例:

```json
{
  "start": 14.5,
  "end": 15.2,
  "type": "effect",
  "effect": "surprise",
  "intensity": 0.9,
  "caption": "うわっ！！",
  "enabled": true
}
```

通常字幕を全部`edit_plan.json`へコピーしないことで、編集プランとCodexコンテキストを小さく保ちます。

---

## 8. プレビューは自分のターミナルで実行

Codexが`edit_plan.json`を変更したら、まず短い区間だけ確認します。

```sh
npm run preview -- --start 0 --seconds 30
```

気になる区間だけ確認:

```sh
npm run preview -- --start 120 --seconds 15
```

出力:

```text
output/preview.mp4
```

プレビューで確認する項目:

- 通常字幕のタイミング
- 強調字幕の大きさ
- ズームの強さ
- シェイクの強さ
- フラッシュの長さ
- ゲームUIを字幕が隠していないか
- カット境界
- 音声同期

---

## 9. Remotion Studio

作業用H.264動画を準備したあと:

```sh
npm run studio
```

通常は次で開けます。

```text
http://localhost:3333
```

Studioはコードで作った動画をブラウザ上で確認するための開発UIです。

---

## 10. 最終レンダリング

現在の編集プランとコードに一致するプレビューを確認してから実行します。

```sh
npm run render
```

出力:

```text
output/final.mp4
```

この版では、最終レンダリング時にプレビューが古い/存在しない場合、勝手にプレビューを追加レンダリングせず停止します。

意図的にプレビュー確認を省略する場合のみ:

```sh
npm run render -- --skip-preview-check
```

通常は使用しないことを推奨します。

---

## 11. SHA-256キャッシュ

大容量の元動画を何度も全読みしないため、元動画の識別情報をキャッシュします。

主なキャッシュ/解析情報:

```text
work/source_identity.json
work/analysis/video_info.json
```

以下が変わっていなければ、保存済みSHA-256を再利用します。

- ファイルパス
- ファイルサイズ
- 更新日時

これにより、907MBの動画を`transcribe`、`analyze`、`preview`のたびに何度もSHA-256計算する処理を削減します。

元動画が変更された場合は、新しいSHA-256が計算されます。

---

## 12. 各ファイルの役割

| ファイル | 役割 | Codexが通常読むか |
|---|---|---|
| `input/*.mp4` | 元動画 | いいえ |
| `work/edit_brief.json` | 編集候補の要約 | はい |
| `work/edit_plan.json` | 演出・カット等の編集計画 | はい |
| `work/transcript.json` | 通常字幕 | 必要区間だけ |
| `work/analysis/*` | 詳細解析結果 | 原則不要 |
| `work/public/media/*` | Remotion作業用動画 | いいえ |
| `output/preview.mp4` | 確認動画 | ユーザーが確認 |
| `output/final.mp4` | 完成動画 | 最終成果物 |

---

## 13. 個別コマンド

### 文字起こしだけ

```sh
npm run transcribe -- input/gameplay.mp4
```

または:

```sh
python scripts/transcribe.py input/gameplay.mp4 --model small --language ja
```

### 解析

専用文字起こし結果を再利用して、別のWhisper処理を走らせない:

```sh
npm run analyze -- --input input/gameplay.mp4 --reuse-transcript
```

### 初期プラン生成

```sh
npm run plan -- --input input/gameplay.mp4
```

### 型・Pythonチェック

```sh
npm run typecheck
npm run check:python
npm test
npm run validate
```

`validate`は作業用H.264動画がなくてもComposition/JSONの検証を行えるようにしています。

---

## 14. Codex利用量を抑える運用ルール

### やること

- 重い処理はターミナルで先に実行
- CodexにはJSON編集を中心に依頼
- 1回の依頼を1目的にする
- `edit_brief.json`から候補を絞る
- 字幕全文ではなく必要時間帯だけ確認
- 15〜30秒の短いプレビューを使う
- 作業用動画・文字起こし・解析結果を再利用

### やらないこと

Codexへ次のような依頼をしない:

```text
全部解析して、文字起こしして、
エフェクトを追加して、全編プレビューして、
問題があれば直して、最終動画まで作って。
```

代わりに:

```text
work/edit_brief.json と work/edit_plan.json を確認して、
120〜180秒の編集だけ改善してください。
edit_plan.json以外は変更せず、レンダリングもしないでください。
```

のように範囲を限定します。

---

## 15. 推奨する日常フロー

```text
① input/に動画を置く
        ↓
② ./scripts/preprocess.sh input/gameplay.mp4 --prepare-media
        ↓
③ Codexを起動
        ↓
④ edit_brief + edit_planだけで編集判断
        ↓
⑤ Codexがedit_plan.jsonを更新
        ↓
⑥ 自分で15〜30秒preview
        ↓
⑦ 必要箇所だけCodexへ修正依頼
        ↓
⑧ 自分でpreview
        ↓
⑨ npm run render
```

同じ動画で2回目以降は、文字起こし・SHA-256・作業用動画などのキャッシュを再利用できます。

---

## 16. よくあるエラー

### Browser media is not prepared

先に実行:

```sh
./node_modules/.bin/tsx scripts/remotion.ts prepare-media
```

### Current plan/code has no matching preview

現在の編集内容を短く確認:

```sh
npm run preview -- --start 0 --seconds 30
```

その後:

```sh
npm run render
```

### faster-whisperがない

```sh
work/analysis-venv/bin/python -m pip install -r requirements-analysis.txt
```

### ffmpeg / ffprobeがない

PATHとFFmpegのインストールを確認してください。

### メモリ不足

`config/editing.json`の`render.concurrency`を下げてください。

---

## 17. 元動画の保護

元動画は常に`input/`配下で読み取り専用として扱います。

レンダリング前後の軽量な保護チェックは、毎回907MBを再ハッシュするのではなく、ファイルサイズと更新日時で確認します。

SHA-256自体は初回または元動画のメタデータ変更時に計算します。

より厳密な監査が必要な場合は、必要なタイミングで明示的にフルSHA-256を再計算してください。
