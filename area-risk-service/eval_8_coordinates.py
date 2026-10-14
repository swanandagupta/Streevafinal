import sys
import json
import math
from pathlib import Path
import h3
import pandas as pd

BASE_DIR = Path(".").resolve()
sys.path.insert(0, str(BASE_DIR / "area-risk-service"))

from app.core.h3_utils import latlng_to_h3, h3_to_centroid
from app.services.macro_baseline_service import get_macro_baseline_score
from app.services.district_service import get_district_for_location
from app.scoring.weighted_scorer import WeightedRiskScorer
from app.scoring.ml_risk_scorer import MLRiskScorer
from app.scoring.base_scorer import FeatureSet
from app.core.time_multiplier import get_time_multiplier

parquet_path = BASE_DIR / "area-risk-service" / "data" / "processed" / "h3_hex_features.parquet"
df = pd.read_parquet(parquet_path)
df_indexed = df.set_index("h3_cell")

# Maximum normalizers from parquet as computed in train_model.py & offline_feature_service.py
max_rd = df['road_density'].max() + 1e-5
max_poi = df['poi_count'].max() + 1e-5
max_pop = df['population'].max() + 1e-5
max_nl = df['nightlight_mean'].max() + 1e-5

TARGETS = [
    ("Chennai (Ripon Bldg)", 13.0827, 80.2707, "Urban Metropolitan Core"),
    ("Bengaluru (MG Road)", 12.9716, 77.5946, "Urban Tech Hub (Karnataka)"),
    ("Hyderabad (Charminar)", 17.3850, 78.4867, "Urban Historic Core (Telangana)"),
    ("Mumbai (Gateway of India)", 18.9256, 72.8242, "Urban Coastal Megacity (Maharashtra)"),
    ("Delhi (Connaught Place)", 28.6139, 77.2090, "Urban National Capital (Delhi NCT)"),
    ("Rural TN (Pennagaram/Dharmapuri)", 12.0500, 78.4500, "Rural Agricultural Corridor (Tamil Nadu)"),
    ("Village Road (Kanchipuram village)", 12.7800, 79.8500, "Semi-rural Village Road (Tamil Nadu)"),
    ("Highway (NH 48 Vellore corridor)", 12.8500, 79.5500, "National Highway Corridor (Tamil Nadu)"),
]

weighted_scorer = WeightedRiskScorer()
ml_scorer = MLRiskScorer()
time_band = get_time_multiplier(14) # 14:00 Daytime (1.0x)

results = []

for name, lat, lng, desc in TARGETS:
    cell = latlng_to_h3(lat, lng, 9)
    c_lat, c_lng = h3_to_centroid(cell)
    
    # 1. District resolution via district_service
    dist_resolved = get_district_for_location(lat, lng)
    
    # 2. NCRB baseline
    crime_score, crime_meta = get_macro_baseline_score(district=dist_resolved, lat=c_lat, lng=c_lng)
    
    # 3. Check Parquet index
    in_parquet = cell in df_indexed.index
    
    if in_parquet:
        row = df_indexed.loc[cell]
        crime_base_parquet = float(row.get('crime_baseline_score', crime_score))
        pop_raw = int(row['population'])
        poi_raw = int(row['poi_count'])
        dist_police_m = float(row['dist_police_m'])
        dist_hospital_m = float(row['dist_hospital_m'])
        rd_density = float(row['road_density'])
        nl_mean = float(row['nightlight_mean'])
        
        iso_score = (1.0 - (rd_density / max_rd)) * 100.0
        com_score = (1.0 - (poi_raw / max_poi)) * 100.0
        pol_score = 100.0 / (1.0 + math.exp(-0.001 * (dist_police_m - 2500)))
        hosp_score = 100.0 / (1.0 + math.exp(-0.001 * (dist_hospital_m - 3000)))
        pop_score = (1.0 - (pop_raw / max_pop)) * 100.0
        nl_score = (1.0 - (nl_mean / max_nl)) * 100.0
        
        fb_features = []
        spatial_source = "precomputed_parquet"
    else:
        # Documented runtime fallback behavior outside coverage bounds
        pop_raw = "UNKNOWN"
        poi_raw = "UNKNOWN"
        dist_police_m = "UNKNOWN"
        dist_hospital_m = "UNKNOWN"
        rd_density = "UNKNOWN"
        nl_mean = "UNKNOWN"
        
        iso_score = 50.0
        com_score = 50.0
        pol_score = 50.0
        hosp_score = 50.0
        pop_score = 50.0
        nl_score = 50.0
        crime_base_parquet = crime_score
        
        fb_features = [
            "isolation", "commercial_density", "police_distance",
            "hospital_distance", "population_density", "nightlight_mean"
        ]
        spatial_source = "fallback_neutral"

    if crime_meta.get("source") == "fallback_neutral" and "crime_baseline" not in fb_features:
        fb_features.append("crime_baseline")

    feat_set = FeatureSet(
        h3_cell=cell,
        lat=c_lat,
        lng=c_lng,
        hour=14,
        crime_baseline_score=crime_base_parquet,
        isolation_score=iso_score,
        commercial_density_score=com_score,
        police_distance_score=pol_score,
        hospital_distance_score=hosp_score,
        population_density_score=pop_score,
        nightlight_mean_score=nl_score,
        time_multiplier=time_band.multiplier,
        time_band_name=time_band.band_name,
        time_band_label=time_band.label,
        fallback_features=fb_features
    )
    
    w_res = weighted_scorer.score(feat_set)
    ml_res = ml_scorer.score(feat_set) if ml_scorer.model_loaded else None
    
    results.append({
        "name": name,
        "desc": desc,
        "lat": lat,
        "lng": lng,
        "h3_cell": cell,
        "in_parquet": in_parquet,
        "spatial_source": spatial_source,
        "district_resolved": dist_resolved,
        "crime_baseline": crime_base_parquet,
        "crime_source": crime_meta.get("source"),
        "raw_pop": pop_raw,
        "raw_poi": poi_raw,
        "dist_police_m": dist_police_m,
        "dist_hospital_m": dist_hospital_m,
        "road_density": rd_density,
        "nightlight_mean": nl_mean,
        "isolation_score": round(iso_score, 2),
        "police_distance_score": round(pol_score, 2),
        "hospital_distance_score": round(hosp_score, 2),
        "commercial_density_score": round(com_score, 2),
        "population_density_score": round(pop_score, 2),
        "time_multiplier": time_band.multiplier,
        "contributing_factors": w_res.contributing_factors,
        "weighted_raw_score": sum(w_res.contributing_factors[k] for k in [
            "crime_baseline", "isolation", "commercial_density",
            "police_distance", "hospital_distance", "population_density"
        ]),
        "weighted_final_score": w_res.risk_score,
        "weighted_classification": w_res.classification,
        "ml_final_score": ml_res.risk_score if ml_res else None,
        "ml_classification": ml_res.classification if ml_res else None,
        "data_completeness": w_res.data_completeness,
        "fallback_features": fb_features
    })

print(json.dumps(results, indent=2))

with open("audit_8_coordinates.json", "w") as f:
    json.dump(results, f, indent=2)
