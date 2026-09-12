# 編集ガイド

work/edit_plan.jsonが編集の正本です。プラン生成は解析にだけ依存し、レンダラーは解析ファイルを参照しません。

## ルート

|キー|意味|
|---|---|
|version|1|
|source|input/内の動画パス|
|sourceHash|原本SHA-256。別ファイルへの誤適用防止|
|sourceDuration|ffprobeで測った元の秒数|
|settings|width, height, fps。標準1920×1080|
|digest|enabledとclips。合計5〜8秒、最大3区間|
|events|下表のイベント配列|
|notes|自由な制作メモ|

## 全イベント共通

idは一意。start/endは元動画秒数、endは排他的。enabled既定true、needsReviewは注釈でレンダリング抑止ではありません。抑止するにはenabled=false。scopeはmain / opening / both（既定both）。intensityは0〜1、reasonは判断理由、evidenceは解析根拠です。

|type|必要・主な追加キー|意味|
|---|---|---|
|cut|追加不要|範囲を除去|
|speed|rate:0.5〜3|倍速・スロー|
|caption|caption|選択字幕|
|effect|effect, intensity, caption任意|単体・複合演出|
|freeze|freezeAt任意、holdSeconds任意|指定区間を静止映像に置換|
|se|asset, volume任意|短い音声|
|bgm|asset, volume, loop|BGM。リアクション時に減衰|
|overlay|asset, overlayKind:image/video|画像・動画重畳|

captionではfontSize、position（bottom/center/top/top-left）、rotation（度）、scale、stroke（px）、shadow（CSS）、entrance（pop/slide/fade/none）、exit（fade/none）、colorを指定できます。これは強調字幕用です。通常字幕はwork/transcript.jsonの発話区間に表示し、edit_plan.jsonへ全件コピーしません。

overlayではwidthPercent、opacity、position、loop。動画オーバーレイの音声はミュートです。音声を使う場合は別seイベントにします。ネットURLは読み込みません。

## 時間変換

たとえば2〜4秒をcut、4〜8秒を2倍速にすると、元6秒のイベントは完成3秒に移ります。カット・倍速・フリーズ区間の境界で分割し、累積時間をフレームへ丸めて丸め誤差を抑えます。

有効なcut/speed/freezeの重なりは拒否します。候補同士の重なりは許可します。scopeが異なっていても構造イベントの重なりは許可しません。編集を単純・確認しやすく保つ制約です。

freezeはstart〜endの内容を、freezeAt（既定start）の静止画でholdSeconds秒（既定end-start）に置換します。その間は無音です。発言を含む区間での使用には注意してください。fail / funnyFailには冒頭0.25秒の静止が含まれ、同区間の明示cut/speed/freezeがあれば明示指定を優先します。

冒頭digestは指定区間を先出しし、続いて元0秒から本編を開始します。main限定のカット等はdigestに適用しません。両方への適用はscope:both。先出しの実尺も確認してください（速度イベントで指定範囲の尺と差が出ます）。

## 推奨確認順

1. highlights/reactionsの候補をStudioで再生し、実況の反応かゲーム音か確認。
2. transcriptを聞き比べ、必要な字幕だけenabled=trueにする。
3. silence候補の前後を確認し、重要操作・笑い・驚きを残す。
4. speed候補は単調な移動の場合のみ有効化。同区間のcutを有効化しない。
5. 見どころを5〜8秒に整え、必要ならdigestをON。
6. SE/BGMの音量とスマホでも読める字幕の位置を確認。
7. previewで確認後render。

自動で重要度や失敗を確定する映像認識は未実装です。そのため候補を人が選ぶ半自動運用です。元内容を最大限残す初期プランになっています。
