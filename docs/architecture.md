# アーキテクチャ

Pythonは解析、React / Remotionは映像表現、FFmpegは入力調査・作業コピー・音声処理を担当します。分析結果とレンダリングをJSONで完全に分離しています。

```text
input/*.MP4（読み取り専用）
  → scripts/analyze_video.py → src/analysis/pipeline.py
  → work/audio + work/analysis/*.json
  → scripts/build_edit_plan.py → work/edit_plan.json
  → Zod検証 → compileTimeline → source秒からoutputフレームに変換
  → GameVideo / effect components
  → Remotion renderer → work/*.partial.mp4 → output/*.mp4
```

Remotion 4.0.523の関連パッケージは同じバージョンに固定。React 19、TypeScript strict。既存リポジトリへの導入は[公式brownfield手順](https://www.remotion.dev/docs/brownfield)、映像は[公式Media Video](https://www.remotion.dev/docs/media/video)、最終生成は[renderMedia](https://www.remotion.dev/docs/renderer/render-media)に従います。

## ソース境界とキャッシュ

入力はrealpathでinput内に制限し、解析キャッシュ・プランはSHA-256で照合します。任意パスや外部URLをプランの素材指定で読み込めません。任意素材はassets内（検証時だけwork/fixtures）に限定し、シンボリックリンクによる外部参照も拒否します。元ファイルへは書き込みません。

ブラウザ用コピーはwork/public/media、音程保持音声はwork/public/audio、提供素材のコピーはwork/public/assets。プレビュー検証の識別子はプラン、素材manifest、設定、TS/TSX/JSONソースに由来します。プラン再作成前にwork/plan_historyへバックアップします。

## 解析

16kHz mono PCMで測定。Silero VADと発言区間の和集合の補集合を無言候補にし、FFmpegの-40dBFS無音検出も記録。短い間を除外し、前後0.2秒を保護します。

faster-whisper CPU int8は30秒以下の独立窓を使います。25〜30秒付近の低RMS位置で分割して境界損傷を減らします。単語時刻・信頼度を保存し、前文への依存とVAD連結を無効にします。モデルが取得できない場合はエラー理由を保存して、その他の処理を継続します。

音量は100ms RMS、局所30パーセンタイルからの上昇幅、文字起こしの反応語、文字/秒を統合します。強度0〜1、ピーク間隔2秒。単なるゲーム効果音も含むため、声や失敗を断定しません。編集への採用は反応語と発話近傍を必要とし、12秒の間隔・周辺1分4回以下に制限します。

## 映像と音声

Remotion Sequenceは各出力区間に配置し、Videoは元時刻でtrim。0.5〜3倍の時間変換は共通コンパイラに集約します。映像はミュートして別音声を重ね、速度変更時はFFmpegのatempoで音程を保持します。フリーズ中は音声を静止・反復させず、無音にします。カットはハードカットで、全カットにクロスフェードを付けません。

派手な演出はCSS transform/filter/opacityとRemotionのフレーム補間。揺れに乱数・実時間を使わず、同じJSONから同じフレームを生成します。SE/BGMは任意。欠損素材は警告して省略します。

## 既存実装

旧FFmpeg版はsrc/ffmpeg_edit.pyとscripts/edit.pyに保持し、work/legacyの旧配列プランを使います。旧work/transcript.json等は新解析の同一ハッシュキャッシュとして利用できます。新しい解析結果はwork/analysisに分離します。
