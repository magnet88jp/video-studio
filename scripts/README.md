# ゲーム実況のFFmpeg編集

プロジェクトのルートから実行する。

```sh
python3 scripts/edit.py
```

出力：`outputs/final.mp4`。1920×1080、30fps、H.264 High / yuv420p、AAC 192kbps・48kHz・ステレオ。

`scripts/edit.py` が入口、実装は `src/ffmpeg_edit.py`。依存はFFmpeg（libx264、AAC、zoompan、overlay、atempo）、ffprobe、Python 3.12、Pillow、日本語フォントのヒラギノ角ゴシックW7。今回使用したFFmpegは9.0.1、Pillowは12.3.0。Pillowが通常のPythonにない場合、このMacのCodex同梱Pythonを自動選択する。他環境ではPillowを導入し、必要に応じてフォント指定を変更する。

## プランと素材の扱い

- 入力は `work/edit_plan.json`。開始・終了は元動画の秒数で解釈する。
- 条件付き候補の採否は `src/edit_decisions.json`。短い動作、移動先の変化、空中の車両は保持し、文字起こしが一致しない字幕は省いた。今回の採否はサンプル静止画と再ASRに基づくもので、手動で全編を聴き起こしたものではない。
- 解決後の全時刻・効果は `work/final_edit/resolved_plan.json`。実際の完成尺はこのファイルを参照する。元のプランJSONは変更しない。
- 元動画は入力として開くだけ。編集開始前後にSHA-256・サイズ・更新日時を比較する。入力ディレクトリや元動画への出力は拒否する。
- 4:3に近い元画面は通常場面で全体を収め、左右に暗色の余白を付ける。ズームは上部のコイン・体力表示を保つ上端中央基準。短いズーム中は下端のタッチ操作アイコンの一部が画角外になる。
- テロップは日本語フォントでPNGを生成して合成する。ズーム後に重ねるため文字サイズは一定。
- 効果音は短い下降音をコードで生成し、被ダメージ場面に1回だけ控えめに追加。素材の購入・ダウンロードはない。
- 倍速はFFmpegの`atempo`で音程を維持。カット境界は4msの音声ランプでクリックノイズを抑える。通常音声の大きさは維持する。

## 再実行と確認

```sh
python3 scripts/edit.py --prepare-only
python3 scripts/edit.py --preview
python3 scripts/edit.py --jobs 2 --preset fast
python3 scripts/edit.py --validate-only
```

中間素材・フィルター・実行コマンド・ログは `work/final_edit/`。同じ元素材・同じコード・同じ設定の区間はキャッシュを再利用する。区間ごとに累積フレーム数を30fpsへ丸め、音声も同じ長さにそろえて長尺の音ズレを防ぐ。

映像は区間ごとにCRF19でH.264化し、連結時は映像を再圧縮しない。中間音声はPCMで保持し、連結時に1回だけAAC化する。既存の `final.mp4` を再生成する場合、以前の完成品を `work/final_edit/previous_final_*.mp4` に退避する。

`work/final_edit/validation.json` に尺、解像度、コーデック、フレーム数、映像と音声の長さ、全編デコード検証、元動画の非変更を記録する。主要フレームは `validation_contact_*.jpg`。追加の検証記録は `work/final_edit/` に保存する。
