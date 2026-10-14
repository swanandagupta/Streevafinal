import requests
import json

url = 'https://router.project-osrm.org/route/v1/driving/80.2707,13.0827;72.8242,18.9256?overview=full&geometries=geojson&steps=true&annotations=true'
print('Fetching OSRM route Chennai -> Mumbai...')
resp = requests.get(url, timeout=30)
print('Status:', resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    routes = data.get('routes', [])
    if routes:
        r0 = routes[0]
        print(f"Total distance: {r0['distance']/1000:.2f} km")
        print(f"Total duration: {r0['duration']/3600:.2f} hours")
        legs = r0.get('legs', [])
        steps = legs[0].get('steps', [])
        print(f"Total OSRM steps: {len(steps)}")
        
        # Examine step fields
        sample_step = steps[0]
        print("Sample step keys:", list(sample_step.keys()))
        print("Sample step:", json.dumps(sample_step, indent=2))
        
        # Check annotations
        annotation = legs[0].get('annotation', {})
        print("Annotation keys:", list(annotation.keys()))
        
        # Tally road names and refs
        names = [s.get('name', '') for s in steps if s.get('name')]
        refs = [s.get('ref', '') for s in steps if s.get('ref')]
        print(f"Named steps: {len(names)} / {len(steps)}")
        print(f"Steps with ref (e.g. NH/SH): {len(refs)} / {len(steps)}")
        print("Sample refs:", list(set(refs))[:10])
        print("Sample names:", list(set(names))[:10])
