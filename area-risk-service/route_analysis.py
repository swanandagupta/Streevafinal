import requests
import json
import math
from pathlib import Path
import h3
import pandas as pd

BASE_DIR = Path(".").resolve()
import sys
sys.path.insert(0, str(BASE_DIR / "area-risk-service"))

from app.core.h3_utils import latlng_to_h3
from app.services.district_service import get_district_for_location

# Load Parquet
parquet_path = BASE_DIR / "area-risk-service" / "data" / "processed" / "h3_hex_features.parquet"
df = pd.read_parquet(parquet_path)
parquet_cells = set(df['h3_cell'].values)

# Fetch OSRM route Chennai -> Mumbai
url = 'https://router.project-osrm.org/route/v1/driving/80.2707,13.0827;72.8242,18.9256?overview=full&geometries=geojson&steps=true'
resp = requests.get(url, timeout=30)
data = resp.json()
route = data['routes'][0]
coordinates = route['geometry']['coordinates'] # [lng, lat]
steps = route['legs'][0]['steps']

print(f"Total route coordinates: {len(coordinates)}")
print(f"Total distance: {route['distance']/1000:.1f} km")

# Sample coordinates along the route
samples = []
step_dist = max(1, len(coordinates) // 100) # 100 samples
in_coverage_count = 0
district_counts = {}

for i in range(0, len(coordinates), step_dist):
    lng, lat = coordinates[i]
    cell = latlng_to_h3(lat, lng, 9)
    in_cov = cell in parquet_cells
    if in_cov:
        in_coverage_count += 1
    dist = get_district_for_location(lat, lng)
    district_counts[dist] = district_counts.get(dist, 0) + 1
    samples.append({
        "lat": lat,
        "lng": lng,
        "cell": cell,
        "in_parquet": in_cov,
        "district": dist
    })

print(f"Samples evaluated: {len(samples)}")
print(f"In Parquet risk coverage: {in_coverage_count} / {len(samples)} ({in_coverage_count/len(samples)*100:.1f}%)")
print(f"District resolution distribution: {district_counts}")

# Examine steps for road attributes
ref_types = {}
step_names_present = 0
for s in steps:
    name = s.get('name', '')
    ref = s.get('ref', '')
    if name:
        step_names_present += 1
    if ref:
        prefix = ref.split()[0] if ref else 'Unref'
        ref_types[prefix] = ref_types.get(prefix, 0) + 1

print(f"Steps with names: {step_names_present}/{len(steps)}")
print(f"Highway/Ref types: {ref_types}")
