# ゲーム実況編集プロジェクト - Codex運用ルール

## 目的
このプロジェクトでは、ゲーム実況動画の前処理・字幕・編集プラン生成・Remotionレンダリングを行う。
Codexの利用量を抑えるため、**重い動画処理はCodexのターン内で自動実行しない**。

## 最重要ルール
- `input/` の元素材は読み取り専用。変更・削除・上書き禁止。
- Codexは通常、`work/edit_brief.json`、`work/edit_plan.json`、必要な範囲の`work/transcript.json`だけを読む。
- Codexは通常、`input/*.mp4`を直接読み込まない。
- Codexは通常、次の重い処理を実行しない。
  - `transcribe`
  - `analyze`
  - `prepare-media`
  - `preview`
  - `render`
  - 元動画全体のSHA-256再計算
  - FFmpegによる全編再エンコード
- 上記を実行するのは、ユーザーが明示的に「実行して」と依頼した場合のみ。
- ユーザーが動画編集を依頼した場合、前処理済みデータがあるなら**編集判断と`work/edit_plan.json`の更新だけ**を行う。
- 新規ライブラリ追加、大規模リファクタリング、プロジェクト再構築は依頼がない限り行わない。

## 推奨ワークフロー
### 1. ユーザーがローカルで前処理
Codexに依頼する前に、ユーザーがターミナルで実行する。

```sh
./scripts/preprocess.sh input/動画.mp4
```

Remotion Studioやプレビューも使う場合のみ、作業用H.264コピーを明示的に準備する。

```sh
./scripts/preprocess.sh input/動画.mp4 --prepare-media
```

### 2. Codexが見るファイル
最初に以下だけ確認する。

1. `work/edit_brief.json`
2. `work/edit_plan.json`
3. 必要な時間帯だけ `work/transcript.json`

全文字幕・全解析JSON・全ログを一括でコンテキストへ入れない。

### 3. Codexが行う作業
- 無言候補、リアクション候補、ハイライト候補を`edit_brief.json`から確認。
- 必要な字幕だけ`transcript.json`から確認。
- `work/edit_plan.json`の編集イベントを追加・修正。
- 通常字幕は`work/transcript.json`を正本とし、全字幕を`edit_plan.json`へコピーしない。
- 既存のエフェクト・プリセットを優先して再利用。

### 4. ユーザーが確認
CodexによるJSON編集後、ユーザーがローカルで実行する。

```sh
npm run preview -- --start 0 --seconds 30
```

必要な区間だけ確認する。

```sh
npm run preview -- --start 120 --seconds 15
```

### 5. 最終出力
プレビュー確認後、ユーザーが実行する。

```sh
npm run render
```

`render`は現在のプランに一致するプレビューがない場合、自動でプレビューを作らず停止する。意図的に省略する場合だけ`--skip-preview-check`を使う。

## 編集方針
- 通常字幕：実況音声の大部分を表示。1〜2行、下部中央、白太字＋黒縁を基本。
- 強調字幕：重要発言や強いリアクションのみ。
- カット：1.2秒以上の不要な間を候補とするが、ゲーム内容を失うカットは避ける。
- `punchZoom`：短いリアクション強調。
- `screenShake`：強い反応だけ。
- `flash`：非常に短く控えめ。
- `speed`：単調な移動・作業に1.5〜3倍速候補。
- `freeze` / `monochrome` / `funnyFail`：失敗・笑いどころに選択的に使用。
- 同じ演出を連発しない。派手だが見づらくしない。

## キャッシュと大容量動画
- 元動画のSHA-256は`size + mtime`が変わらない限りキャッシュを再利用する。
- 907MB級の入力を毎回フルハッシュしない。
- 文字起こし音声、解析結果、ブラウザ用H.264コピーは`work/`配下で再利用する。
- プレビュー時にブラウザ用全編コピーを自動生成しない。未準備なら停止し、`prepare-media`を案内する。
- 変更のない解析・文字起こし・全編レンダリングを繰り返さない。

## 保護対象と出力先
- 元動画: `input/`（変更禁止）
- 中間生成物: `work/`
- 通常字幕: `work/transcript.json`
- 編集プラン: `work/edit_plan.json`
- Codex向け要約: `work/edit_brief.json`
- プレビュー/完成動画: `output/`

## 完了報告
Codexが編集作業を終えたら、以下だけ簡潔に報告する。
- 変更したファイル
- 追加・変更した編集イベント数
- 要確認区間
- ユーザーが次に実行するプレビューコマンド

重い処理を勝手に続行しない。
