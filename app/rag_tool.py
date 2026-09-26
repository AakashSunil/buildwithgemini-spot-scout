"""RAG retrieval tool for SpotScout.

Queries official San Francisco parking rules, curb color codes, street sweeping,
and municipal parking restrictions indexed in Vertex AI RAG Engine (serverless mode).
Exposed as a plain function tool so it coexists safely with A2UI, Firestore, and media generation.
"""

import vertexai
from vertexai.preview import rag

PROJECT_ID = "qwiklabs-gcp-03-d27323349804"
LOCATION = "us-central1"
CORPUS_NAME = "projects/1018248709546/locations/us-central1/ragCorpora/3475573847585980416"

# Initialize vertexai client for RAG Engine in us-central1
vertexai.init(project=PROJECT_ID, location=LOCATION)


def consult_sf_parking_regulations(query: str) -> str:
    """Consult official San Francisco municipal parking regulations and curb rules via Vertex AI RAG Engine.

    Retrieves authoritative SFMTA rules for:
    - Curb color restrictions (red, yellow, white, green, blue)
    - 72-hour parking limits, street sweeping, and commute rush-hour tow-away zones
    - Hill parking and wheel curbing requirements
    - Residential Permit Parking (RPP) visitor stay limits

    Args:
        query: Specific municipal parking question or restriction to look up
               (e.g., 'rules for yellow curb loading', 'how to curb wheels on a hill', '72 hour rule').

    Returns:
        Authoritative rule passages retrieved from the official municipal parking regulations corpus.
    """
    try:
        resp = rag.retrieval_query(
            text=query,
            rag_resources=[rag.RagResource(rag_corpus=CORPUS_NAME)],
            rag_retrieval_config=rag.RagRetrievalConfig(top_k=3),
        )
    except Exception as e:
        return f"Regulation lookup unavailable: {e}"

    contexts = getattr(resp.contexts, "contexts", [])
    passages = [c.text.strip() for c in contexts if getattr(c, "text", "").strip()]
    return "\n\n---\n\n".join(passages) or "No specific parking regulation found matching the query."
