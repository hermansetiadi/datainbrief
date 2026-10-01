"""Rasterize Lahan Baku Sawah (LBS) 2019 polygons onto a georeferenced image grid.

This is the rule that produced the published *_mask.tif files (verified pixel-exact
at all five sites): a pixel is paddy (255) only if its CENTRE falls inside an LBS
polygon (rasterio all_touched=False); everything else is 0.

Needs the ORIGINAL georeferenced imagery and the LBS vectors, neither of which is in
this record (the published rasters carry no coordinates).

usage: python make_mask.py <georeferenced_image.tif> <lbs_vectors.gpkg|.gdb> [layer] <out_mask.tif>
"""
import sys
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window, transform as window_transform

image, vectors, *rest = sys.argv[1:]
layer, out = (rest[0], rest[1]) if len(rest) == 2 else (None, rest[0])

with rasterio.open(image) as img:
    lbs = gpd.read_file(vectors, layer=layer)
    lbs = lbs.set_geometry(lbs.geometry.force_2d()).to_crs(img.crs)
    geoms = [g for g in lbs.geometry if g is not None and not g.is_empty]
    profile = dict(driver="GTiff", width=img.width, height=img.height, count=1, dtype="uint8",
                   crs=img.crs, transform=img.transform, compress="lzw")
    with rasterio.open(out, "w", **profile) as dst:
        for r0 in range(0, img.height, 4096):                      # row blocks keep memory flat
            w = Window(0, r0, img.width, min(4096, img.height - r0))
            dst.write(rasterize(geoms, out_shape=(w.height, w.width), transform=window_transform(w, img.transform),
                                fill=0, default_value=255, all_touched=False, dtype="uint8"), 1, window=w)
