#!/usr/bin/env python3
"""Straighten bowed text lines in a single-column book-page crop.

Photos of a bound book curve near the gutter: text lines bow, so an OCR
engine's line grouping breaks and fragments from lower in the column get
pulled into earlier paragraphs. Perspective correction does not fix this --
the distortion is a curl, not a plane.

Method (per column crop, so the bow is close to a pure vertical shift):
  1. binarize to ink, build the column's global row-ink profile
  2. cut the column into vertical slices; for each, find the integer y-shift
     that best aligns its own row profile with the global one
  3. smooth the shifts across slices, interpolate to per-x, and remap

Correlation is scored on mean-centred profiles so a slice with more ink
than average doesn't win by sheer magnitude. Slices with almost no ink
inherit their neighbours' shift rather than voting with noise.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def row_profile(ink: np.ndarray) -> np.ndarray:
    return ink.sum(axis=1).astype(np.float32)


def line_pitch(ref: np.ndarray, lo: int = 20, hi: int = 200) -> int:
    """Dominant text-line spacing, via autocorrelation of the row profile.

    Body text is periodic, so a shift search wider than the pitch will happily
    align line N onto line N+1 -- a perfect-looking correlation that shears the
    column by a whole line. Callers clamp their search to a fraction of this.
    """
    r = ref - ref.mean()
    n = len(r)
    hi = min(hi, n // 3)
    if hi <= lo:
        return 0
    best_lag, best_v = 0, -np.inf
    for lag in range(lo, hi):
        v = float(np.dot(r[lag:], r[: n - lag]) / (n - lag))
        if v > best_v:
            best_lag, best_v = lag, v
    return best_lag


def best_shift(prof: np.ndarray, ref: np.ndarray, max_shift: int) -> int:
    """y-shift maximising correlation of prof against ref, in [-max, +max]."""
    p = prof - prof.mean()
    r = ref - ref.mean()
    n = len(r)
    best_s, best_v = 0, -np.inf
    for s in range(-max_shift, max_shift + 1):
        if s >= 0:
            a, b = p[s:], r[: n - s]
        else:
            a, b = p[: n + s], r[-s:]
        if len(a) < n // 2:
            continue
        v = float(np.dot(a, b) / (len(a) or 1))
        if v > best_v:
            best_s, best_v = s, v
    return best_s


def estimate_shifts(gray: np.ndarray, ink_thresh: int, slices: int,
                    max_shift: int, min_ink: float):
    ink = (gray < ink_thresh).astype(np.float32)
    ref = row_profile(ink)
    pitch = line_pitch(ref)
    if pitch:
        max_shift = min(max_shift, max(2, int(pitch * 0.4)))
    w = gray.shape[1]
    edges = np.linspace(0, w, slices + 1).astype(int)

    shifts, centres, valid = [], [], []
    for i in range(slices):
        x0, x1 = edges[i], edges[i + 1]
        if x1 <= x0:
            continue
        sl = ink[:, x0:x1]
        centres.append((x0 + x1) / 2.0)
        if sl.mean() < min_ink:
            shifts.append(0.0)
            valid.append(False)
            continue
        shifts.append(float(best_shift(row_profile(sl), ref, max_shift)))
        valid.append(True)

    shifts = np.array(shifts, dtype=np.float32)
    centres = np.array(centres, dtype=np.float32)
    valid = np.array(valid, dtype=bool)
    if valid.sum() >= 2:
        # ink-poor slices carry no signal -- interpolate them from real ones
        shifts = np.interp(centres, centres[valid], shifts[valid])
    return centres, shifts


def smooth(vals: np.ndarray, k: int) -> np.ndarray:
    if k < 2 or len(vals) < k:
        return vals
    pad = k // 2
    padded = np.pad(vals, pad, mode="edge")
    kern = np.ones(k, dtype=np.float32) / k
    return np.convolve(padded, kern, mode="same")[pad: pad + len(vals)]


def apply_shifts(img: Image.Image, centres, shifts) -> Image.Image:
    arr = np.asarray(img)
    h, w = arr.shape[:2]
    per_x = np.interp(np.arange(w), centres, shifts)
    out = np.empty_like(arr)
    for x in range(w):
        s = int(round(per_x[x]))
        col = arr[:, x]
        if s == 0:
            out[:, x] = col
        elif s > 0:
            out[: h - s, x] = col[s:]
            out[h - s:, x] = col[-1]
        else:
            s = -s
            out[s:, x] = col[: h - s]
            out[:s, x] = col[0]
    return Image.fromarray(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--ink-thresh", type=int, default=140)
    ap.add_argument("--slices", type=int, default=24)
    ap.add_argument("--max-shift", type=int, default=60)
    ap.add_argument("--smooth", type=int, default=5)
    ap.add_argument("--min-ink", type=float, default=0.01)
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for path in sorted(a.images):
        p = Path(path)
        if not p.exists():
            sys.exit(f"not found: {p}")
        img = Image.open(p).convert("RGB")
        gray = np.asarray(img.convert("L"))

        centres, shifts = estimate_shifts(gray, a.ink_thresh, a.slices,
                                          a.max_shift, a.min_ink)
        if len(centres) == 0:
            img.save(outdir / p.name)
            print(f"[dewarp] {p.name}: no slices, copied")
            continue
        shifts = smooth(shifts, a.smooth)
        apply_shifts(img, centres, shifts).save(outdir / p.name)
        print(f"[dewarp] {p.name}: shift range "
              f"{shifts.min():+.0f}..{shifts.max():+.0f}px")


if __name__ == "__main__":
    main()
