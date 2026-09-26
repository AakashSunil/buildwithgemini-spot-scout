"""External public API integration for SpotScout.

Uses OpenStreetMap Nominatim API (from public-apis directory) to geocode addresses,
landmarks, and destinations into real geographic coordinates and formatted locations.
No API key required; supports an optional NOMINATIM_USER_AGENT env var.
"""

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List


def lookup_destination_coordinates(query: str, city: str = "San Francisco") -> Dict[str, Any]:
    """Look up real-world geographic coordinates, neighborhood, and exact address for a destination.

    Uses the OpenStreetMap Nominatim Geocoding API (free public API).

    Args:
        query: Destination, landmark, venue, or street address (e.g., 'Ferry Building', 'Oracle Park', '444 Stockton St').
        city: City to scope the search to (defaults to 'San Francisco').

    Returns:
        A dictionary containing latitude, longitude, formatted display name, and location type.
    """
    search_query = f"{query}, {city}" if city.lower() not in query.lower() else query
    encoded_query = urllib.parse.quote(search_query)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&limit=1&addressdetails=1"

    # User-Agent header (defaults to app name or reads from NOMINATIM_USER_AGENT env var)
    user_agent = os.getenv("NOMINATIM_USER_AGENT", "SpotScoutParkingFinder/1.0 (GoogleAgentPlatform)")
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode())
            if not data:
                return {
                    "found": False,
                    "query": query,
                    "message": f"Could not find coordinates for '{query}'. Please check the spelling or provide a nearby landmark.",
                }

            top_match = data[0]
            lat = float(top_match.get("lat", 0.0))
            lon = float(top_match.get("lon", 0.0))
            display_name = top_match.get("display_name", "")
            address_details = top_match.get("address", {})

            return {
                "found": True,
                "query": query,
                "latitude": lat,
                "longitude": lon,
                "formatted_address": display_name,
                "neighbourhood": address_details.get("neighbourhood") or address_details.get("suburb", "San Francisco"),
                "road": address_details.get("road", ""),
                "postcode": address_details.get("postcode", ""),
            }
    except Exception as e:
        return {
            "found": False,
            "query": query,
            "error": f"Failed to connect to geocoding service: {str(e)}",
        }


def discover_nearby_parking_spots(latitude: float, longitude: float, radius_km: float = 1.5) -> List[Dict[str, Any]]:
    """Discovers real-world parking garages, surface lots, and facilities near coordinates using OpenStreetMap.

    Args:
        latitude: Target latitude coordinate.
        longitude: Target longitude coordinate.
        radius_km: Search radius in kilometers (defaults to 1.5km).

    Returns:
        A list of real-world parking facilities with names, coordinates, and types.
    """
    # Degree offset for bounding box (~0.01 deg ~= 1.1km)
    delta = (radius_km / 111.0) * 1.2
    min_lat = latitude - delta
    max_lat = latitude + delta
    min_lon = longitude - delta
    max_lon = longitude + delta

    viewbox = f"{min_lon:.5f},{max_lat:.5f},{max_lon:.5f},{min_lat:.5f}"
    url = f"https://nominatim.openstreetmap.org/search?amenity=parking&bounded=1&viewbox={viewbox}&format=json&limit=10&addressdetails=1"

    user_agent = os.getenv("NOMINATIM_USER_AGENT", "SpotScoutParkingFinder/1.0 (GoogleAgentPlatform)")
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            items = json.loads(response.read().decode())
            results = []
            for item in items:
                raw_name = item.get("name")
                disp = item.get("display_name", "").split(",")[0].strip()
                name = raw_name or (disp if "parking" in disp.lower() or "garage" in disp.lower() else f"{disp} Parking")
                
                addr = item.get("address", {})
                neighborhood = addr.get("neighbourhood") or addr.get("suburb") or addr.get("city_district") or "Metro Area"
                road = addr.get("road", "")
                city_name = addr.get("city") or addr.get("town") or "Metro"

                results.append({
                    "name": name,
                    "address": f"{road}, {city_name}".strip(", "),
                    "neighborhood": neighborhood,
                    "city": city_name.lower().replace(" ", "_"),
                    "latitude": float(item.get("lat", 0.0)),
                    "longitude": float(item.get("lon", 0.0)),
                    "osm_id": item.get("osm_id"),
                })
            return results
    except Exception as e:
        return []

