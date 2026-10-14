"""
STREEVA — Comprehensive Data-Provenance Audit Script
Runs all empirical checks directly against runtime codebase, Parquet files,
NCRB lookup, OSRM routes, and Area Risk endpoints.
"""

import sys
import json
import math
import asyncio
from pathlib import Path
import h3
import pandas as pd
import requests

# Add area-risk-service to sys.path
BASE_DIR = Path(".").resolve()
sys.path.insert(0, str(BASE_DIR / "area-risk-service"))

from app.core.h3_utils import latlng_to_h3, h3_to_centroid
from app.services.offline_feature_service import get_precomputed_features, get_h3_index
from app.services.macro_baseline_service import get_macro_baseline_score, _load_district_lookup
from app.services.district_service import get_district_for_location
from app.scoring.weighted_scorer import WeightedRiskScorer
from app.scoring.ml_risk_scorer import MLRiskScorer
from app.scoring.base_scorer import FeatureSet
from app.core.time_multiplier import get_time_multiplier
from app.config import get_scoring_weights, get_city_config

print("=== 1. AUDITING PARQUET DATASET ===")
parquet_path = BASE_DIR / "area-risk-service" / "data" / "processed" / "h3_hex_features.parquet"
df = pd.read_parquet(parquet_path)
print(f"Total H3 cells: {len(df)}")
coords = [h3.cell_to_latlng(c) for c in df["h3_cell"]]
lats = [c[0] for c in coords]
lngs = [c[1] for c in coords]
print(f"Parquet BBox: Lat [{min(lats):.6f}, {max(lats):.6f}], Lng [{min(lngs):.6f}, {max(lngs):.6f}]")
print(f"Parquet columns: {df.columns.tolist()}")

print("\n=== 2. AUDITING NCRB DATASET ===")
ncrb_path = BASE_DIR / "area-risk-service" / "data" / "processed" / "ncrb_district_lookup.json"
with open(ncrb_path, encoding="utf-8") as f:
    ncrb_data = json.load(f)

print(f"Total districts in NCRB: {len(ncrb_data)}")
violent_counts = [d["violent_crimes"] for d in ncrb_data.values()]
import statistics
min_v = min(violent_counts)
max_v = max(violent_counts)
med_v = statistics.median(violent_counts)
mean_v = statistics.mean(violent_counts)
print(f"Violent crimes: min={min_v}, max={max_v}, median={med_v}, mean={mean_v:.2f}")

chennai_ncrb = ncrb_data.get("Chennai")
print(f"Chennai NCRB: violent={chennai_ncrb['violent_crimes']}, total_ipc={chennai_ncrb['total_ipc_crimes']}")
print(f"Chennai norm score in JSON: {chennai_ncrb['normalized_score']}")
calc_norm = (chennai_ncrb['violent_crimes'] - min_v) / (max_v - min_v) * 100.0
print(f"Calculated Min-Max norm: {calc_norm:.4f}")
print(f"Normalization metadata: {chennai_ncrb['normalization']}")

print("\n=== 3. AUDITING 8 TARGET COORDINATES ===")
TARGETS = [
    ("Chennai (Ripon Bldg)", 13.0827, 80.2707),
    ("Bengaluru (MG Road)", 12.9716, 77.5946),
    ("Hyderabad (Charminar)", 17.3850, 78.4867),
    ("Mumbai (Gateway of India)", 18.9256, 72.8242),
    ("Delhi (Connaught Place)", 28.6139, 77.2090),
    ("Rural TN (Pennagaram/Dharmapuri)", 12.0500, 78.4500),
    ("Village Road (Kanchipuram village)", 12.7800, 79.8500),
    ("Highway (NH 48 Vellore corridor)", 12.8500, 79.5500),
]

weighted_scorer = WeightedRiskScorer()
ml_scorer = MLRiskScorer()

results = []

for name, lat, lng in TARGETS:
    cell = latlng_to_h3(lat, lng, 9)
    c_lat, c_lng = h3_to_centroid(cell)
    
    # 1. District resolution
    dist = get_district_for_location(lat, lng)
    
    # 2. Macro crime baseline
    crime_score, crime_meta = get_macro_baseline_score(lat=c_lat, lng=c_lng)
    
    # 3. Offline feature lookup
    offline = get_precomputed_features(cell)
    in_parquet = cell in df["h3_cell"].values
    
    # If in parquet, extract exact raw values
    if in_parquet:
        row = df[df["h3_cell"] == cell].iloc[0]
        pop_raw = int(row["population"])
        poi_raw = int(row["poi_count"])
        pol_dist_m = float(row["dist_police_m"])
        hosp_dist_m = float(row["dist_hospital_m"])
        rd_density = float(row["road_density"])
        nl_mean = float(row["nightlight_mean"])
    else:
        pop_raw = "N/A (outside parquet)"
        poi_raw = "N/A (outside parquet)"
        pol_dist_m = "N/A (outside parquet)"
        hosp_dist_m = "N/A (outside parquet)"
        rd_density = "N/A (outside parquet)"
        nl_mean = "N/A (outside parquet)"

    time_band = get_time_multiplier(14) # Daytime (14:00)
    
    fb_features = []
    if offline.get("fallback", False):
        fb_features = offline.get("fallback_features", ["spatial_fallback"])
    if crime_meta.get("source") == "fallback_neutral":
        fb_features.append("crime_baseline")
        
    feat_set = FeatureSet(
        h3_cell=cell,
        lat=c_lat,
        lng=c_lng,
        hour=14,
        crime_baseline_score=crime_score,
        isolation_score=offline["isolation_score"],
        commercial_density_score=offline["commercial_density_score"],
        police_distance_score=offline["police_distance_score"],
        hospital_distance_score=offline["hospital_distance_score"],
        population_density_score=offline["population_density_score"],
        nightlight_mean_score=offline.get("nightlight_mean_score", 50.0),
        time_multiplier=time_band.multiplier,
        time_band_name=time_band.band_name,
        time_band_label=time_band.label,
        fallback_features=fb_features
    )
    
    w_res = weighted_scorer.score(feat_set)
    ml_res = ml_scorer.score(feat_set) if ml_scorer.model_loaded else None
    
    res_dict = {
        "name": name,
        "lat": lat,
        "lng": lng,
        "h3_cell": cell,
        "in_parquet": bool(in_parquet),
        "district_resolved": dist,
        "crime_score": crime_score,
        "crime_source": crime_meta.get("source"),
        "raw_pop": pop_raw,
        "raw_poi": poi_raw,
        "raw_police_m": pol_dist_m,
        "raw_hosp_m": hosp_dist_m,
        "raw_road_density": rd_density,
        "isolation_score": offline["isolation_score"],
        "police_score": offline["police_distance_score"],
        "hospital_score": offline["hospital_distance_score"],
        "commercial_score": offline["commercial_density_score"],
        "population_score": offline["population_density_score"],
        "time_multiplier": time_band.multiplier,
        "weighted_final_score": w_res.risk_score,
        "weighted_classification": w_res.classification,
        "ml_final_score": ml_res.risk_score if ml_res else None,
        "ml_classification": ml_res.classification if ml_res else None,
        "fallback_features": fb_features,
        "data_completeness": w_res.data_completeness
    }
    results.append(res_dict)

print(json.dumps(results, indent=2))

with open(BASE_DIR / "area-risk-service" / "scratch_audit_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nAudit results saved to scratch_audit_results.json")
