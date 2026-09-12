# gameplay0307-1 の解析

元動画 `input/gameplay0307-1.MP4` を読み取り、`work/` に解析結果を保存する。動画編集・再エンコードは行わない。時刻は元動画の先頭を0秒とする。大小文字を含む実ファイル名は `.MP4`。

## 依存関係と実行

Python 3.12、FFmpeg/ffprobe、faster-whisper、SciPy。今回の全パッケージバージョンは `work/analysis-requirements.lock.txt`。Whisper large-v3-turbo のCTranslate2変換モデルをCPU・int8で実行する。モデルの初回ダウンロードのみネットワーク接続が必要。動画・音声のアップロードはない。

プロジェクトのルートで実行する。

```sh
python3 -m venv work/analysis-venv
work/analysis-venv/bin/python -m pip install -r work/analysis-requirements.lock.txt
work/analysis-venv/bin/python src/analyze_gameplay.py prepare
HF_HOME=work/huggingface HF_XET_CACHE=work/xet-cache work/analysis-venv/bin/python src/analyze_gameplay.py download
HF_HUB_OFFLINE=1 work/analysis-venv/bin/python src/analyze_gameplay.py transcribe
HF_HUB_OFFLINE=1 work/analysis-venv/bin/python src/analyze_gameplay.py transcribe_bounded
HF_HUB_OFFLINE=1 work/analysis-venv/bin/python src/analyze_gameplay.py analyze
python3 src/sample_gameplay_frames.py
python3 src/finalize_gameplay_analysis.py
```

モデルの取得元と固定スナップショットは `work/model_path.json`。再実行時は既存のモデルを使い、`download` を省略できる。抽出音声が既存の場合は再利用するため、別の元動画を解析する場合は入力と出力のパスを変更すること。

## 出力と解釈

- `work/ffprobe.json`：ストリーム、コーデック、尺、解像度、フレームレート等。
- `work/gameplay0307-1.analysis.wav`：文字起こし・測定用の16kHz、モノラル、16bit PCM。元ステレオをダウンミックス。音量正規化なし。
- `work/transcript.json`：発言単位のテキスト、秒単位の開始・終了、タイムコード、単語時刻、ASR信頼度。句読点または1.2秒以上の単語間の休止で区切る。最終認識は30秒以下の独立した区間を使用し、長い無言をまたぐVAD結合を避ける。区間境界は25〜30秒地点の最小100ms RMSに設定。
- `work/silence.json`：Silero VADとASRの両方で0.6秒以上発話の証拠がない区間と、FFmpegで-40dBFS以下が0.5秒以上続く区間を別々に記録。前者はゲーム音が残る場合も含む。短い実況のVAD取りこぼしを考慮し、ASRの発言範囲も前後0.15秒を保護する。元のVAD区間も保存。
- `work/highlights.json`：大音量イベントと文脈を踏まえた盛り上がり候補。大音量イベントは100ms RMSの上位15%、周囲±5秒の30パーセンタイルから4dB以上上昇、ピーク間隔2秒以上、prominence 3dBで抽出。発言・VADの有無を併記。200–4000Hzの値も混合音の測定であり、実況だけを分離した音量ではない。
- `work/whisper_raw.json`、`work/audio_metrics.json`、`work/silencedetect.log`：自動解析の中間記録。
- `work/source_verification.json`：解析前後のSHA-256、サイズ、更新日時が一致することを検証。

音声は単一の混合トラックのため、実況とゲーム内音声の話者分離は実施していない。固有名詞、叫び声、ゲーム音と重なる発言、発言の境界は自動推定。`needs_review` は編集前の確認目印。候補の抽出はカット指示ではなく、長い無言区間も映像上の見どころを含む可能性がある。

候補の範囲と選定理由は `src/gameplay_highlight_selection.json` に保存している。`finalize_gameplay_analysis.py` が計測結果、発言、優先順位、確認した静止画の所見を統合し、JSONの区間・参照・元ファイルの非変更を検証する。`sample_gameplay_frames.py` は候補から静止画を抽出する。今回16点の静止画を確認したが、通し再生・聴き直しによる確認は未実施。最終結果は自動文字起こしに誤認識候補の目印を加えたもの。最終選定前に再生確認が必要。
