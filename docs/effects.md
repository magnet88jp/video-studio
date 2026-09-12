# エフェクトライブラリ

|部品|JSON指定|挙動|
|---|---|---|
|PunchZoom|effect:punchZoom|約0.4秒、100→最大125→115→100%。イージング付き|
|ScreenShake|effect:screenShake|intensityで2〜20px、減衰。外周を拡大し端の隙間を防止|
|Flash|effect:flash|最大でも短い0.1秒の白フェード。既定はさらに低強度|
|ImpactCaption|type:caption / effectのcaption|文字、縁、影、位置、回転、拡大、入退場|
|FreezeFrame|type:freeze|任意元フレームを短時間静止|
|Monochrome|effect:monochrome|intensityでグレースケール|
|SlowMotion|type:speed, rate:0.5〜0.8|映像速度変更＋atempo音声|
|SpeedUp|type:speed, rate:1.5〜3|映像速度変更＋atempo音声|
|RedAlert|effect:redAlert|周辺の薄い赤。中央の視認性を維持|
|FunnyFail|effect:funnyFail|短い静止、縮小、モノクロ、任意caption。seを別イベントで追加可能|

## 複合プリセット

|コンポーネント|effect|構成|
|---|---|---|
|SurpriseEffect|surprise|PunchZoom + ScreenShake + Flash + 任意caption|
|FailEffect|fail|FreezeFrame + Monochrome + ZoomOut + 任意caption|
|WinEffect|win|Zoom + Flash + 任意caption。同時刻のoverlayで装飾|
|DangerEffect|danger|Shake + RedAlert + 任意caption|
|FunnyEffect|funny|PunchZoom + 任意caption。同時刻のseで効果音|

入力intensityは0〜1。config/editing.jsonの全体strength、style係数、各チャンネル係数と組み合わせます。event単位の強度は自動計測値または人の指定です。

設定の正本はconfig/effects.jsonです。白文字・暗い太縁・影を基調に、surpriseは黄色、dangerは赤、winは明るい緑。日本語フォントは利用環境のfontFamilyで変更します。今回のmacOSはHiragino Kaku Gothic ProN。特定クリエイターの素材や装飾を流用しません。

## 追加ルール

既存のプリミティブを組み合わせられる場合は再利用します。新しい演出はsrc/components/effectsまたはsrc/effectsへ追加し、schema.tsのeffectNames、ルーティング、ドキュメント、短いレンダリングを更新します。フレームに対して決定的に計算し、React内でファイル書き込み・ネット取得・Math.random・実時間を使用しません。時間変更はcompileTimelineへ集約してください。
