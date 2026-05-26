#!/usr/bin/env bash
# Stub generate.sh for integration testing.
# Writes a minimal JPEG file to the --output directory and prints its path.

OUTPUT_DIR=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output) OUTPUT_DIR="$2"; shift 2 ;;
        *) shift ;;
    esac
done

mkdir -p "$OUTPUT_DIR"
OUT_FILE="$OUTPUT_DIR/grsai_stub.jpeg"

# Minimal valid JPEG: SOI + APP0 + EOI
printf '\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9' > "$OUT_FILE"

echo "$OUT_FILE"
