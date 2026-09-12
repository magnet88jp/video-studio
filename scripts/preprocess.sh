#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/preprocess.sh input/video.mp4 [--model small] [--replan] [--prepare-media]

Purpose:
  Run heavy preprocessing locally BEFORE handing the project to Codex.

Steps:
  1. Transcribe with the fixed Whisper script
  2. Reuse that transcript for analysis
  3. Create/reuse work/edit_plan.json and work/edit_brief.json
  4. Optional: create the reusable H.264 browser copy for Remotion

Options:
  --model NAME       Whisper model (default: existing cached model, otherwise small)
  --replan           Rebuild work/edit_plan.json (existing plan is backed up by the tools)
  --prepare-media    Also prepare reusable H.264 browser media for Studio/preview
  -h, --help         Show this help
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

INPUT="$1"
shift
MODEL=""
REPLAN=0
PREPARE_MEDIA=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      [[ $# -ge 2 ]] || { echo "--model requires a value" >&2; exit 2; }
      MODEL="$2"
      shift 2
      ;;
    --replan)
      REPLAN=1
      shift
      ;;
    --prepare-media)
      PREPARE_MEDIA=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

[[ -f "$INPUT" ]] || { echo "Input file not found: $INPUT" >&2; exit 1; }
case "$INPUT" in
  input/*) ;;
  *) echo "Input must be inside input/: $INPUT" >&2; exit 1 ;;
esac

for cmd in node npm python3 ffmpeg ffprobe; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Required command not found: $cmd" >&2; exit 1; }
done

[[ -d node_modules ]] || {
  echo "node_modules is missing. Run: npm ci" >&2
  exit 1
}

PREP=(python3 scripts/prepare_edit.py "$INPUT")
[[ -n "$MODEL" ]] && PREP+=(--model "$MODEL")
[[ "$REPLAN" -eq 1 ]] && PREP+=(--replan)

echo "[1/2] Preparing transcript, analysis, edit brief and edit plan..."
"${PREP[@]}"

echo "[2/2] Checking handoff files..."
for file in work/edit_brief.json work/edit_plan.json work/transcript.json work/analysis/video_info.json; do
  [[ -s "$file" ]] || { echo "Expected handoff file missing or empty: $file" >&2; exit 1; }
done

if [[ "$PREPARE_MEDIA" -eq 1 ]]; then
  echo "[optional] Preparing reusable H.264 browser media..."
  ./node_modules/.bin/tsx scripts/remotion.ts prepare-media
fi

cat <<'DONE'

Preprocessing complete.

Hand these SMALL files to Codex logically (Codex should read them from the repo):
  - work/edit_brief.json
  - work/edit_plan.json
  - only required ranges from work/transcript.json

Recommended Codex instruction:
  "Do not run transcribe/analyze/prepare-media/preview/render. Read work/edit_brief.json
   and work/edit_plan.json, inspect only the necessary transcript ranges, and update
   work/edit_plan.json only."

After Codex edits the plan, run preview yourself, for example:
  npm run preview -- --start 0 --seconds 30
DONE
