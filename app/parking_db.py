"""Firestore database tools for SpotScout agent.

Hardcodes project ID as 'qwiklabs-gcp-03-d27323349804' per Agent Platform requirements.
"""

import datetime
from typing import Any, Dict, List, Optional
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-d27323349804"


def _get_db() -> firestore.Client:
    return firestore.Client(project=PROJECT_ID)


def list_supported_cities() -> List[str]:
    """Returns a list of cities currently supported by the SpotScout parking finder."""
    return ["san_francisco", "sf", "new_york", "nyc", "chicago", "seattle", "los_angeles", "austin", "global"]


def _calculate_realtime_occupancy(total_spaces: int, neighborhood: str, hourly_rate: float) -> tuple[int, str, str]:
    """Dynamically models real-world parking occupancy based on time of day, capacity, and rate."""
    now = datetime.datetime.now()
    hour = now.hour
    is_weekend = now.weekday() >= 5

    # Base rush profile (midday business hours higher, night lower)
    if 9 <= hour <= 17 and not is_weekend:
        fill_factor = 0.78  # Business peak
    elif 18 <= hour <= 22:
        fill_factor = 0.84 if is_weekend else 0.65  # Evening dining/entertainment
    elif hour >= 23 or hour <= 6:
        fill_factor = 0.25  # Overnight
    else:
        fill_factor = 0.55

    occupied = int(total_spaces * fill_factor)
    avail = max(3, total_spaces - occupied)
    pct = (occupied / total_spaces) * 100

    if avail <= 8 or pct >= 92:
        return avail, "almost_full", "Almost full! Limited remaining stalls. Expect delays at entry."
    elif pct >= 65:
        return avail, "filling_up", "Filling up steadily. Stalls available on upper and inner levels."
    else:
        return avail, "ample", "Ample parking available. Easy direct entry and clear stalls."


def search_parking_spots(
    neighborhood: Optional[str] = None,
    city: str = "san_francisco",
    max_hourly_rate: Optional[float] = None,
    min_clearance_inches: Optional[int] = None,
    requires_ev_charging: Optional[bool] = None,
    spot_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Dynamically search and discover real-world parking spots near any location or landmark worldwide via OpenStreetMap API.

    Args:
        neighborhood: Target neighborhood, destination, or landmark (e.g. 'Union Square', 'Yerba Buena', 'Times Square').
        city: The city to search in. Default is 'san_francisco'.
        max_hourly_rate: Maximum hourly price budget.
        min_clearance_inches: Minimum vehicle vertical clearance in inches.
        requires_ev_charging: Whether the spot must have electric vehicle chargers.
        spot_type: Desired parking type ('garage', 'surface_lot', 'metered_street').

    Returns:
        A list of real-world parking facilities discovered dynamically from the map API.
    """
    search_query = neighborhood or city or "parking"
    results = []

    try:
        from app.geocoding import lookup_destination_coordinates, discover_nearby_parking_spots

        coords = lookup_destination_coordinates(search_query, city=city)
        if coords.get("found"):
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            discovered = discover_nearby_parking_spots(lat, lon, radius_km=2.0)

            for item in discovered:
                spot_id = f"osm-{item.get('osm_id', abs(hash(item['name']))) % 1000000}"
                # Strictly use dynamic API values. Do NOT invent rates or fake space counts.
                dynamic_spot = {
                    "id": spot_id,
                    "name": item["name"],
                    "address": item["address"] or "N.A.",
                    "city": city.lower().replace(" ", "_"),
                    "neighborhood": item["neighborhood"] or search_query,
                    "hourly_rate": None,
                    "daily_max": None,
                    "spot_type": "garage" if "garage" in item["name"].lower() else "surface_lot",
                    "clearance_height_inches": None,
                    "has_ev_charging": False,
                    "ev_chargers_count": 0,
                    "covered": True if "garage" in item["name"].lower() else False,
                    "security_level": "N.A.",
                    "total_spaces": None,
                    "available_spaces": None,
                    "driver_tip": f"Location: {item['address'] if item['address'] else 'N.A.'}. Specific real-time rates or live capacity not published by map API (N.A.).",
                }

                results.append(dynamic_spot)
                if len(results) >= 4:
                    break
    except Exception as e:
        pass

    return results


def get_parking_spot_details(spot_id: str) -> Dict[str, Any]:
    """Retrieve detailed information, restrictions, and entry tips for a specific parking spot.

    Args:
        spot_id: The unique ID of the parking spot (e.g., 'sf-sutter-stockton').

    Returns:
        Full details of the parking spot, or an error dictionary if not found.
    """
    db = _get_db()
    doc = db.collection("parking_spots").document(spot_id).get()
    if not doc.exists:
        return {"error": f"Parking spot with ID '{spot_id}' not found."}

    data = doc.to_dict()
    data["id"] = doc.id
    return data


def add_parking_spot(
    spot_id: str,
    name: str,
    neighborhood: str,
    address: str,
    hourly_rate: float,
    daily_max: float,
    spot_type: str = "garage",
    clearance_height_inches: int = 80,
    has_ev_charging: bool = False,
    ev_chargers_count: int = 0,
    covered: bool = True,
    security_level: str = "medium",
    restrictions: str = "",
    entry_tip: str = "",
    city: str = "san_francisco",
    total_spaces: int = 100,
    available_spaces: int = 20,
) -> Dict[str, Any]:
    """Add or register a new parking spot or lot into the Firestore database.

    Args:
        spot_id: Unique identifier for the spot (e.g. 'sf-embarcadero-center').
        name: Name of the garage or parking area.
        neighborhood: Neighborhood location.
        address: Full street address.
        hourly_rate: Base hourly parking rate.
        daily_max: Daily maximum flat rate.
        spot_type: Type of spot ('garage', 'surface_lot', 'metered_street').
        clearance_height_inches: Vertical clearance limit in inches.
        has_ev_charging: True if EV charging is available.
        ev_chargers_count: Number of EV charging stalls.
        covered: Whether parking is covered/sheltered.
        security_level: Security level ('high', 'medium', 'unattended').
        restrictions: Parking limits, hours, street sweeping, or height warnings.
        entry_tip: Driver instructions on which street or alley to enter from.
        city: City name (defaults to 'san_francisco').
        total_spaces: Total vehicle capacity.
        available_spaces: Currently available spaces.

    Returns:
        Status dictionary confirming creation.
    """
    db = _get_db()
    data = {
        "id": spot_id,
        "city": city,
        "name": name,
        "neighborhood": neighborhood,
        "address": address,
        "spot_type": spot_type,
        "total_spaces": total_spaces,
        "available_spaces": available_spaces,
        "hourly_rate": hourly_rate,
        "daily_max": daily_max,
        "clearance_height_inches": clearance_height_inches,
        "has_ev_charging": has_ev_charging,
        "ev_chargers_count": ev_chargers_count,
        "covered": covered,
        "security_level": security_level,
        "restrictions": restrictions,
        "entry_tip": entry_tip,
    }
    db.collection("parking_spots").document(spot_id).set(data)
    return {"status": "success", "message": f"Parking spot '{name}' registered successfully.", "spot": data}


def update_spot_availability(spot_id: str, available_spaces: int) -> Dict[str, Any]:
    """Update real-time available spaces for a parking spot.

    Args:
        spot_id: The ID of the parking spot.
        available_spaces: The new count of free spaces.

    Returns:
        Status dictionary confirming the update.
    """
    db = _get_db()
    doc_ref = db.collection("parking_spots").document(spot_id)
    doc = doc_ref.get()
    if not doc.exists:
        return {"error": f"Parking spot '{spot_id}' not found."}

    doc_ref.update({"available_spaces": available_spaces})
    return {"status": "success", "spot_id": spot_id, "available_spaces": available_spaces}


def calculate_parking_fee(
    spot_id: str,
    duration_hours: float,
    is_early_bird: bool = False,
) -> Dict[str, Any]:
    """Calculate the estimated parking fee for a spot based on hours stayed and rate structure.

    Args:
        spot_id: The unique ID of the parking spot (e.g. 'sf-sutter-stockton').
        duration_hours: The number of hours the driver plans to park (e.g. 2.5 or 5.0).
        is_early_bird: Whether early bird entry conditions are met (e.g., entered before 9:00 AM on a weekday).

    Returns:
        A breakdown of the parking fee including base rate, daily max cap, and total estimated price.
    """
    if duration_hours <= 0:
        return {"error": "duration_hours must be greater than 0."}

    db = _get_db()
    doc = db.collection("parking_spots").document(spot_id).get()
    if not doc.exists:
        return {"error": f"Parking spot '{spot_id}' not found."}

    spot = doc.to_dict()
    hourly_rate = spot.get("hourly_rate")
    daily_max = spot.get("daily_max")
    spot_name = spot.get("name", spot_id)

    if hourly_rate is None:
        return {
            "spot_id": spot_id,
            "spot_name": spot_name,
            "duration_hours": duration_hours,
            "hourly_rate": "N.A.",
            "daily_max": "N.A.",
            "total_estimated_fee": "N.A.",
            "note": "Pricing information is not available (N.A.) for this location.",
        }

    hourly_rate = float(hourly_rate)
    daily_max = float(daily_max) if daily_max is not None else 0.0

    # Standard hourly calculation
    raw_cost = round(hourly_rate * duration_hours, 2)

    # Apply early-bird flat discount if applicable (e.g. 20% discount on daily max for early birds)
    effective_daily_max = daily_max
    discount_note = None
    if is_early_bird and daily_max > 0:
        effective_daily_max = round(daily_max * 0.80, 2)
        discount_note = f"Early-bird discount applied: daily max reduced from ${daily_max:.2f} to ${effective_daily_max:.2f}."

    # Compare raw hourly vs daily cap
    daily_cap_applied = False
    if effective_daily_max > 0 and raw_cost > effective_daily_max:
        final_fee = effective_daily_max
        daily_cap_applied = True
    else:
        final_fee = raw_cost

    return {
        "spot_id": spot_id,
        "spot_name": spot_name,
        "duration_hours": duration_hours,
        "hourly_rate": hourly_rate,
        "daily_max": daily_max,
        "raw_cost": raw_cost,
        "daily_cap_applied": daily_cap_applied,
        "total_estimated_fee": final_fee,
        "notes": discount_note or ("Daily maximum cap applied." if daily_cap_applied else "Standard hourly billing."),
    }


def check_spot_occupancy_status(
    spot_id: str,
) -> Dict[str, Any]:
    """Check live occupancy, available stalls, and capacity status for a specific parking spot or garage.

    Args:
        spot_id: The unique ID of the parking spot (e.g. 'sf-sutter-stockton', 'sf-portsmouth-square').

    Returns:
        A dictionary containing live occupancy percentage, available spaces, total capacity,
        and an availability status indicator ('ample', 'filling_up', 'almost_full', 'full').
    """
    db = _get_db()
    doc = db.collection("parking_spots").document(spot_id).get()
    if not doc.exists:
        return {"error": f"Parking spot '{spot_id}' not found."}

    spot = doc.to_dict()
    total_spaces = spot.get("total_spaces")
    available_spaces = spot.get("available_spaces")
    name = spot.get("name", spot_id)
    neighborhood = spot.get("neighborhood", "")

    if available_spaces is None:
        return {
            "spot_id": spot_id,
            "name": name,
            "neighborhood": neighborhood,
            "total_spaces": total_spaces if total_spaces else "N.A.",
            "available_spaces": "N.A.",
            "occupancy_rate_percent": "N.A.",
            "status": "N.A.",
            "status_message": f"Total capacity is {total_spaces} spaces; however, live real-time slot availability fluctuates continuously and is not published statically." if total_spaces else "Real-time occupancy data is not published (N.A.) for this location.",
            "has_ev_charging": spot.get("has_ev_charging", False),
            "ev_chargers_count": spot.get("ev_chargers_count", 0),
            "entry_tip": spot.get("entry_tip", ""),
        }

    total_spaces = int(total_spaces)
    available_spaces = int(available_spaces)
    occupied_spaces = max(0, total_spaces - available_spaces)
    occupancy_pct = round((occupied_spaces / total_spaces) * 100, 1)

    if available_spaces <= 0:
        status = "full"
        status_message = "Garage is FULL. No stalls currently available."
    elif available_spaces <= 15 or occupancy_pct >= 90:
        status = "almost_full"
        status_message = "Almost full! Few stalls remaining. High likelihood of having to wait or hunt."
    elif occupancy_pct >= 70:
        status = "filling_up"
        status_message = "Filling up steadily. Stalls available on upper/inner levels."
    else:
        status = "ample"
        status_message = "Ample parking available. Easy entry and open stalls."

    return {
        "spot_id": spot_id,
        "name": name,
        "neighborhood": neighborhood,
        "total_spaces": total_spaces,
        "available_spaces": available_spaces,
        "occupancy_rate_percent": occupancy_pct,
        "status": status,
        "status_message": status_message,
        "has_ev_charging": spot.get("has_ev_charging", False),
        "ev_chargers_count": spot.get("ev_chargers_count", 0),
        "entry_tip": spot.get("entry_tip", ""),
    }


