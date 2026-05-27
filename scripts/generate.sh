#!/bin/bash
# Grsai Image Generation Script
# Usage: bash generate.sh [options] "prompt"
#
# Requires: GRSAI_API_KEY environment variable (or .env file in project root)

set -euo pipefail

# --- Load .env if present ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
fi

# --- Config ---
API_KEY="${GRSAI_API_KEY:?Error: GRSAI_API_KEY not set. Copy .env.example to .env and add your key.}"
BASE_URL="${GRSAI_BASE_URL:-https://grsaiapi.com}"
OUTPUT_DIR="${GRSAI_OUTPUT_DIR:-$HOME/Downloads}"

# --- Defaults ---
MODEL="nano-banana-pro-vip"
RATIO="auto"
SIZE="2K"
REFS=""
ASYNC_MODE="false"
QUALITY="auto"
HELP="false"
POLL_INTERVAL=5
POLL_ATTEMPTS=200

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --ratio) RATIO="$2"; shift 2 ;;
    --size) SIZE="$2"; shift 2 ;;
    --ref) REFS="$2"; shift 2 ;;
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    --async) ASYNC_MODE="true"; shift ;;
    --quality) QUALITY="$2"; shift 2 ;;
    --help|-h) HELP="true"; shift ;;
    -*) echo "Unknown option: $1"; exit 1 ;;
    *) PROMPT="$1"; shift ;;
  esac
done

if [[ "$HELP" == "true" ]] || [[ -z "${PROMPT:-}" ]]; then
  cat <<'EOF'
Grsai Image Generation

Usage: bash generate.sh [options] "prompt description"

Options:
  --model MODEL    Model name (default: nano-banana-pro-vip)
                   nano-banana: nano-banana, nano-banana-fast, nano-banana-2, nano-banana-2-cl,
                   nano-banana-2-4k-cl, nano-banana-pro, nano-banana-pro-cl, nano-banana-pro-vip,
                   nano-banana-pro-4k-vip
                   gpt-image: gpt-image-2, gpt-image-2-vip
  --ratio RATIO    Aspect ratio (default: auto)
                   auto, 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3, 5:4, 4:5, 21:9
                   nano-banana-2 extra: 1:4, 4:1, 1:8, 8:1
  --size SIZE      Resolution: 1K, 2K, 4K (nano-banana) or WxH like 2048x2048 (gpt-image-2-vip)
  --ref PATH       Reference image path(s), comma-separated
  --output DIR     Output directory (default: ~/Downloads)
  --quality QUAL   Image quality: auto, low, medium, high (default: auto)
  --async          Use async polling mode
  --help           Show this help

Environment:
  GRSAI_API_KEY    (required) Your Grsai API key
  GRSAI_BASE_URL   API base URL (default: https://grsaiapi.com)
  GRSAI_OUTPUT_DIR Default output directory (default: ~/Downloads)

Examples:
  bash generate.sh "a cute cat, digital art"
  bash generate.sh --model nano-banana-pro-4k-vip --ratio 16:9 --size 4K "landscape at sunset"
  bash generate.sh --model gpt-image-2-vip --size 2048x2048 "abstract geometric art"
  bash generate.sh --model gpt-image-2 --quality high "detailed artwork"
  bash generate.sh --ref /path/to/photo.jpg "same character in a different pose"
EOF
  exit 0
fi

# --- Build images array ---
IMAGES_JSON="[]"
if [[ -n "$REFS" ]]; then
  IMAGES_JSON="["
  IFS=',' read -ra REF_ARRAY <<< "$REFS"
  FIRST=true
  for ref in "${REF_ARRAY[@]}"; do
    ref=$(echo "$ref" | xargs)  # trim whitespace
    if [[ "$ref" == http* ]]; then
      if [[ "$FIRST" == "true" ]]; then
        IMAGES_JSON+="\"$ref\""
        FIRST=false
      else
        IMAGES_JSON+=",\"$ref\""
      fi
    else
      if [[ ! -f "$ref" ]]; then
        echo "Reference file not found: $ref" >&2
        exit 1
      fi
      MIME=$(file --brief --mime-type "$ref")
      B64=$(base64 -i "$ref" | tr -d '\n')
      if [[ "$FIRST" == "true" ]]; then
        IMAGES_JSON+="\"data:${MIME};base64,${B64}\""
        FIRST=false
      else
        IMAGES_JSON+=",\"data:${MIME};base64,${B64}\""
      fi
    fi
  done
  IMAGES_JSON+="]"
fi

# --- Determine aspectRatio parameter ---
if [[ "$MODEL" == gpt-image-2* ]]; then
  if [[ "$SIZE" =~ ^[0-9]+x[0-9]+$ ]]; then
    ASPECT="$SIZE"
  else
    ASPECT="$RATIO"
  fi
else
  ASPECT="$RATIO"
fi

REQUEST_BODY_FILE=$(mktemp)
IMAGES_JSON_FILE=$(mktemp)
trap 'rm -f "$REQUEST_BODY_FILE" "$IMAGES_JSON_FILE"' EXIT
printf '%s' "$IMAGES_JSON" > "$IMAGES_JSON_FILE"

# --- Build request body using python for safe JSON ---
python3 -c "
import json, sys

model = sys.argv[1]
prompt = sys.argv[2]
images_file = sys.argv[3]
aspect = sys.argv[4]
size = sys.argv[5]
async_mode = sys.argv[6]
quality = sys.argv[7]
output_file = sys.argv[8]

with open(images_file, 'r', encoding='utf-8') as f:
    images = json.load(f)

body = {
    'model': model,
    'prompt': prompt,
    'images': images,
    'aspectRatio': aspect,
    'replyType': 'async' if async_mode == 'true' else 'json',
    'quality': quality
}

# nano-banana series has imageSize param
if not model.startswith('gpt-image-2'):
    body['imageSize'] = size

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(body, f)
" "$MODEL" "$PROMPT" "$IMAGES_JSON_FILE" "$ASPECT" "$SIZE" "$ASYNC_MODE" "$QUALITY" "$REQUEST_BODY_FILE"

echo "Generating with model: $MODEL" >&2
echo "  Ratio: $ASPECT | Size: $SIZE" >&2
[[ -n "$REFS" ]] && echo "  References: $REFS" >&2

# --- Make API call ---
RESPONSE=$(curl -s -X POST "${BASE_URL}/v1/api/generate" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary "@${REQUEST_BODY_FILE}" \
  --max-time 1000)

# --- Check for errors ---
STATUS=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null || echo "")
ERROR=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error',''))" 2>/dev/null || echo "")

if [[ "$STATUS" == "failed" ]] || [[ "$STATUS" == "violation" ]]; then
  echo "Generation failed: $ERROR" >&2
  echo "$RESPONSE" >&2
  exit 1
fi

# --- Handle async mode ---
if [[ "$STATUS" == "running" ]]; then
  TASK_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  echo "Async task created: $TASK_ID" >&2
  echo "  Polling for result..." >&2

  for i in $(seq 1 "$POLL_ATTEMPTS"); do
    sleep "$POLL_INTERVAL"
    POLL=$(curl -s "${BASE_URL}/v1/api/result?id=${TASK_ID}" \
      -H "Authorization: Bearer ${API_KEY}")
    POLL_STATUS=$(echo "$POLL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")

    if [[ "$POLL_STATUS" == "succeeded" ]]; then
      RESPONSE="$POLL"
      break
    elif [[ "$POLL_STATUS" == "failed" ]] || [[ "$POLL_STATUS" == "violation" ]]; then
      echo "Async task failed: $(echo "$POLL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error',''))" 2>/dev/null)" >&2
      exit 1
    fi

    PROGRESS=$(echo "$POLL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('progress',0))" 2>/dev/null || echo "?")
    echo "  Progress: ${PROGRESS}% (attempt $i/$POLL_ATTEMPTS)" >&2
  done

  if [[ "$POLL_STATUS" != "succeeded" ]]; then
    WAITED=$((POLL_INTERVAL * POLL_ATTEMPTS))
    echo "Async task timed out after ${WAITED}s: ${TASK_ID}" >&2
    exit 1
  fi
fi

# --- Extract image URL ---
IMAGE_URL=$(python3 -c "
import sys, json
d = json.loads('''$RESPONSE''')
results = d.get('results', [])
if results:
    print(results[0].get('url', ''))
" 2>/dev/null || echo "")

if [[ -z "$IMAGE_URL" ]]; then
  echo "No image URL in response" >&2
  echo "$RESPONSE" >&2
  exit 1
fi

# --- Download image ---
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EXTENSION="${IMAGE_URL##*.}"
EXTENSION="${EXTENSION%%\?*}"
[[ "$EXTENSION" == "$IMAGE_URL" ]] && EXTENSION="png"
FILENAME="grsai_${TIMESTAMP}.${EXTENSION}"
OUTPUT_PATH="${OUTPUT_DIR}/${FILENAME}"

curl -s -o "$OUTPUT_PATH" "$IMAGE_URL" --max-time 60

if [[ ! -f "$OUTPUT_PATH" ]] || [[ ! -s "$OUTPUT_PATH" ]]; then
  echo "Failed to download image" >&2
  exit 1
fi

echo "$OUTPUT_PATH"
