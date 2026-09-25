"""Image generation tool for SpotScout.

Generates realistic visual parking guides, entrance views, and landmark signage
using the gemini-3.1-flash-lite-image model in the global region.
Saves the artifact to tool_context for the ADK Playground and uploads bytes
directly to the public Google Cloud Storage bucket.
"""

import time
import uuid
from typing import Any, Dict

from google import genai
from google.adk.tools.tool_context import ToolContext
from google.cloud import storage
from google.genai import types

PROJECT_ID = "qwiklabs-gcp-03-d27323349804"
BUCKET_NAME = "spot-scout-qwiklabs-gcp-03-d27323349804"
IMAGE_MODEL = "gemini-3.1-flash-lite-image"


async def generate_parking_spot_visual(
    spot_name_or_prompt: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """Generate an architectural visual or entrance guide image for a parking location or landmark.

    Generates the image using gemini-3.1-flash-lite-image in the global region,
    saves the image as a session artifact (viewable in Playground Artifacts),
    and uploads the image bytes to the public Cloud Storage bucket.

    Args:
        spot_name_or_prompt: Name of the parking spot, garage entrance description, or visual scene
                             (e.g., 'Sutter-Stockton Garage Bush St entrance', 'Portsmouth Square underground garage entrance').
        tool_context: ADK ToolContext injected by the framework to store session artifacts.

    Returns:
        A dictionary containing the public GCS image URL and artifact metadata.
    """
    enhanced_prompt = (
        f"A clear, realistic architectural exterior photograph of the vehicle entrance and signage "
        f"for {spot_name_or_prompt} in San Francisco, showing vehicle clearance signs and street perspective, daytime."
    )

    # Initialize genai Client targeting Vertex AI with location='global'
    genai_client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location="global",
    )

    response = genai_client.models.generate_content(
        model=IMAGE_MODEL,
        contents=enhanced_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    image_part = None
    for part in response.parts:
        if part.inline_data:
            image_part = part
            break

    if not image_part or not image_part.inline_data:
        return {
            "success": False,
            "error": "No image was returned by the image generation model.",
        }

    image_bytes = image_part.inline_data.data
    mime_type = image_part.inline_data.mime_type or "image/jpeg"
    ext = "jpg" if "jpeg" in mime_type or "jpg" in mime_type else "png"

    # Unique filename
    clean_name = "".join(c if c.isalnum() else "_" for c in spot_name_or_prompt.lower()[:30]).strip("_")
    filename = f"{clean_name}_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"

    # (1) Save artifact in session context (async method)
    artifact_version = await tool_context.save_artifact(
        filename=filename,
        artifact=image_part,
        custom_metadata={"prompt": spot_name_or_prompt, "model": IMAGE_MODEL},
    )

    # (2) Upload image bytes directly to public Cloud Storage bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

    return {
        "success": True,
        "spot_name_or_prompt": spot_name_or_prompt,
        "filename": filename,
        "artifact_version": artifact_version,
        "public_url": public_url,
        "mime_type": mime_type,
    }
