"""Shared £(1924-26) -> € (today) rough conversion, used by both the email and the site.

The figures are approximate: a single cumulative UK inflation factor per book year and a
GBP->EUR rate. The point is the sense of scale ("a whole house for £18,000"), not accountancy.
Tune INFL / FX in one place and both surfaces follow.
"""
import re, math

INFL = {1924: 80.0, 1925: 80.0, 1926: 81.0}   # GBP cumulative to ~2026 (approx)
FX = 1.16                                       # GBP -> EUR (approx)

_AMT = re.compile(
    r'£\s?([\d,]+)(?:\s*(\d+)\s*s\.)?(?:\s*(\d+)\s*d\.)?'   # £ amount (+ optional s./d.)
    r'|(\d+)\s*s\.(?:\s*(\d+)\s*d\.)?'                      # bare shillings (+ optional pence)
    r'|(\d+)\s*d\.'                                          # bare pence
)


def euro(v):
    if v <= 0:
        return "€0"
    d = int(math.floor(math.log10(v)))
    r = round(v, -(d - 2))                      # 3 significant figures
    return "€" + format(int(r), ",")


def rows(body, year):
    """[(original £ label, € string)] for each distinct £ amount found in the text."""
    seen = set()
    out = []
    for m in _AMT.finditer(body):
        label = m.group(0).strip().rstrip(',')
        if label in seen:
            continue
        seen.add(label)
        if m.group(1) is not None:                  # £ amount
            p = int(m.group(1).replace(',', ''))
            s = int(m.group(2)) if m.group(2) else 0
            d = int(m.group(3)) if m.group(3) else 0
        elif m.group(4) is not None:                # bare shillings (+ pence)
            p = 0
            s = int(m.group(4))
            d = int(m.group(5)) if m.group(5) else 0
        else:                                        # bare pence
            p = 0
            s = 0
            d = int(m.group(6))
        pounds = p + s / 20 + d / 240
        out.append((label, euro(pounds * INFL.get(year, 80.0) * FX)))
    return out
