

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FARS SETTLEMENT PROJECTION
Data Preparation

هدف:
- پیدا کردن اولین Raster مرجع 30 متری موجود
- تبدیل همه Rasterهای موجود به یک شبکه مشترک
- استفاده از CRS متریک پروژه
- بازنمونه‌برداری مناسب برای داده‌های پیوسته و طبقه‌ای
- قرار دادن خروجی‌ها در data/aligned/

نکته:
تبدیل داده‌های درشت‌تر به 30 متر اطلاعات مکانی جدید ایجاد نمی‌کند؛
فقط همه لایه‌ها را روی یک Grid مشترک قرار می‌دهد.
"""

from pathlib import Path
import logging
import argparse

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject


# ============================================================
# تنظیمات اصلی پروژه
# ============================================================

# سیستم مختصات متریک پروژه
TARGET_CRS = (
    "+proj=tmerc "
    "+lat_0=0 "
    "+lon_0=53 "
    "+k=1 "
    "+x_0=0 "
    "+y_0=0 "
    "+datum=WGS84 "
    "+units=m "
    "+no_defs "
    "+type=crs"
)

# شبکه هدف
TARGET_RESOLUTION = 30.0


# ============================================================
# Rasterهای مناسب برای تعیین Grid مرجع
# ============================================================

REFERENCE_CANDIDATES = [
    Path("data/environmental/ndvi/ndvi_2020.tif"),
    Path("data/environmental/lst/lst_2020.tif"),
    Path("data/environmental/ndbi/ndbi_2020.tif"),
]


# ============================================================
# فایل‌های ورودی پروژه
# ============================================================

RASTER_FILES = {

    "builtup": [
        "data/builtup/builtup_1995.tif",
        "data/builtup/builtup_2000.tif",
        "data/builtup/builtup_2005.tif",
        "data/builtup/builtup_2010.tif",
        "data/builtup/builtup_2015.tif",
        "data/builtup/builtup_2020.tif",
        "data/builtup/builtup_2025.tif",
    ],

    "lulc": [
        "data/lulc/lulc_1995.tif",
        "data/lulc/lulc_2000.tif",
        "data/lulc/lulc_2005.tif",
        "data/lulc/lulc_2010.tif",
        "data/lulc/lulc_2015.tif",
        "data/lulc/lulc_2020.tif",
        "data/lulc/lulc_2025.tif",
    ],

    "ndvi": [
        "data/environmental/ndvi/ndvi_1995.tif",
        "data/environmental/ndvi/ndvi_2000.tif",
        "data/environmental/ndvi/ndvi_2005.tif",
        "data/environmental/ndvi/ndvi_2010.tif",
        "data/environmental/ndvi/ndvi_2015.tif",
        "data/environmental/ndvi/ndvi_2020.tif",
        "data/environmental/ndvi/ndvi_2025.tif",
    ],

    "lst": [
        "data/environmental/lst/lst_1995.tif",
        "data/environmental/lst/lst_2000.tif",
        "data/environmental/lst/lst_2005.tif",
        "data/environmental/lst/lst_2010.tif",
        "data/environmental/lst/lst_2015.tif",
        "data/environmental/lst/lst_2020.tif",
        "data/environmental/lst/lst_2025.tif",
    ],

    "ndbi": [
        "data/environmental/ndbi/ndbi_1995.tif",
        "data/environmental/ndbi/ndbi_2000.tif",
        "data/environmental/ndbi/ndbi_2005.tif",
        "data/environmental/ndbi/ndbi_2010.tif",
        "data/environmental/ndbi/ndbi_2015.tif",
        "data/environmental/ndbi/ndbi_2020.tif",
        "data/environmental/ndbi/ndbi_2025.tif",
    ],

    "rainfall": [
        "data/climate/precipitation/precipitation_1995.tif",
        "data/climate/precipitation/precipitation_2000.tif",
        "data/climate/precipitation/precipitation_2005.tif",
        "data/climate/precipitation/precipitation_2010.tif",
        "data/climate/precipitation/precipitation_2015.tif",
        "data/climate/precipitation/precipitation_2020.tif",
        "data/climate/precipitation/precipitation_2025.tif",
    ],

    "population": [
        "data/population/population_1995.tif",
        "data/population/population_2000.tif",
        "data/population/population_2005.tif",
        "data/population/population_2010.tif",
        "data/population/population_2015.tif",
        "data/population/population_2020.tif",
        "data/population/population_2025.tif",
    ],

    "terrain": [
        "data/terrain/elevation_fars.tif",
        "data/terrain/slope_fars.tif",
    ],

    "accessibility": [
        "data/accessibility/roads/distance_roads_fars.tif",
        "data/accessibility/settlements/distance_settlements_fars.tif",
    ],
}


# ============================================================
# نوع بازنمونه‌برداری
# ============================================================

# این داده‌ها نباید Bilinear شوند.
NEAREST_GROUPS = {
    "lulc",
    "builtup",
    "population",
}


# ============================================================
# پیدا کردن Raster مرجع
# ============================================================

def find_reference():
    """
    اولین Raster موجود 30 متری را به‌عنوان Raster مرجع انتخاب می‌کند.
    """

    for path in REFERENCE_CANDIDATES:

        if path.exists():
            return path

    raise FileNotFoundError(
        "هیچ Raster مرجع پیدا نشد.\n"
        "حداقل یکی از این فایل‌ها را باید ابتدا داخل پروژه قرار دهید:\n"
        "  - data/environmental/ndvi/ndvi_2020.tif\n"
        "  - data/environmental/lst/lst_2020.tif\n"
        "  - data/environmental/ndbi/ndbi_2020.tif"
    )


# ============================================================
# ساخت Grid مرجع
# ============================================================

def build_reference_profile(reference_path):
    """
    Grid هدف را بر اساس محدوده Raster مرجع می‌سازد.
    """

    with rasterio.open(reference_path) as src:

        if src.crs is None:
            raise ValueError(
                f"Raster مرجع CRS ندارد: {reference_path}"
            )

        transform, width, height = calculate_default_transform(
            src.crs,
            TARGET_CRS,
            src.width,
            src.height,
            *src.bounds,
            resolution=TARGET_RESOLUTION,
        )

        profile = src.profile.copy()

        profile.update(
            crs=TARGET_CRS,
            transform=transform,
            width=width,
            height=height,
            compress="deflate",
            tiled=True,
            BIGTIFF="IF_SAFER",
        )

        return profile


# ============================================================
# تبدیل یک Raster
# ============================================================

def align_raster(
    input_path,
    output_path,
    reference_profile,
    resampling_method,
):
    """
    یک Raster را به Grid مشترک پروژه منتقل می‌کند.
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with rasterio.open(input_path) as src:

        if src.crs is None:
            raise ValueError(
                f"Raster فاقد CRS است: {input_path}"
            )

        profile = reference_profile.copy()

        profile.update(
            driver="GTiff",
            dtype=src.dtypes[0],
            count=src.count,
            nodata=src.nodata,
        )

        with rasterio.open(
            output_path,
            "w",
            **profile
        ) as dst:

            for band_index in range(
                1,
                src.count + 1
            ):

                reproject(
                    source=rasterio.band(
                        src,
                        band_index
                    ),
                    destination=rasterio.band(
                        dst,
                        band_index
                    ),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    src_nodata=src.nodata,
                    dst_transform=reference_profile["transform"],
                    dst_crs=reference_profile["crs"],
                    dst_nodata=src.nodata,
                    resampling=resampling_method,
                )

    logging.info(
        "Aligned: %s -> %s",
        input_path,
        output_path
    )


# ============================================================
# پیدا کردن فایل‌های موجود
# ============================================================

def collect_existing_files():

    existing = []

    for group, paths in RASTER_FILES.items():

        for raw_path in paths:

            path = Path(raw_path)

            if path.exists():

                existing.append(
                    (group, path)
                )

            else:

                logging.info(
                    "Not available yet: %s",
                    path
                )

    return existing


# ============================================================
# اجرای اصلی
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Align Fars settlement-project rasters "
            "to a common 30 m metric grid."
        )
    )

    parser.add_argument(
        "--output-dir",
        default="data/aligned",
        help=(
            "مسیر خروجی. "
            "پیش‌فرض: data/aligned"
        )
    )

    parser.add_argument(
        "--reference",
        default=None,
        help=(
            "مسیر Raster مرجع. "
            "در صورت خالی بودن، اولین گزینه موجود انتخاب می‌شود."
        )
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------
    # Reference
    # --------------------------------------------

    if args.reference:

        reference_path = Path(
            args.reference
        )

    else:

        reference_path = find_reference()

    logging.info(
        "Reference raster: %s",
        reference_path
    )

    logging.info(
        "Target CRS: %s",
        TARGET_CRS
    )

    logging.info(
        "Target resolution: %s m",
        TARGET_RESOLUTION
    )

    # --------------------------------------------
    # Build target grid
    # --------------------------------------------

    reference_profile = build_reference_profile(
        reference_path
    )

    # --------------------------------------------
    # Existing files
    # --------------------------------------------

    existing_files = collect_existing_files()

    logging.info(
        "Number of available rasters: %d",
        len(existing_files)
    )

    # --------------------------------------------
    # Align
    # --------------------------------------------

    prepared_count = 0

    for group, input_path in existing_files:

        output_path = (
            output_dir
            / group
            / input_path.name
        )

        if group in NEAREST_GROUPS:

            method = Resampling.nearest

        else:

            method = Resampling.bilinear

        align_raster(
            input_path=input_path,
            output_path=output_path,
            reference_profile=reference_profile,
            resampling_method=method,
        )

        prepared_count += 1

    logging.info(
        "Finished. %d raster(s) prepared.",
        prepared_count
    )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()
