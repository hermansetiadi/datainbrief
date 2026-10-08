"""Per-scene audit: how much of the LBS footprint the 2022 parcel inventory actually maps.

Answers the reviewer's two questions with numbers instead of an [AUTHOR CHECK]:
  (a) mapped-LBS / LBS per scene, and whether unmapped LBS area was silently counted as paddy;
  (b) how much parcel area overlaps other parcels inside LBS (double counting in the sums).

Reads the BBSDLP vectors from the survey folder, works in ESRI:54034 (the projection the
manuscript states), writes lbs_coverage.csv. Run:
    uv run --with geopandas --with shapely python scripts/lbs_coverage.py [SCENE ...]
"""
import csv
import sys
from pathlib import Path

import geopandas as gpd
from shapely import force_2d, make_valid
from shapely.ops import unary_union

BASE = Path(r"C:\Dropbox\01BinusS3\-BINUS S3\thesis SLP BBSDLP 2022 Onedrive\saveall\all")
OUT = Path(__file__).resolve().parent.parent
CRS_CEA = "ESRI:54034"
HA = 1e4

SCENES = {
    "BANGLI_SUSUT":            ("LBS_BALI_BANGLI_SUSUT.gpkg",            "PETAK LAHAN — PETAK_LAHAN_BALI_BANGLI_SUSUT.gpkg"),
    "KULONPROGO_GALUR":        ("LBS_DIY_KULONPROGO_GALUR.gpkg",         "PETAK LAHAN — PETAK_LAHAN_DIY_KULONPROGO_GALUR.gpkg"),
    "LEUWIDAMAR":              ("LBS_BANTEN_LEBAK_LEUWIDAMAR.gpkg",      "PETAK LAHAN — PETAK_LAHAN_BANTEN_LEBAK_LEUWIDAMAR.gpkg"),
    "SITUBONDO_SITUBONDO":     ("LBS_JATIM_SITUBONDO_SITUBONDO.gpkg",    "PETAK LAHAN — PETAK_LAHAN_JAWATIMUR_SITUBONDO_SITUBONDO.gpkg"),
    "Tangerang_Sepatan_Timur": ("LBS_BANTEN_TANGERANG_SEPATAN_TIMUR.gpkg","PETAK LAHAN — PETAK_LAHAN_BANTEN_TANGERANG_SEPATAN_TIMUR.gpkg"),
}


def load(path):
    g = gpd.read_file(path, engine="pyogrio")
    g = g.set_geometry(g.geometry.map(lambda x: make_valid(force_2d(x))))
    return g.to_crs(CRS_CEA) if g.crs and g.crs.to_string().upper() != CRS_CEA else g


def audit(scene):
    lbs_file, parcel_file = SCENES[scene]
    lbs = load(BASE / lbs_file)
    parcels = load(BASE / parcel_file)

    lbs_u = unary_union(lbs.geometry)
    lbs_ha = lbs_u.area / HA

    kd = parcels["KDKOMO"].astype("float")
    paddy = unary_union(parcels.geometry[kd == 1])
    other = unary_union(parcels.geometry[(kd != 1) & kd.notna()])
    unclassed = unary_union(parcels.geometry[kd.isna()]) if kd.isna().any() else None

    par_u = unary_union(parcels.geometry)
    mapped_ha = lbs_u.intersection(par_u).area / HA
    a_ha = lbs_u.intersection(paddy).area / HA
    b_ha = lbs_u.intersection(other).area / HA
    unmapped_ha = lbs_ha - mapped_ha
    overlap_ha = (a_ha + b_ha) - (lbs_u.intersection(paddy.union(other)).area / HA)
    summed_ha = sum(parcels.geometry.area) / HA          # double counts overlaps
    row = dict(scene=scene, lbs_ha=round(lbs_ha, 1), mapped_ha=round(mapped_ha, 1),
               mapped_pct=round(100 * mapped_ha / lbs_ha, 2),
               unmapped_ha=round(unmapped_ha, 1),
               a_ha=round(a_ha, 1), b_ha=round(b_ha, 1),
               overlap_in_lbs_ha=round(overlap_ha, 1),
               parcel_sum_ha=round(summed_ha, 1),
               unclassed_ha=round(unclassed.area / HA, 1) if unclassed else 0.0,
               features=len(parcels))
    # the audit only holds together if the parts reconstruct the footprint
    assert abs((a_ha + b_ha - overlap_ha) - mapped_ha) < 0.5, f"{scene}: parts do not sum to mapped area"
    assert mapped_ha <= lbs_ha + 0.05, f"{scene}: mapped exceeds LBS"
    return row


if __name__ == "__main__":
    wanted = sys.argv[1:] or list(SCENES)
    rows = [audit(s) for s in wanted]
    for r in rows:
        print(f"{r['scene']:24s} LBS {r['lbs_ha']:8.1f} ha | mapped {r['mapped_pct']:6.2f}% "
              f"({r['mapped_ha']:.1f} ha) | unmapped {r['unmapped_ha']:6.1f} ha | "
              f"A {r['a_ha']:7.1f} + B {r['b_ha']:6.1f} | overlap in LBS {r['overlap_in_lbs_ha']:.1f} ha")
    if len(rows) > 1:
        out = OUT / "lbs_coverage.csv"
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"\nwrote {out}")
