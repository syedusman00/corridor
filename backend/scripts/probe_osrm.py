"""Probe how many OSRM alternatives Chicago→Denver returns."""
import requests

o_lon, o_lat = -87.6298, 41.8781
d_lon, d_lat = -104.9903, 39.7392
url = f"https://router.project-osrm.org/route/v1/driving/{o_lon},{o_lat};{d_lon},{d_lat}"

for alt in ["true", "2", "3"]:
    r = requests.get(url, params={"overview": "false", "alternatives": alt}, timeout=60)
    data = r.json()
    routes = data.get("routes") or []
    print(f"alternatives={alt!r} -> {len(routes)} routes, code={data.get('code')}")
    for i, rt in enumerate(routes):
        print(
            f"  [{i}] dist_mi={rt['distance']/1609.344:.1f} "
            f"dur_h={rt['duration']/3600:.2f}"
        )

# Exclude strategies
for exclude in ["toll", "motorway"]:
    r = requests.get(
        url,
        params={"overview": "false", "alternatives": "true", "exclude": exclude},
        timeout=60,
    )
    data = r.json()
    routes = data.get("routes") or []
    print(f"exclude={exclude} -> {len(routes)} routes, code={data.get('code')}")
    for i, rt in enumerate(routes):
        print(
            f"  [{i}] dist_mi={rt['distance']/1609.344:.1f} "
            f"dur_h={rt['duration']/3600:.2f}"
        )

# Via Des Moines (approx)
via = f"{o_lon},{o_lat};-93.6091,41.6005;{d_lon},{d_lat}"
via_url = f"https://router.project-osrm.org/route/v1/driving/{via}"
r = requests.get(via_url, params={"overview": "false"}, timeout=60)
data = r.json()
routes = data.get("routes") or []
print(f"via Des Moines -> {len(routes)} routes, code={data.get('code')}")
if routes:
    print(
        f"  dist_mi={routes[0]['distance']/1609.344:.1f} "
        f"dur_h={routes[0]['duration']/3600:.2f}"
    )
