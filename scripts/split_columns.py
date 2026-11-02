#!/usr/bin/env python3
"""Cut book-spread photos into single text columns, in reading order.

Both OCR engines interleave these pages because each photo is a two-page
spread and every page is double-column. Neither dewarping nor a text-level
merge fixes that -- the fix is to hand the OCR engine one column at a time.

Column finding is a vertical ink-projection: threshold to ink, sum per x,
smooth, then treat sustained low-ink runs as gutters. Strips narrower than
--min-width or with almost no ink are dropped (margins, desk background).
Output names sort in reading order: <stem>_c01.png, _c02.png, ...
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def find_columns(gray: np.ndarray, ink_thresh: int, min_width: int,
                 gutter_frac: float, smooth: int):
    ink = (gray < ink_thresh).astype(np.float32)
    prof = ink.mean(axis=0)
    if smooth > 1:
        k = np.ones(smooth) / smooth
        prof = np.convolve(prof, k, mode="same")

    peak = float(prof.max())
    if peak <= 0:
        return []
    is_text = prof > (peak * gutter_frac)

    spans, start = [], None
    for x, t in enumerate(is_text):
        if t and start is None:
            start = x
        elif not t and start is not None:
            spans.append((start, x))
            start = None
    if start is not None:
        spans.append((start, len(is_text)))

    spans = [(a, b) for a, b in spans if (b - a) >= min_width]
    return subdivide_wide(spans)


def subdivide_wide(spans, ratio=1.5):
    """Cut spans that are really N columns fused together.

    A page whose inner gutter is bridged by a figure has no full-height
    whitespace, so the projection sees one wide span. Columns in a given book
    are near-equal width, so compare against the median and split evenly.
    """
    if len(spans) < 2:
        return spans
    widths = sorted(b - a for a, b in spans)
    med = widths[len(widths) // 2]
    out = []
    for a, b in spans:
        n = int(round((b - a) / med))
        if (b - a) > med * ratio and n >= 2:
            step = (b - a) / n
            for k in range(n):
                out.append((int(a + k * step), int(a + (k + 1) * step)))
        else:
            out.append((a, b))
    return out


def crop_rows(col: np.ndarray, ink_thresh: int, pad: int):
    """Trim blank top/bottom so a strip is tight on its text."""
    ink = (col < ink_thresh)
    rows = np.where(ink.any(axis=1))[0]
    if rows.size == 0:
        return None
    y0 = max(0, rows[0] - pad)
    y1 = min(col.shape[0], rows[-1] + pad)
    return y0, y1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--ink-thresh", type=int, default=140)
    ap.add_argument("--min-width", type=int, default=350)
    ap.add_argument("--gutter-frac", type=float, default=0.12)
    ap.add_argument("--smooth", type=int, default=41)
    ap.add_argument("--pad", type=int, default=20)
    ap.add_argument("--min-ink", type=float, default=0.01)
    ap.add_argument("--force-cols", type=int, default=0,
                    help="cut every detected span into N equal parts "
                         "(for spreads where both pages fuse their gutter)")
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for path in sorted(a.images):
        p = Path(path)
        if not p.exists():
            sys.exit(f"not found: {p}")
        img = Image.open(p).convert("RGB")
        gray = np.asarray(img.convert("L"))

        spans = find_columns(gray, a.ink_thresh, a.min_width,
                             a.gutter_frac, a.smooth)
        if a.force_cols > 1:
            forced = []
            for x0, x1 in spans:
                step = (x1 - x0) / a.force_cols
                forced += [(int(x0 + k * step), int(x0 + (k + 1) * step))
                           for k in range(a.force_cols)]
            spans = forced
        kept = 0
        for x0, x1 in spans:
            strip_gray = gray[:, x0:x1]
            frac = float((strip_gray < a.ink_thresh).mean())
            if frac < a.min_ink:
                continue
            rows = crop_rows(strip_gray, a.ink_thresh, a.pad)
            if rows is None:
                continue
            y0, y1 = rows
            kept += 1
            out = outdir / f"{p.stem}_c{kept:02d}.png"
            img.crop((x0, y0, x1, y1)).save(out)
        widths = [b - a_ for a_, b in spans]
        print(f"[cols] {p.name}: {kept} columns kept, widths={widths}")


if __name__ == "__main__":
    main()
