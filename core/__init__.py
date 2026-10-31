"""
Core module for Maritime Delimitation Plugin.
"""

from .delimitation_engine import DelimitationEngine
from .marching_squares import marching_squares_zero_cross, chain_segments_to_polylines, chaikin_smooth
from .geodetic_utils import get_utm_epsg_for_lon_lat, get_recommended_metric_crs, meters_to_nautical_miles
