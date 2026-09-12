# バスケットボール動画・修正版

`render_basketball.py` で150フレームを描画し、`encode.swift` で5秒・1280×720・30fps・音声なしのMP4を出力します。

変更点：放物線の頂点を約55px高くし、4.3秒までフォロースルーを維持。3.5秒のリング通過後にネットを伸縮させ、減衰する左右の揺れを加えています。

プロジェクトのルートで実行：

```sh
python3 src/render_basketball.py
swift -module-cache-path work/swift-cache src/encode.swift
```

PythonにはPillowが必要です。書き出しにはmacOSのAVFoundationを使用します。
完成品は `outputs/basketball_shot_revised.mp4`、中間ファイルと検証結果は `work/` に保存します。元の動画とソースは `outputs/` に保持しています。
