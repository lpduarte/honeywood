#!/usr/bin/env python3
"""Rebuild honeywood_full.txt from the clean Vision OCR output (ocr_text/page_NNNN.txt)."""
import re, glob
from pathlib import Path

files = sorted(glob.glob('ocr_text/page_*.txt'), key=lambda x: int(re.search(r'page_(\d+)', x).group(1)))
out = []
for f in files:
    num = int(re.search(r'page_(\d+)', f).group(1))
    txt = Path(f).read_text(encoding='utf-8').strip()
    out.append(f'\n\n<<<PAGE {num}>>>\n\n{txt}')

full = ''.join(out)
Path('honeywood_full.txt').write_text(full, encoding='utf-8')
print(f"Rebuilt honeywood_full.txt: {len(full):,} chars from {len(files)} pages")
