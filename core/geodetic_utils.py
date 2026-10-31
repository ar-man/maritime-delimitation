"""
Maritime Delimitation - Geodetic Utilities
Handles coordinate reference systems, UTM auto-projection, and geodesic scaling according to TALOS.
"""

import math

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject,
        QgsPointXY,
        QgsGeometry,
        QgsRectangle
    )
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False


def get_utm_epsg_for_lon_lat(lon, lat):
    """
    Determines the best WGS 84 UTM EPSG code for a given longitude and latitude.
    EPSG 32601-32660 for Northern Hemisphere.
    EPSG 32701-32760 for Southern Hemisphere.
    """
    zone = int((lon + 180.0) / 6.0) + 1
    zone = max(1, min(60, zone))
    if lat >= 0:
        return 32600 + zone
    else:
        return 32700 + zone


def get_recommended_metric_crs(source_crs, bounding_rect=None):
    """
    Returns a metric projected CRS suitable for accurate distance calculations.
    If source_crs is already projected and metric, returns source_crs.
    If source_crs is geographic (degrees, e.g. EPSG:4326), recommends appropriate UTM CRS.
    """
    if not HAS_QGIS or source_crs is None:
        return None

    if not source_crs.isGeographic():
        # Already projected metric CRS
        return source_crs

    # If geographic, find centroid of bounding rect
    if bounding_rect is not None and not bounding_rect.isNull():
        lon = bounding_rect.center().x()
        lat = bounding_rect.center().y()
    else:
        lon, lat = 105.0, 0.0  # Default Indonesia/Equatorial maritime region

    utm_epsg = get_utm_epsg_for_lon_lat(lon, lat)
    target_crs = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg}")
    if target_crs.isValid():
        return target_crs
    return source_crs


def transform_geometry(geom, source_crs, dest_crs):
    """
    Transforms a QgsGeometry from source_crs to dest_crs.
    """
    if not HAS_QGIS or geom is None:
        return geom

    if source_crs == dest_crs or not source_crs.isValid() or not dest_crs.isValid():
        return QgsGeometry(geom)

    transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
    new_geom = QgsGeometry(geom)
    new_geom.transform(transform)
    return new_geom


def meters_to_nautical_miles(meters):
    """
    Converts meters to international Nautical Miles (M / NM).
    1 NM = 1852 meters (standardized by IHO and UNCLOS).
    """
    return meters / 1852.0
