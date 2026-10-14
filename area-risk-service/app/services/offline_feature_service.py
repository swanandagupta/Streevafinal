"""
STREEVA — Offline Feature Service
app/services/offline_feature_service.py

Replaces runtime OSM/Google Places calls by looking up pre-computed hex values.
Loads in-memory parquet table.
"""

import pandas as pd
from pathlib import Path
import logging
import math

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FEATURES_PATH = BASE_DIR / "data" / "processed" / "h3_hex_features.parquet"

_df = None

def get_h3_index():
    global _df
    if _df is None:
        if FEATURES_PATH.exists():
            # Load and index by h3_cell for O(1) lookups
            _df = pd.read_parquet(FEATURES_PATH).set_index("h3_cell")
        else:
            logger.info(f"Parquet feature store not found at {FEATURES_PATH}. Will use online/cached service extraction.")
            # Mock empty DataFrame
            _df = pd.DataFrame()
    return _df

def _extract_live_or_cached_features(h3_cell: str) -> dict:
    """
    Extract features using existing services (OSMnx, Google Places/OSM amenities, WorldPop),
    each backed by DiskCache.
    """
    from app.services.osm_service import compute_isolation_score
    from app.services.places_service import (
        compute_commercial_density_score,
        compute_police_distance_score,
        compute_hospital_distance_score,
    )
    from app.services.population_service import compute_population_density_score

    iso_score, _, iso_fb = compute_isolation_score(h3_cell)
    com_score, _, com_fb = compute_commercial_density_score(h3_cell)
    pol_score, _, pol_fb = compute_police_distance_score(h3_cell)
    hosp_score, _, hosp_fb = compute_hospital_distance_score(h3_cell)
    pop_score, _, pop_fb = compute_population_density_score(h3_cell)

    fallback_features = []
    if iso_fb: fallback_features.append("isolation")
    if com_fb: fallback_features.append("commercial_density")
    if pol_fb: fallback_features.append("police_distance")
    if hosp_fb: fallback_features.append("hospital_distance")
    if pop_fb: fallback_features.append("population_density")

    return {
        "crime_baseline_score": 50.0,
        "isolation_score": iso_score,
        "commercial_density_score": com_score,
        "police_distance_score": pol_score,
        "hospital_distance_score": hosp_score,
        "population_density_score": pop_score,
        "nightlight_mean_score": 50.0,
        "fallback": len(fallback_features) > 0,
        "fallback_features": fallback_features,
        "source": "online_cached",
    }

def get_precomputed_features(h3_cell: str) -> dict:
    df = get_h3_index()
    
    if not df.empty and h3_cell in df.index:
        row = df.loc[h3_cell]
        
        # We perform the same normalizations to 0-100 here as we did in train_model.py
        max_rd = df['road_density'].max() + 1e-5
        iso = (1.0 - (row['road_density'] / max_rd)) * 100.0
        
        max_poi = df['poi_count'].max() + 1e-5
        com = (1.0 - (row['poi_count'] / max_poi)) * 100.0
        
        pol_dist = row['dist_police_m']
        pol = 100.0 / (1.0 + math.exp(-0.001 * (pol_dist - 2500)))
        
        hosp_dist = row['dist_hospital_m']
        hosp = 100.0 / (1.0 + math.exp(-0.001 * (hosp_dist - 3000)))
        
        max_pop = df['population'].max() + 1e-5
        pop = (1.0 - (row['population'] / max_pop)) * 100.0
        
        max_nl = df['nightlight_mean'].max() + 1e-5
        nl = (1.0 - (row['nightlight_mean'] / max_nl)) * 100.0
        
        crime = float(row.get('crime_baseline_score', 50.0))
        
        return {
            "crime_baseline_score": crime,
            "isolation_score": iso,
            "commercial_density_score": com,
            "police_distance_score": pol,
            "hospital_distance_score": hosp,
            "population_density_score": pop,
            "nightlight_mean_score": nl,
            "fallback": False,
            "fallback_features": [],
            "source": "precomputed_parquet",
        }
    else:
        # Parquet index absent or cell outside index -> extract via online/cached services
        try:
            return _extract_live_or_cached_features(h3_cell)
        except Exception as exc:
            logger.error(f"Failed online/cached feature extraction for H3 cell {h3_cell}: {exc}")
            return {
                "crime_baseline_score": 50.0,
                "isolation_score": 50.0,
                "commercial_density_score": 50.0,
                "police_distance_score": 50.0,
                "hospital_distance_score": 50.0,
                "population_density_score": 50.0,
                "nightlight_mean_score": 50.0,
                "fallback": True,
                "fallback_features": [
                    "isolation", "commercial_density", "police_distance",
                    "hospital_distance", "population_density", "nightlight_mean"
                ],
                "source": "fallback_neutral",
            }
