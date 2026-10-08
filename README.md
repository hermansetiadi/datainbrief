# Dataset of sub-metre Pléiades imagery and national paddy-field labels for five sub-districts in Java and Bali, Indonesia

Five uncropped very-high-resolution (~0.5 m) Pléiades-derived RGB scenes of Indonesian sub-districts, each paired with a pixel-aligned binary paddy-field mask. The masks are the official Lahan Baku Sawah (LBS) 2019 paddy-field polygons rasterized onto each image grid. LBS records designated paddy land, not observed land cover; the label-quality section below reports how far the designation agrees with land-use attribution recorded in 2022.

This repository holds the documentation, statistics, label-quality tables, checksums and scripts. The rasters themselves (10 GeoTIFF files, 4.25 GB zipped) are on Figshare:

- Raster files: https://doi.org/10.6084/m9.figshare.33000494.v2
- Record description: https://doi.org/10.6084/m9.figshare.32938838

Download the ten `*.tif.zip` files, unzip them into one folder, then check them with `sha256sum -c checksums.sha256` run in that folder (with a copy of `checksums.sha256` next to the files).

## Sites

| Scene | Sub-district, regency | Province | Width × height (px) | Valid pixels | Paddy, % of valid |
|---|---|---|---|---|---|
| BANGLI_SUSUT | Susut, Bangli | Bali | 9730 × 39666 | 51.2% | 18.3 |
| KULONPROGO_GALUR | Galur, Kulon Progo | DI Yogyakarta | 17507 × 14854 | 50.0% | 36.6 |
| LEUWIDAMAR | Leuwidamar, Lebak | Banten | 24291 × 48442 | 48.7% | 9.7 |
| SITUBONDO_SITUBONDO | Situbondo, Situbondo | East Java | 15462 × 26421 | 30.1% | 25.3 |
| Tangerang_Sepatan_Timur | Sepatan Timur, Tangerang | Banten | 11918 × 11460 | 54.9% | 49.3 |

Only 30–55% of each rectangle holds image data; the rest is no-data (65536).

## Files

On Figshare:

| File | Content |
|---|---|
| `<SCENE>_raw.tif` | 3 bands, uint32, uncompressed GeoTIFF container, 128 × 128 tiles. Pan-sharpened, rescaled values, observed range 0–5722. No-data = 65536 (stored in the `GDAL_NODATA` tag). Band order assumed R, G, B (see Notes). |
| `<SCENE>_mask.tif` | 1 band, uint8, LZW. 255 = paddy (LBS 2019), 0 = not paddy. Same width and height as the paired raw file; pixel (row, col) in the mask covers pixel (row, col) in the image. |

In this repository:

| File | Content |
|---|---|
| `scene_statistics.csv` | Per scene: size, valid (non-no-data) pixels, paddy pixels, per-band min / max / mean / std over valid pixels. |
| `label_agreement_matrix.csv` | Per scene: LBS area with 2022 parcel land use = paddy, LBS area with other land use, 2022 paddy parcels outside LBS (ha), and area-based precision, recall, F1 and IoU of the LBS mask against the 2022 parcel land use (see "Label quality"). |
| `label_agreement_by_village.csv` | The same precision and recall per village (anonymised IDs; villages with ≥5 ha of LBS), showing the spread within each scene. |
| `lbs_landuse_composition.csv` | Area (ha) inside the LBS mask by 2022 parcel land-use class (11 classes), per scene. |
| `coverage_domain.csv` | Per scene: LBS area, parcel area recorded outside the LBS perimeter, the part of that area not classified as paddy, the surrounding kecamatan area, and two ratios. |
| `sensitivity_lainlain.csv` | Precision and IoU per scene as published, then recomputed with the undefined class Lain-lain removed from the comparison domain. |
| `checksums.sha256` | SHA-256 of every `.tif`. Verify with `sha256sum -c checksums.sha256`. |
| `scripts/make_mask.py` | The rasterization used to make the masks (pixel-centre rule). Needs the original georeferenced imagery and LBS vectors, which are not published. |
| `scripts/scene_statistics.py` | Recomputes `scene_statistics.csv` from the Figshare `.tif` files: `python scripts/scene_statistics.py <folder with the .tif files>`. Needs `rasterio` and `numpy`. |
| `LICENSE` | Licence terms (CC BY 4.0) and the imagery rights note. |

## Reading the data

```python
import rasterio
with rasterio.open("BANGLI_SUSUT_raw.tif") as r, rasterio.open("BANGLI_SUSUT_mask.tif") as m:
    img = r.read()          # (3, H, W) uint32; 65536 = no-data
    mask = m.read(1) == 255 # (H, W) bool; True = paddy
```

The scenes are large (up to 1.18 gigapixels, 13.5 GB). Read them in windows (`rasterio.windows.Window`) rather than whole.

## Notes

- **No geolocation.** The files carry no coordinate reference system, geotransform, GCPs or RPCs (rasterio reports an identity transform and a `NotGeoreferencedWarning`). This is deliberate: exact field locations are withheld. They cannot be overlaid on maps.
- **Photometric tag.** The raw files are tagged MinIsBlack with three samples, not RGB, so some viewers show only band 1. Read the bands explicitly.
- **Band order.** Bands are unnamed in the source and are assumed to be R, G, B.
- **Mask rule.** A pixel is paddy only if its centre lies inside an LBS polygon (`rasterio.features.rasterize`, `all_touched=False`). Re-running `scripts/make_mask.py` on the original inputs reproduces the published masks with zero differing pixels.
- **Masks on no-data.** Masks are defined over the full scene rectangle, including no-data image areas. A small number of paddy pixels fall on no-data (at most 1.0% of a scene's paddy pixels, in Leuwidamar); see `paddy_px_on_nodata` in `scene_statistics.csv`. Mask them out with the image no-data before training.
- **Acquisition metadata** (dates, Pléiades 1A/1B, processing level) was not supplied with the imagery and is not available. What the files show: the imagery predates October 2022; the ≈0.5 m pixel size fits pan-sharpened Pléiades 1A/1B; values reach up to 5722, above the 12-bit sensor range, so the digital numbers of the supplied product were rescaled during processing. Do not treat them as radiance or reflectance.

## Label quality

LBS 2019 records designated paddy land, not observed land cover. Compared with a 2022 parcel-level land-use dataset compiled by Balai Besar Sumber Daya Lahan Pertanian (BBSDLP) in its "Spasialisasi Lahan Petani" activity (finalised September–October 2022, covering the entire LBS area), the masks reach area-based precision 82.9%, recall 85.0% and IoU 72.3% over all scenes. Agreement varies by scene (IoU 48.5% in Situbondo to 86.4% in Bangli) and across 41 villages (precision 44.8–96.6%, recall 34.3–99.0%). In Situbondo, 261 ha of the 779 ha mask were recorded as sugarcane in 2022. Part of the parcel geometry was derived from the LBS polygons, so the comparison measures the 2022 land-use attribution of parcels against the 2019 LBS designation, not independent boundary accuracy. The parcel data extend only partly beyond LBS, so true-negative area and overall accuracy are not reported. Disagreement can reflect LBS error or land-use change between 2019 and 2022. The parcel data are not redistributed; only these summaries are. How far the comparison reaches beyond the LBS perimeter is in `coverage_domain.csv`: 951 ha of recorded parcels lie outside LBS across the five scenes, 18.3% of the 5184 ha of designated paddy, and LBS plus those parcels cover 10.8% to 53.4% of the surrounding kecamatan. The effect of the undefined class is in `sensitivity_lainlain.csv`: pooled precision is 82.9% with Lain-lain counted as non-paddy and 91.7% with it removed from the comparison domain, so the higher figure reflects deleted unclassified area, not better labels.

## Credits and licence

Pléiades imagery © CNES, distribution Airbus DS; provided to the authors by Balai Besar Sumber Daya Lahan Pertanian (BBSDLP), Ministry of Agriculture, Indonesia. LBS 2019 paddy-field data: Ministry of Agrarian Affairs and Spatial Planning / National Land Agency (ATR/BPN) and Ministry of Agriculture, Indonesia.

CC BY 4.0 applies to the masks, statistics, documentation and scripts, in this repository and on Figshare. It does not apply to the Pléiades imagery, which is included in the associated Figshare records as supplied by BBSDLP. Work that uses these scenes should credit CNES / Airbus DS as above.
