"""Per-pixel label-agreement raster for each scene, on the same grid as the released masks.

One uint8 GTiff per scene, codes:
    0 = no parcel record (unmapped)
    1 = A  paddy (KDKOMO 1) inside LBS 2019
    2 = B  sugarcane (KDKOMO 2) inside LBS
    3 = B  Lain-lain (KDKOMO 11) inside LBS
    4 = B  other class (KDKOMO 3-10) inside LBS
    5 = C  paddy outside LBS
    6 = mapped non-paddy outside LBS (outside the comparison domain)
Pixel-centre rule (all_touched=False), the same rule that made the masks. Writes the rasters and
their georeferencing sidecars to the output folder, and agreement_codes.csv into the repository.

Run:  uv run --with rasterio --with geopandas --with shapely --with numpy python scripts/agreement_raster.py [SCENE ...]
"""
import csv
import math
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.errors import NotGeoreferencedWarning
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.windows import Window, transform as win_transform
from shapely import force_2d, make_valid

warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)

MASKS = Path(r"C:\Users\laptop-4800h\Desktop\figsharefile")
BASE = Path(r"C:\Dropbox\01BinusS3\-BINUS S3\thesis SLP BBSDLP 2022 Onedrive\saveall\all")
OUTDIR = Path(r"C:\Users\laptop-4800h\Desktop\paper ketiga\agreement_out")
REPO = Path(__file__).resolve().parent.parent
CHUNK = 4096
NAMES = {0: "unmapped", 1: "A paddy in LBS", 2: "B sugarcane in LBS", 3: "B Lain-lain in LBS",
         4: "B other class in LBS", 5: "C paddy outside LBS", 6: "mapped non-paddy outside LBS"}

PARCELS = {
    "BANGLI_SUSUT":            "PETAK LAHAN — PETAK_LAHAN_BALI_BANGLI_SUSUT.gpkg",
    "KULONPROGO_GALUR":        "PETAK LAHAN — PETAK_LAHAN_DIY_KULONPROGO_GALUR.gpkg",
    "LEUWIDAMAR":              "PETAK LAHAN — PETAK_LAHAN_BANTEN_LEBAK_LEUWIDAMAR.gpkg",
    "SITUBONDO_SITUBONDO":     "PETAK LAHAN — PETAK_LAHAN_JAWATIMUR_SITUBONDO_SITUBONDO.gpkg",
    "Tangerang_Sepatan_Timur": "PETAK LAHAN — PETAK_LAHAN_BANTEN_TANGERANG_SEPATAN_TIMUR.gpkg",
}


def build(scene):
    parcels = gpd.read_file(BASE / PARCELS[scene], engine="pyogrio").to_crs("EPSG:4326")
    parcels = parcels.set_geometry(parcels.geometry.map(lambda g: make_valid(force_2d(g))))
    kd = parcels["KDKOMO"].astype("float")
    shapes = [(g, 12 if np.isnan(k) else int(k)) for g, k in zip(parcels.geometry, kd)]
    nan_parcels = int(np.isnan(kd).sum())

    # the masks carry no transform of their own, so rasterize against the scene's real grid
    geo = {r["scene"]: r for r in csv.DictReader((REPO / "georeference.csv").open(encoding="utf-8"))}[scene]
    scene_affine = Affine(*(float(geo[k]) for k in "abcdef"))

    with rasterio.open(MASKS / f"{scene}_mask.tif") as m:
        prof, H, W = m.profile, m.height, m.width
    prof.update(count=1, dtype="uint8", compress="lzw", tiled=True,
                blockxsize=128, blockysize=128, nodata=None)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / f"{scene}_agreement.tif"
    counts = np.zeros(7, "int64")
    lbs_px = lbs_covered = 0
    with rasterio.open(out, "w", **prof) as dst:
        for row in range(0, H, CHUNK):
            h = min(CHUNK, H - row)
            win = Window(0, row, W, h)
            wt = win_transform(win, scene_affine)
            with rasterio.open(MASKS / f"{scene}_mask.tif") as m:
                lbs = m.read(1, window=win) == 255
            k = rasterize(shapes, out_shape=(h, W), transform=wt, fill=0,
                          dtype="uint8", all_touched=False)
            arr = np.zeros((h, W), "uint8")
            kd_in = np.where(k == 12, 4, k)          # unclassed parcels count as other
            arr[(k > 0) & ~lbs] = 6                  # mapped land outside the baseline
            arr[(k > 0) & ~lbs & (k == 1)] = 5       # C: paddy outside wins over 6
            arr[lbs & (kd_in >= 3) & (kd_in <= 10)] = 4   # B: dry field, mixed garden, settlement...
            arr[lbs & (kd_in == 11)] = 3             # B: Lain-lain
            arr[lbs & (kd_in == 2)] = 2              # B: sugarcane
            arr[lbs & (k == 1)] = 1                  # A wins overlaps
            assert not (lbs & (arr > 4)).any(), f"{scene}: code outside 0-4 on an LBS pixel"
            dst.write(arr, 1, window=win)
            counts += np.bincount(arr.ravel(), minlength=7)
            lbs_px += int(lbs.sum())
            lbs_covered += int((lbs & (arr > 0)).sum())

    # LBS pixels are painted only by the inside rules, so the mapped share must agree with the
    # polygon audit (~100%); a large gap would mean the mask and the parcel layer disagree
    mapped_pct = 100 * lbs_covered / lbs_px
    assert mapped_pct > 98, f"{scene}: only {mapped_pct:.2f}% of LBS pixels carry a parcel record"
    assert counts[1] > 0, f"{scene}: no A pixels"
    assert counts[2] + counts[3] + counts[4] > 0, f"{scene}: no B pixels"
    assert counts[5] + counts[6] > 0, f"{scene}: no parcel mapped outside LBS"

    # cross-check against the published polygon component areas: raster code counts scaled by the
    # local pixel area are the only thing that catches a mis-mapped class code
    ref = {r["scene"]: r for r in
           csv.DictReader((REPO / "label_agreement_matrix.csv").open(encoding="utf-8"))}[scene]
    px_m2 = (float(geo["a"]) * 111320 * math.cos(math.radians(float(geo["f"])))) \
        * (abs(float(geo["e"])) * 110574)
    for label, raster_ha, ref_ha in (
            ("A", counts[1] * px_m2 / 1e4, float(ref["paddy_in_lbs_ha"])),
            ("B", (counts[2] + counts[3] + counts[4]) * px_m2 / 1e4, float(ref["other_in_lbs_ha"])),
            ("C", counts[5] * px_m2 / 1e4, float(ref["paddy_outside_lbs_ha"]))):
        assert abs(raster_ha - ref_ha) <= 0.05 * ref_ha, \
            f"{scene}: raster {label} {raster_ha:.1f} ha vs published {ref_ha:.1f} ha"

    # sidecars: same transform as the mask, because the grid is the same
    r = geo
    a, b, c, d, e, f = (float(r[k]) for k in "abcdef")
    (OUTDIR / f"{scene}_agreement.tfw").write_text(
        "\n".join(f"{v:.12f}" for v in (a, d, b, e, c + a / 2, f + e / 2)) + "\n", encoding="utf-8")
    (OUTDIR / f"{scene}_agreement.prj").write_text(
        rasterio.crs.CRS.from_string(r["crs"]).to_wkt() + "\n", encoding="utf-8")
    (OUTDIR / f"{scene}_agreement.tif.aux.xml").write_text(
        "<PAMDataset>\n"
        f"  <SRS>{rasterio.crs.CRS.from_string(r['crs']).to_wkt()}</SRS>\n"
        f"  <GeoTransform>{c}, {a}, {b}, {f}, {d}, {e}</GeoTransform>\n"
        "</PAMDataset>\n", encoding="utf-8")

    total = counts.sum()
    print(f"{scene:24s} mapped {mapped_pct:6.2f}% of LBS | " +
          " ".join(f"{NAMES[i]}={counts[i]/total:7.3%}" for i in range(7)))
    return [dict(scene=scene, code=i, name=NAMES[i], pixels=int(counts[i]),
                 pct_of_grid=round(100 * counts[i] / total, 3), unclassed_parcels=nan_parcels)
            for i in range(7)] + [dict(scene=scene, code=-1, name="LBS mapped by parcels (raster)",
                                       pixels=int(lbs_covered), pct_of_grid=round(mapped_pct, 3),
                                       unclassed_parcels=nan_parcels)]


if __name__ == "__main__":
    wanted = sys.argv[1:] or list(PARCELS)
    rows = [r for s in wanted for r in build(s)]
    if len(wanted) > 1:
        out = REPO / "agreement_codes.csv"
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"\nwrote {out}")
