"""Seed script to populate Firestore with initial San Francisco parking spots.

Hardcodes project ID as 'qwiklabs-gcp-03-d27323349804' per Agent Platform requirements.
"""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-d27323349804"

SEED_SPOTS = [
    {
        "id": "sf-sutter-stockton",
        "city": "san_francisco",
        "name": "Sutter-Stockton Garage",
        "neighborhood": "Union Square",
        "address": "444 Stockton St, San Francisco, CA 94108",
        "spot_type": "garage",
        "total_spaces": 1865,
        "available_spaces": 340,
        "hourly_rate": 4.50,
        "daily_max": 36.00,
        "clearance_height_inches": 80,  # 6'8"
        "has_ev_charging": True,
        "ev_chargers_count": 20,
        "covered": True,
        "security_level": "high",  # attendant + cameras
        "restrictions": "No oversized vehicles over 6'8\". Overnight parking allowed.",
        "entry_tip": "Enter from Stockton St or Bush St. The Bush St entrance is usually less congested.",
    },
    {
        "id": "sf-fifth-mission",
        "city": "san_francisco",
        "name": "Fifth & Mission / Yerba Buena Garage",
        "neighborhood": "SoMa",
        "address": "833 Mission St, San Francisco, CA 94103",
        "spot_type": "garage",
        "total_spaces": 2585,
        "available_spaces": 620,
        "hourly_rate": 4.00,
        "daily_max": 34.00,
        "clearance_height_inches": 78,  # 6'6"
        "has_ev_charging": True,
        "ev_chargers_count": 36,
        "covered": True,
        "security_level": "high",
        "restrictions": "No trailers. 24/7 security on duty.",
        "entry_tip": "Primary vehicle entrance on Mission St between 4th and 5th, with a secondary entry on Minna St.",
    },
    {
        "id": "sf-portsmouth-square",
        "city": "san_francisco",
        "name": "Portsmouth Square Plaza Garage",
        "neighborhood": "Chinatown",
        "address": "733 Kearny St, San Francisco, CA 94108",
        "spot_type": "garage",
        "total_spaces": 500,
        "available_spaces": 45,
        "hourly_rate": 4.00,
        "daily_max": 32.00,
        "clearance_height_inches": 74,  # 6'2" - tight clearance!
        "has_ev_charging": False,
        "ev_chargers_count": 0,
        "covered": True,
        "security_level": "medium",
        "restrictions": "Strict 6'2\" clearance. Tall SUVs and roof racks will scrape.",
        "entry_tip": "Underground entrance off Kearny St just past Clay St.",
    },
    {
        "id": "sf-valencia-metered-16th",
        "city": "san_francisco",
        "name": "Valencia Corridor Metered Parking",
        "neighborhood": "Mission",
        "address": "Valencia St & 16th St, San Francisco, CA 94110",
        "spot_type": "metered_street",
        "total_spaces": 35,
        "available_spaces": 6,
        "hourly_rate": 3.00,
        "daily_max": 24.00,
        "clearance_height_inches": 120,  # Open air street
        "has_ev_charging": False,
        "ev_chargers_count": 0,
        "covered": False,
        "security_level": "unattended",
        "restrictions": "2-hour limit Mon-Sat 9am-6pm. Street sweeping Tuesday 2am-6am. Check signs before leaving vehicle.",
        "entry_tip": "Look for spaces on side streets like 17th or Albion if Valencia is full.",
    },
    {
        "id": "sf-marina-green-lot",
        "city": "san_francisco",
        "name": "Marina Green East Parking Lot",
        "neighborhood": "Marina",
        "address": "Marina Blvd & Scott St, San Francisco, CA 94123",
        "spot_type": "surface_lot",
        "total_spaces": 210,
        "available_spaces": 85,
        "hourly_rate": 2.50,
        "daily_max": 18.00,
        "clearance_height_inches": 120,  # Open surface lot
        "has_ev_charging": True,
        "ev_chargers_count": 4,
        "covered": False,
        "security_level": "medium",
        "restrictions": "No parking 10pm-6am without permit. Pay by phone or station.",
        "entry_tip": "Direct entry from Marina Blvd westbound. Excellent spot for walks along the bay.",
    },
]


def seed_parking_spots():
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("parking_spots")

    print(f"Connecting to Firestore project: {PROJECT_ID}...")
    for spot in SEED_SPOTS:
        doc_id = spot["id"]
        collection_ref.document(doc_id).set(spot)
        print(f"Seeded parking spot: {spot['name']} ({doc_id})")

    print(f"Successfully seeded {len(SEED_SPOTS)} parking spots into 'parking_spots' collection.")


if __name__ == "__main__":
    seed_parking_spots()
