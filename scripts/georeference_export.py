"""Export the georeferencing of each supplied scene as a sidecar for the released mask.

The masks keep the grid of the scenes supplied by BBSDLP, so one transform serves both files.
Writes, per scene: <SCENE>_mask.tfw (world file), <SCENE>_mask.prj (WKT), and one combined
georeference.csv. Verifies first that the released mask has the same pixel dimensions as the
original scene; refuses otherwise.

Run:  uv run --with rasterio python scripts/georeference_export.py
"""
import csv
import sys
from pathlib import Path

import rasterio

SRC = Path(r"C:\Dropbox\01BinusS3\-BINUS S3\thesis SLP BBSDLP 2022 Onedrive\CITRA")
MASKS = Path(r"C:\Users\laptop-4800h\Desktop\figsharefile")          # released masks
OUT = Path(__file__).resolve().parent.parent                        # repository root
SCENES = ["BANGLI_SUSUT", "KULONPROGO_GALUR", "LEUWIDAMAR",
          "SITUBONDO_SITUBONDO", "Tangerang_Sepatan_Timur"]

rows, problems = [], []
for scene in SCENES:
    src = SRC / f"{scene}.tif"
    mask = MASKS / f"{scene}_mask.tif"
    if not src.exists() or not mask.exists():
        problems.append(f"{scene}: missing {'original' if not src.exists() else 'mask'}")
        continue
    with rasterio.open(src) as r, rasterio.open(mask) as m:
        if (r.width, r.height) != (m.width, m.height):
            problems.append(f"{scene}: grid mismatch {r.width}x{r.height} vs mask {m.width}x{m.height}")
            continue
        t, crs = r.transform, r.crs
        if crs is None:
            problems.append(f"{scene}: original carries no CRS")
            continue

        # world file: pixel size, rotation, rotation, pixel size, x/y of the TOP-LEFT PIXEL CENTRE
        (OUT / f"{scene}_mask.tfw").write_text(
            "\n".join(f"{v:.12f}" for v in
                      (t.a, t.d, t.b, t.e, t.c + t.a / 2, t.f + t.e / 2)) + "\n", encoding="utf-8")
        (OUT / f"{scene}_mask.prj").write_text(crs.to_wkt() + "\n", encoding="utf-8")
        # PAM sidecar: GDAL reads this for both CRS and transform, which a bare .prj does not give it.
        # The GeoTransform element is in GDAL's own order: topLeftX, xSize, xSkew, topLeftY, ySkew, ySize.
        (OUT / f"{scene}_mask.tif.aux.xml").write_text(
            "<PAMDataset>\n"
            f"  <SRS>{crs.to_wkt()}</SRS>\n"
            f"  <GeoTransform>{t.c}, {t.a}, {t.b}, {t.f}, {t.d}, {t.e}</GeoTransform>\n"
            "</PAMDataset>\n", encoding="utf-8")
        rows.append(dict(scene=scene, width=m.width, height=m.height, crs=crs.to_string(),
                         a=t.a, b=t.b, c=t.c, d=t.d, e=t.e, f=t.f,
                         upper_left_lon=t.c, upper_left_lat=t.f))

if problems:
    print("REFUSED:"); [print("  -", p) for p in problems]; sys.exit(1)

with (OUT / "georeference.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

# self-check: with the .tfw/.prj beside the mask, GDAL must derive the original transform
import shutil, tempfile
tmp = Path(tempfile.mkdtemp(prefix="georef_check_"))
for r in rows:
    sc = r["scene"]
    for suffix in ("_mask.tif", "_mask.tfw", "_mask.prj", "_mask.tif.aux.xml"):
        src = (MASKS / f"{sc}{suffix}") if suffix == "_mask.tif" else (OUT / f"{sc}{suffix}")
        shutil.copy(src, tmp / f"{sc}{suffix}")
    with rasterio.open(tmp / f"{sc}_mask.tif") as m:
        ok = (abs(m.transform.a - r["a"]) < 1e-12 and abs(m.transform.e - r["e"]) < 1e-12
              and abs(m.transform.c - r["c"]) < 1e-9 and abs(m.transform.f - r["f"]) < 1e-9
              and m.crs is not None)
    print(f"{'ok ' if ok else 'FAIL'} {sc:24s} {r['width']}x{r['height']}  "
          f"corner {r['upper_left_lon']:.5f}, {r['upper_left_lat']:.5f}  {r['crs']}")
    assert ok, f"{sc}: transform derived from the sidecar does not match the original"
shutil.rmtree(tmp)
print(f"\nwrote georeference.csv, 5 .tfw and 5 .prj into {OUT}")
