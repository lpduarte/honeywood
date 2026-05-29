#!/usr/bin/env python3
"""Procedurally generate the site/email image assets into ./assets (run once; PNGs are committed).

  pattern.png       transparent floral tile (light bg)        — also hosted for the email
  pattern_dark.png  same tile, very faint (dark bg)
  ring.png          wax seal ring (annulus)
  dots.png          wax floral motif (centre + 4 petals)
  prev.png/next.png wax 3-dot chevrons (the seal minus 2 dots)
All wax marks share one canvas/scale so ring + dots/chevron compose cleanly.
"""
import zlib, struct, math, random
from pathlib import Path

OUT = Path(__file__).parent.parent / 'assets'
OUT.mkdir(exist_ok=True)
OX = (130, 59, 47)   # oxblood sealing wax

def png_rgba(path, w, h, rows):
    raw = bytearray()
    for r in rows: raw.append(0); raw.extend(r)
    def ch(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + ch(b'IDAT', zlib.compress(bytes(raw), 9)) + ch(b'IEND', b''))

# ---- floral background tile (transparent) ----
def make_pattern(path, rgb, alpha):
    SC = 2; CELL = 48 * SC; S = CELL; BUD = 2.0 * SC; PET = 2.4 * SC; OFF = 5.0 * SC
    def cover(ox, oy, ss=4):
        h = 0
        for sy in range(ss):
            for sx in range(ss):
                x = ox + (sx + .5) / ss; y = oy + (sy + .5) / ss; hit = False
                for px, py in [(0, 0), (CELL, 0), (0, CELL), (CELL, CELL), (CELL / 2, CELL / 2)]:
                    for wx in (0, -S, S):
                        for wy in (0, -S, S):
                            dx = x - (px + wx); dy = y - (py + wy)
                            if dx * dx + dy * dy <= BUD * BUD: hit = True; break
                            if any((dx - a) ** 2 + (dy - b) ** 2 <= PET * PET for a, b in ((0, -OFF), (0, OFF), (-OFF, 0), (OFF, 0))): hit = True; break
                        if hit: break
                    if hit: break
                if hit: h += 1
        return h / (ss * ss)
    tile = [[(rgb[0], rgb[1], rgb[2], round(cover(ox, oy) * alpha * 255)) for ox in range(S)] for oy in range(S)]
    N = 4; W = S * N; rows = []
    for y in range(W):
        src = tile[y % S]; r = bytearray()
        for x in range(W): r += bytes(src[x % S])
        rows.append(r)
    png_rgba(path, W, W, rows)

# ---- wax marks (ring / dots / chevrons) ----
N = 128; C = 64
def _noise(seed):
    random.seed(seed); g = [[random.random() for _ in range(20)] for _ in range(20)]
    def s(x, y):
        fx = x / N * 19; fy = y / N * 19; ix = int(fx); iy = int(fy); tx = fx - ix; ty = fy - iy
        a = g[iy][ix] * (1 - tx) + g[iy][ix + 1] * tx
        b = g[iy + 1][ix] * (1 - tx) + g[iy + 1][ix + 1] * tx
        return a * (1 - ty) + b * ty
    return s
def wax(path, inside, seed=7, distress=0.45, speckle=0.06):
    nf = _noise(seed); random.seed(seed * 3)
    spk = [[random.random() for _ in range(N)] for _ in range(N)]
    rows = []
    for y in range(N):
        row = bytearray()
        for x in range(N):
            cov = sum(1 for a in range(3) for b in range(3) if inside(x + (a + .5) / 3, y + (b + .5) / 3)) / 9
            al = cov * 0.92
            if al > 0:
                al *= (1 - distress) + distress * nf(x, y) * 1.3
                if spk[y][x] < speckle: al = 0
            row += bytes((OX[0], OX[1], OX[2], max(0, min(255, round(al * 255)))))
        rows.append(row)
    png_rgba(path, N, N, rows)

OFF = 23; PET = 12; BUD = 8; ROUT = 60; RIN = 53
def _dot(x, y, pts, r=PET): return any((x - dx) ** 2 + (y - dy) ** 2 <= r * r for dx, dy in pts)

if __name__ == '__main__':
    make_pattern(OUT / 'pattern.png', (214, 198, 158), 0.40)
    make_pattern(OUT / 'pattern_dark.png', (224, 214, 190), 0.07)
    wax(OUT / 'ring.png', lambda x, y: RIN <= math.hypot(x - C, y - C) <= ROUT)
    wax(OUT / 'dots.png', lambda x, y: ((x - C) ** 2 + (y - C) ** 2 <= BUD * BUD) or _dot(x, y, [(C, C - OFF), (C, C + OFF), (C - OFF, C), (C + OFF, C)]))
    wax(OUT / 'prev.png', lambda x, y: _dot(x, y, [(C, C - OFF), (C, C + OFF), (C - OFF, C)]))
    wax(OUT / 'next.png', lambda x, y: _dot(x, y, [(C, C - OFF), (C, C + OFF), (C + OFF, C)]))
    print("assets written to", OUT)
