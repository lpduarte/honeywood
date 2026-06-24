#!/usr/bin/env python3
"""Shared imperial -> metric rough conversion, the sibling of money.py: shown in a small
"In metric" block under the money one, on both the email and the site. Approximate on
purpose — the point is to feel the scale of the peripeties (men disputing a ¼-inch step =
~6 mm), not surveying. Lengths (in/ft/yd), weights (lb/oz/cwt/ton), areas (sq ft)."""
import re

_FR = {'½': .5, '¼': .25, '¾': .75, '⅓': 1/3, '⅔': 2/3, '⅛': .125, '⅜': .375, '⅝': .625, '⅞': .875}
_FRC = ''.join(_FR)

def _num(s):
    """Parse '3', '3½', '½', '3 ¾' into a float (None if not a number)."""
    s = s.strip()
    m = re.fullmatch(r'(\d+)?\s*([%s])?' % _FRC, s)
    if not m or not (m.group(1) or m.group(2)):
        return None
    return (int(m.group(1)) if m.group(1) else 0) + (_FR[m.group(2)] if m.group(2) else 0)

def _len(inches):                                   # inches -> mm / cm / m
    mm = inches * 25.4
    if mm < 100:  return '≈%d mm' % round(mm)
    if mm < 1000: return '≈%d cm' % round(mm / 10)
    return '≈%g m' % round(mm / 1000, 2)

def _wt(g):                                          # grams -> g / kg
    if g < 1000: return '≈%d g' % (round(g, -1) if g >= 100 else round(g))
    return '≈%g kg' % round(g / 1000, 2)

def _area(sqft):
    return '≈%g m²' % round(sqft * 0.092903, 2)

def _sqft(g):
    """Square-feet value from an area-context match. "132 ft." -> 132; "12 ft. 10 in." (the
    book's muddled "12 5/6 superficial feet") -> 12 + 10/12."""
    toks = re.findall(r'\d+\s*[½¼¾⅓⅔⅛⅜⅝⅞]|\d+|[½¼¾⅓⅔⅛⅜⅝⅞]', g)
    if not toks:
        return None
    v = _num(toks[0]) or 0
    if len(toks) > 1 and re.search(r'in', g):
        v += (_num(toks[1]) or 0) / 12
    return v

# number token: a whole number, a fraction glyph, or whole+glyph ("1¼", "3 ¾", "½")
_N = r'(?:\d+\s*[%s]|\d+|[%s])' % (_FRC, _FRC)

# spelled-out numbers (for "four feet nine", "half an inch", "a foot"…)
_WN = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
       'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
       'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
       'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
       'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90, 'half': .5}
_W = '|'.join(sorted(_WN, key=len, reverse=True))
def _wn(w): return _WN.get(w.lower(), 0)

def _wnum(g):                                        # group that is a digit or a number word
    return int(g) if g.isdigit() else _wn(g)

_PASSES = [
    # --- area first, so "square feet" isn't grabbed as length ---
    (r'(\d+)\s*sq\.?\s*ft\.', lambda m: _area(int(m.group(1)))),          # 14 sq. ft.
    (r'\b(\d+|%s)\s+square\s+(?:feet|foot)\b' % _W, lambda m: _area(_wnum(m.group(1)))),
    (r'\b(\d+|%s)\s+square\s+inch(?:es)?\b' % _W, lambda m: '≈%g cm²' % round(_wnum(m.group(1)) * 6.4516, 1)),
    (r'\bsquare\s+(?:feet|foot)\b', lambda m: _area(1)),
    (r'\bsquare\s+inch(?:es)?\b', lambda m: '≈6.5 cm²'),
    # --- length, abbreviations (space- or hyphen-joined) ---
    (r'(%s)[\s-]*ft\.\s*(%s)[\s-]*ins?\.' % (_N, _N),                     # 3 ft. 6 in.
     lambda m: _len((_num(m.group(1)) or 0) * 12 + (_num(m.group(2)) or 0))),
    (r'(%s)[\s-]*ft\.' % _N, lambda m: _len((_num(m.group(1)) or 0) * 12)),  # 8 ft. / 4-ft.
    (r'(%s)[\s-]*ins?\.' % _N, lambda m: _len(_num(m.group(1)) or 0)),       # ½ in. / 2-in.
    # --- length, unit spelled as a word (½ inch, 4-inch, 9 feet, 11½ feet, 6-foot) ---
    (r'\b(%s)\s+feet\s+(%s)(?:\s+inch(?:es)?)?\b' % (_W, _W),             # four feet nine [inches]
     lambda m: _len(_wn(m.group(1)) * 12 + _wn(m.group(2)))),
    (r'(%s)[\s-]*feet\b' % _N, lambda m: _len((_num(m.group(1)) or 0) * 12)),   # 15 feet / 11½ feet
    (r'(%s)[\s-]*foot\b' % _N, lambda m: _len((_num(m.group(1)) or 0) * 12)),   # 6-foot
    (r'\b(%s)\s+feet\b' % _W, lambda m: _len(_wn(m.group(1)) * 12)),      # five feet, twenty feet
    (r'\b(an?|one)\s+foot\b', lambda m: _len(12)),                        # a foot
    (r'(%s)[\s-]*inch(?:es)?\b' % _N, lambda m: _len(_num(m.group(1)) or 0)),   # ½ inch / 4-inch
    (r'\b(%s)\s+inch(?:es)?\b' % _W, lambda m: _len(_wn(m.group(1)))),    # twelve inches
    (r'\bhalf\s+an?\s+inch\b', lambda m: _len(.5)),
    (r'\bthree[-\s]quarters?\s+of\s+an?\s+inch\b', lambda m: _len(.75)),
    (r'\ba\s+quarter\s+of\s+an?\s+inch\b', lambda m: _len(.25)),
    # --- yards / distances ---
    (r'(%s)\s*(?:yds?\.|yards?\b)' % _N, lambda m: _len((_num(m.group(1)) or 0) * 36)),  # 320 yds.
    (r'\b(%s)\s+hundred\s+(?:yards?|feet|foot)\b' % _W,                   # three hundred yards
     lambda m: _len(_wn(m.group(1)) * 100 * (36 if 'yard' in m.group(0).lower() else 12))),
    (r'\b(%s)\s+yards?\b' % _W, lambda m: _len(_wn(m.group(1)) * 36)),    # a yard, ten yards
    # --- weight (NB: bare "pounds" is money, not weight, so only "a pound of") ---
    (r'(\d+)\s*lb\.', lambda m: _wt(int(m.group(1)) * 453.6)),
    (r'(\d+)\s*oz\.', lambda m: _wt(int(m.group(1)) * 28.35)),
    (r'(\d+)\s*cwt\.', lambda m: _wt(int(m.group(1)) * 50800)),
    (r'(\d+)\s*tons?\b', lambda m: '≈%g t' % round(int(m.group(1)) * 1.016, 2)),
    (r'\ba pound of\b', lambda m: _wt(453.6)),                            # "a pound of putty"
]

def find(text):
    """[(start, end, original, metric)] for each measurement, in document order, non-overlapping."""
    out, used = [], []
    for pat, conv in _PASSES:
        for m in re.finditer(pat, text, re.IGNORECASE):   # catch sentence-initial "Four feet nine"
            sp = m.span()
            if any(not (sp[1] <= s or sp[0] >= e) for s, e in used):  # overlaps an earlier match
                continue
            # The window-area sub-plot writes AREA as plain feet ("14 ft. super", "window area
            # is 14 ft.", "makes 15 feet") — never convert those as length.
            # The window-area sub-plot writes AREA in feet ("14 ft. super", "= 132 ft.",
            # "12 feet superficial"). Convert those as area (m²) — never as length, and never
            # leave them imperial (a stray "132 ft." amid metric reads as an escape).
            g = m.group(0)
            pre, post = text[:sp[0]], text[sp[1]:sp[1] + 30]
            is_feet = re.search(r'ft\.|feet|foot', g)
            bare_feet = is_feet and not re.search(r'ins?\b|inch', g)
            calc_result = pre.rstrip().endswith(('=', 'makes'))      # "A × B = 132 ft."
            area_ctx = bare_feet and (re.search(r'square|super', post) or
                                      re.search(r'square|super|\barea\b', pre[-60:]))
            if is_feet and (calc_result or area_ctx):
                v = _sqft(g)
                if v is not None:
                    end = sp[1]
                    sup = re.match(r'\s+(?:superficial(?:ly)?|super)\b', text[end:end + 14])
                    if sup:                       # "14 ft. super" -> "1.3 m²" (drop the leftover word)
                        end += sup.end()
                    used.append((sp[0], end)); out.append((sp[0], end, text[sp[0]:end], _area(v)))
                continue
            try:
                metric = conv(m)
            except Exception:
                metric = None
            if metric:
                used.append(sp); out.append((sp[0], sp[1], m.group(0), metric))
    out.sort()
    return out

# A passage that NAMES the imperial area unit ("12 feet superficial", "a superficial foot",
# "12 5/6 feet super") is explaining the imperial system itself — listing its figures in the
# metric block is noise (and would garble), so the renderers skip such a note. Only the
# editor's window-area note does this.
_EXPLAINS_IMPERIAL = re.compile(r'feet super|superficial (?:foot|feet|inch)|feet superficial', re.I)

def rows(text):
    """[(original measurement, metric string)] for each distinct measurement in the text."""
    seen, res = set(), []
    for _s, _e, orig, met in find(text):
        label = re.sub(r'\s+', ' ', orig).strip()
        if label not in seen:
            seen.add(label); res.append((label, met))
    return res

if __name__ == '__main__':
    for t in ['½ in.', '1¼ in.', '3 ft. 6 in.', '8 ft.', '3¾ in.', '2 ft. 9½ ins.',
              'a pound of putty', '14 sq. ft.', '10 ft. 9 in. × 12 ft.']:
        print('%-22s %s' % (t, rows(t)))
