# SpotScout (Smart City Parking Finder)

An intelligent, multi-modal conversational agent that helps drivers navigate San Francisco's complex parking ecosystem. SpotScout finds parking options, computes real-time fee estimates, queries live garage occupancy and clearance restrictions from Google Cloud Firestore, remembers driver preferences across sessions with Vertex AI Memory Bank, renders interactive A2UI cards, and generates visual entrance guides and approach videos using Google's Gemini multimodal models.

![SpotScout Demo](./demo.gif)

---

## What the Agent Actually Does

SpotScout is built using the **Agent Development Kit (ADK)** and the **Gemini 3.6 Flash** model, supported by an array of specialized tools and Google Cloud integrations:

### 1. Dynamic Web Grounding & Worldwide Real-Time Search (Zero Hardcoding)
- **`google_search`**: Grounded with Google Search to dynamically verify official municipal tariffs, entrance overhead clearances (e.g., 6'5", 6'8", 7'2"), operating hours, and daily caps for ANY city or landmark worldwide directly from official garage operators and city transportation agencies.
- **`search_parking_spots`**: Dynamically queries OpenStreetMap (OSM) / Nominatim APIs to discover real-world parking garages and surface facilities around any address or landmark without hardcoded database entries.
- **`lookup_destination_coordinates`**: Resolves landmarks, venues, and street intersections into precise geographic coordinates worldwide.
- **`get_current_time`**: Evaluates active local time to account for time-sensitive parking rules and evening/weekend rate tiers.

### 2. Long-Term Cross-Session Memory (Vertex AI Memory Bank)
- **`PreloadMemoryTool`**: Injects relevant past facts and preferences (such as EV vs. gas vehicle type, vehicle clearance height, budget tolerances, and frequent destinations) into the agent's context at the start of a conversation.
- **`generate_memories_callback`**: Executes after each conversation turn to distill durable driver preferences and persist them to the managed Vertex AI Memory Bank.

### 3. Interactive Display UI (A2UI) & Dynamic Driver HUD
- Uses an **`after_model_callback` (`a2ui_callback`)** and custom web frontend to intercept and translate model output into rich, structured A2UI display cards:
  - **Dynamic Telemetry Grid**: Automatically shows verified Hourly Rate, Total Physical Capacity, EV Plugs, and Vehicle Clearance.
  - **Dynamic Omission**: Telemetry cells with unverified data (`N.A.`) are cleanly omitted, presenting drivers with only verified truths.
  - **Option A Transparency**: Never fabricates static open stall counts; displays known physical capacity and notes that live slots fluctuate.
  - **Direct Google Maps Navigation**: One-tap navigation button directly opens turn-by-turn directions to the verified address.

### 4. Official Parking Regulations & Municipal Knowledge Base (Vertex AI RAG Engine)
- **`consult_sf_parking_regulations`**: Searches an official SFMTA municipal regulations corpus managed in Vertex AI RAG Engine (serverless mode with `text-embedding-005` in `us-central1`). Grounded on official curb color codes, street sweeping schedules, 72-hour limits, driveway clearance, and hill wheel curbing laws.

### 5. Multi-Modal Visuals & Video Generation (Cloud Storage)
- **`generate_parking_spot_visual`**: Generates high-resolution entrance and signage images using **`gemini-3.1-flash-lite-image`** in the `global` region. Saves the image as a session artifact in ADK and streams the image bytes directly to a public Google Cloud Storage bucket (`spot-scout-qwiklabs-gcp-03-d27323349804`).
- **`generate_parking_spot_video`**: Generates 3-second entrance approach videos using Google's Omni model (**`gemini-omni-flash-preview`**) via the Interactions API. Persists the video via `tool_context.save_artifact` and uploads bytes to Cloud Storage, returning a public HTTPS URL.

---

## Architecture & Google Cloud Services

| Service | Purpose | Implementation |
|---|---|---|
| **Gemini 3.6 Flash** | Core reasoning, conversational logic, and tool orchestration | `google.adk.models.Gemini` |
| **Google Search Grounding** | Dynamic real-time verification of clearance heights, official tariffs, and hours worldwide | `google.adk.tools.google_search` |
| **OpenStreetMap & Nominatim** | Worldwide geographic amenity and facility discovery | Dynamic OSM API queries |
| **Vertex AI RAG Engine** | Grounding on official SF municipal parking and curb regulations | Serverless Vector Search + `text-embedding-005` in `us-central1` |
| **Vertex AI Memory Bank** | Long-term memory across sessions | `PreloadMemoryTool` & `add_session_to_memory()` |
| **Cloud Storage** | Public hosting for generated entrance visuals and videos | `google.cloud.storage.Client` |
| **Cloud Run** | Serverless hosting for the web chat frontend and A2A proxy | Fully managed Cloud Run container |
| **Gemini 3.1 Flash Lite Image** | Exterior architectural entrance and signage generation | `genai.Client(location="global")` |
| **Gemini Omni Flash Preview** | Dynamic approach video generation | `genai.Client.interactions.create` |
| **A2A (Agent-to-Agent Protocol)** | Protocol bridging frontend chat interface to ADK Agent Runtime | FastAPI async proxy streaming SSE events |

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
