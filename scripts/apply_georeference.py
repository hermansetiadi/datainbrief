"""Embed the released georeference into a copy of a mask, or of the supplied scene.

The released files carry no coordinates, by design; this script attaches them, using
`georeference.csv` from the repository root. Nothing original is modified.

Run:
    uv run --with rasterio python scripts/apply_georeference.py <file.tif> [...]

For each input, writes `<name>_georef.tif` next to it with the CRS and transform set, so the result
opens in a GIS or with rasterio/GDAL and can be overlaid on other layers.
"""
import csv
import sys
from pathlib import Path

import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

HERE = Path(__file__).resolve().parent
REF = {}
with (HERE.parent / "georeference.csv").open(encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        # scene names in the CSV match the file-name prefix; the Tangerang scene is spelled differently
        REF[row["scene"]] = row


def lookup(name: str):
    for scene, row in REF.items():
        if name.startswith(scene):
            return row
    for scene, row in REF.items():                    # fall back to a loose match
        if scene.split("_")[0].lower() in name.lower():
            return row
    raise SystemExit(f"{name}: no entry in georeference.csv; known scenes: {', '.join(REF)}")


def main(paths):
    for p in map(Path, paths):
        row = lookup(p.name)
        with rasterio.open(p) as src:
            if (src.width, src.height) != (int(row["width"]), int(row["height"])):
                raise SystemExit(f"{p.name}: grid is {src.width}x{src.height}, expected "
                                 f"{row['width']}x{row['height']} — refusing to guess")
            profile = src.profile
            bands = src.read()
        profile.update(crs=CRS.from_string(row["crs"]),
                       transform=Affine(float(row["a"]), float(row["b"]), float(row["c"]),
                                        float(row["d"]), float(row["e"]), float(row["f"])))
        out = p.with_name(p.stem + "_georef.tif")
        with rasterio.open(out, "w", **profile) as dst:
            dst.write(bands)
        with rasterio.open(out) as chk:
            print(f"ok  {out.name}  {chk.width}x{chk.height}  {chk.crs}  corner "
                  f"{chk.transform.c:.5f}, {chk.transform.f:.5f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
