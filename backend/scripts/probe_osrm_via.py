"""Find distinct via-point OSRM routes for Chicago→Denver."""
import requests

o = (-87.6298, 41.8781)
d = (-104.9903, 39.7392)

vias = {
    "Kansas City": (-94.5786, 39.0997),
    "Omaha": (-95.9345, 41.2565),
    "Oklahoma City": (-97.5164, 35.4676),
    "Minneapolis": (-93.2650, 44.9778),
    "St Louis": (-90.1994, 38.6270),
    "Wichita": (-97.3301, 37.6872),
    "Lincoln NE": (-96.7026, 40.8136),
    "Colorado Springs": (-104.8214, 38.8339),
}

base = f"https://router.project-osrm.org/route/v1/driving/{o[0]},{o[1]};{d[0]},{d[1]}"
r = requests.get(base, params={"overview": "false", "alternatives": "3"}, timeout=60)
base_routes = r.json().get("routes") or []
print("BASE:")
for i, rt in enumerate(base_routes):
    print(f"  [{i}] {rt['distance']/1609.344:.1f} mi / {rt['duration']/3600:.2f} h")

for name, (lon, lat) in vias.items():
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{o[0]},{o[1]};{lon},{lat};{d[0]},{d[1]}"
    )
    r = requests.get(url, params={"overview": "false"}, timeout=60)
    data = r.json()
    routes = data.get("routes") or []
    if not routes:
        print(f"{name}: FAIL {data.get('code')}")
        continue
    rt = routes[0]
    dist = rt["distance"] / 1609.344
    dur = rt["duration"] / 3600
    # compare to base
    diffs = [abs(dist - b["distance"] / 1609.344) for b in base_routes]
    min_diff = min(diffs) if diffs else 999
    print(f"{name}: {dist:.1f} mi / {dur:.2f} h | min_diff_vs_base={min_diff:.1f} mi")
