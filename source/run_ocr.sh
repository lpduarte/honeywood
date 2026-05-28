#!/bin/bash
# Batch OCR all JP2 page scans via macOS Vision. Fault-tolerant: skips unreadable pages.
cd "$(dirname "$0")"
JP2DIR="jp2/2015.242964.The-Honey_jp2"
OUTDIR="ocr_text"
TMPDIR="/tmp/honeywood_png"
mkdir -p "$OUTDIR" "$TMPDIR"

count=0
skipped=0
for f in $(ls "$JP2DIR"/*.jp2 | sort); do
    base=$(basename "$f" .jp2)
    num=$(echo "$base" | grep -oE '[0-9]+$')
    [ -z "$num" ] && continue
    png="$TMPDIR/${num}.png"
    out="$OUTDIR/page_${num}.txt"
    # Skip if JP2 has no readable dimensions (corrupt/blank scanner pages)
    if ! sips -g pixelWidth "$f" >/dev/null 2>&1; then
        echo "SKIP $base (no dimensions)"; : > "$out"; skipped=$((skipped+1)); continue
    fi
    rm -f "$png"
    sips -s format png --resampleWidth 2000 "$f" --out "$png" >/dev/null 2>&1
    if [ ! -f "$png" ]; then
        echo "SKIP $base (convert failed)"; : > "$out"; skipped=$((skipped+1)); continue
    fi
    ./ocr_tool "$png" > "$out" 2>/dev/null || : > "$out"
    count=$((count+1))
    echo "[$count] $base -> $(wc -l < "$out" | tr -d ' ') lines"
done
echo "DONE: $count pages OCR'd, $skipped skipped, into $OUTDIR/"
