# SpotScout (Smart City Parking Finder)

An intelligent, multi-modal conversational agent that helps drivers navigate San Francisco's complex parking ecosystem. SpotScout finds parking options, computes real-time fee estimates, queries live garage occupancy and clearance restrictions from Google Cloud Firestore, remembers driver preferences across sessions with Vertex AI Memory Bank, renders interactive A2UI cards, and generates visual entrance guides and approach videos using Google's Gemini multimodal models.

![SpotScout Demo](./demo.gif)

---

## What the Agent Actually Does

SpotScout is built using the **Agent Development Kit (ADK)** and the **Gemini 3.6 Flash** model, supported by an array of specialized tools and Google Cloud integrations:

### 1. Parking Search & Real-Time Firestore Database
- **`search_parking_spots`**: Queries Google Cloud Firestore (`parking_spots` collection) to filter garages, lots, and metered zones by neighborhood/destination, rate, clearance height, and EV charging support.
- **`check_spot_occupancy_status`**: Reads live occupancy metrics, open space counts, and full/available status directly from Firestore.
- **`get_parking_spot_details`**: Retrieves comprehensive spot metadata (exact street address, vehicle height limits, security level, operating hours).
- **`calculate_parking_fee`**: Calculates tiered parking totals based on hourly rates, daily maximums, early bird discounts, and requested stay duration.
- **`add_parking_spot` & `update_spot_availability`**: Dynamically onboards new parking facilities or updates available space counts in Firestore.
- **`list_supported_cities`**: Lists active and planned coverage areas.

### 2. Destination Geocoding & Local Time
- **`lookup_destination_coordinates`**: Resolves San Francisco neighborhoods, landmarks, and street intersections into geographic coordinates and standardized bounding areas.
- **`get_current_time`**: Evaluates active local time in `America/Los_Angeles` to account for time-sensitive parking rules and evening/weekend rate tiers.

### 3. Long-Term Cross-Session Memory (Vertex AI Memory Bank)
- **`PreloadMemoryTool`**: Injects relevant past facts and preferences (such as EV vs. gas vehicle type, vehicle clearance height, budget tolerances, and frequent destinations like SoMa or Union Square) into the agent's context at the start of a conversation.
- **`generate_memories_callback`**: Executes after each conversation turn to distill durable driver preferences and persist them to the managed Vertex AI Memory Bank.

### 4. Interactive Display UI (A2UI)
- Uses an **`after_model_callback` (`a2ui_callback`)** to intercept and translate model output into rich, structured A2UI display cards and tables:
  - Parking spot summary cards with rate tags, distance, and amenity badges.
  - Side-by-side comparison tables evaluating rates, clearance, and features across multiple garages.

### 5. Official Parking Regulations & Municipal Knowledge Base (Vertex AI RAG Engine)
- **`consult_sf_parking_regulations`**: Searches an official SFMTA municipal regulations corpus managed in Vertex AI RAG Engine (serverless mode with `text-embedding-005` in `us-central1`). Grounded on official curb color codes, street sweeping schedules, 72-hour limits, driveway clearance, and hill wheel curbing laws.

### 6. Multi-Modal Visuals & Video Generation (Cloud Storage)
- **`generate_parking_spot_visual`**: Generates high-resolution entrance and signage images using **`gemini-3.1-flash-lite-image`** in the `global` region. Saves the image as a session artifact in ADK and streams the image bytes directly to a public Google Cloud Storage bucket (`spot-scout-qwiklabs-gcp-03-d27323349804`).
- **`generate_parking_spot_video`**: Generates 3-second entrance approach videos using Google's Omni model (**`gemini-omni-flash-preview`**) via the Interactions API. Persists the video via `tool_context.save_artifact` and uploads bytes to Cloud Storage, returning a public HTTPS URL.

---

## Architecture & Google Cloud Services

| Service | Purpose | Implementation |
|---|---|---|
| **Gemini 3.6 Flash** | Core reasoning, conversational logic, and tool orchestration | `google.adk.models.Gemini` |
| **Vertex AI RAG Engine** | Grounding on official SF municipal parking and curb regulations | Serverless Vector Search + `text-embedding-005` in `us-central1` |
| **Vertex AI Memory Bank** | Long-term memory across sessions | `PreloadMemoryTool` & `add_session_to_memory()` |
| **Cloud Firestore** | Real-time parking catalog, live occupancy, and rates | `google.cloud.firestore.Client` |
| **Cloud Storage** | Public hosting for generated entrance visuals and videos | `google.cloud.storage.Client` |
| **Gemini 3.1 Flash Lite Image** | Exterior architectural entrance and signage generation | `genai.Client(location="global")` |
| **Gemini Omni Flash Preview** | Dynamic approach video generation | `genai.Client.interactions.create` |
| **A2A (Agent-to-Agent Protocol)** | Protocol bridging frontend chat interface to ADK Agent Runtime | FastAPI async proxy streaming SSE events |

---

## Planned Capabilities (Not Yet Implemented)

The following features from the initial project design brief are currently roadmap items:
- **SFMTA Open Data API Integration**: Real-time integration with live city street sweeping sensors and parking meters *(currently simulated via Firestore)*.
- **Python Code Execution Sandbox**: Running custom mathematical optimization scripts for meter expiration curves.

---

## Local Setup & Run Instructions

### Prerequisites
- Python 3.11+
- Google Cloud SDK (`gcloud`) authenticated to your GCP project
- Application Default Credentials set up:
  ```bash
  gcloud auth login
  gcloud auth application-default login
  ```

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/AakashSunil/buildwithgemini-spot-scout.git
cd buildwithgemini-spot-scout

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Agent Locally (ADK Web)
To test the agent inside the ADK Playground:
```bash
adk web --port 8000
```
Open your browser to `http://127.0.0.1:8000/dev-ui/?app=app` to interact with SpotScout, inspect tool calls, and view session artifacts.

### 3. Run the Custom Frontend Locally
To test the web frontend and A2UI renderer:
```bash
cd frontend
pip install -r requirements.txt
python main.py
```
Then navigate to `http://localhost:8080` in your web browser.
