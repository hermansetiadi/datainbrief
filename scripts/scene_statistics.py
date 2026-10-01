"""Recompute scene_statistics.csv from the published *_raw.tif / *_mask.tif files.

usage: python scene_statistics.py <folder with the .tif files> [out.csv]
Valid pixel = none of the three bands equals 65536. Reads 512 rows at a time.
"""
import csv, sys
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window

folder = Path(sys.argv[1])
out = sys.argv[2] if len(sys.argv) > 2 else "scene_statistics.csv"
NODATA, ROWS = 65536, 512
rows = []
for raw in sorted(folder.glob("*_raw.tif")):
    scene = raw.name.removesuffix("_raw.tif")
    with rasterio.open(raw) as r, rasterio.open(folder / f"{scene}_mask.tif") as m:
        valid = paddy = paddy_on_nodata = 0
        bmin, bmax, bsum, bsq = [sys.maxsize] * 3, [0] * 3, [0] * 3, [0] * 3
        for r0 in range(0, r.height, ROWS):
            w = Window(0, r0, r.width, min(ROWS, r.height - r0))
            a, p = r.read(window=w), m.read(1, window=w) == 255
            ok = (a != NODATA).all(axis=0)
            valid += int(ok.sum()); paddy += int((p & ok).sum()); paddy_on_nodata += int((p & ~ok).sum())
            for b in range(3):
                v = a[b][ok]
                if v.size:
                    bmin[b] = min(bmin[b], int(v.min())); bmax[b] = max(bmax[b], int(v.max()))
                    bsum[b] += int(v.sum(dtype=np.uint64)); bsq[b] += int((v.astype(np.uint64) ** 2).sum())
        total = r.width * r.height
        row = {"scene": scene, "width_px": r.width, "height_px": r.height, "total_px": total,
               "valid_px": valid, "valid_pct": round(100 * valid / total, 2),
               "paddy_px": paddy, "paddy_pct_of_valid": round(100 * paddy / valid, 2),
               "paddy_px_on_nodata": paddy_on_nodata}
        for b in range(3):
            mean = bsum[b] / valid
            row |= {f"b{b+1}_min": bmin[b], f"b{b+1}_max": bmax[b], f"b{b+1}_mean": round(mean, 2),
                    f"b{b+1}_std": round((bsq[b] / valid - mean ** 2) ** 0.5, 2)}
        rows.append(row)
        print(scene, "done", flush=True)

with open(out, "w", newline="") as fh:
    wr = csv.DictWriter(fh, fieldnames=rows[0].keys()); wr.writeheader(); wr.writerows(rows)
