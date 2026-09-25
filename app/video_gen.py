"""Video generation tool for SpotScout.

Generates realistic parking visual guides and approach videos
using Google's Omni model (gemini-omni-flash-preview) in the global region via the Interactions API.
(1) Saves the video artifact with tool_context.save_artifact so it shows up in Playground Artifacts.
(2) Uploads the video bytes directly to the public Cloud Storage bucket and returns its public URL.
"""

import base64
import time
import uuid
from typing import Any, Dict

from google import genai
from google.adk.tools.tool_context import ToolContext
from google.cloud import storage
from google.genai import types

PROJECT_ID = "qwiklabs-gcp-03-d27323349804"
BUCKET_NAME = "spot-scout-qwiklabs-gcp-03-d27323349804"
VIDEO_MODEL = "gemini-omni-flash-preview"


async def generate_parking_spot_video(
    spot_name_or_prompt: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """Generate a short video entrance guide or street approach for a parking location or landmark.

    Generates the video using Google's Omni model (gemini-omni-flash-preview) in the global region,
    saves it as a session artifact (viewable in the Playground Artifacts panel),
    and uploads the video bytes directly to the public Cloud Storage bucket.

    Args:
        spot_name_or_prompt: Name of the parking spot, garage entrance description, or visual scene
                             (e.g., 'Sutter-Stockton Garage Bush St entrance', 'Portsmouth Square garage approach').
        tool_context: ADK ToolContext injected by the framework to store session artifacts.

    Returns:
        A dictionary containing the public GCS video URL, filename, and artifact version.
    """
    enhanced_prompt = (
        f"A realistic 3-second dashcam/street-level video showing a car approaching and turning into "
        f"the vehicle entrance of {spot_name_or_prompt} in San Francisco, showing entrance signage and clearance."
    )

    # Initialize genai Client targeting Vertex AI with location='global'
    genai_client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location="global",
    )

    # Call Gemini Omni Flash model via the Interactions API
    interaction = genai_client.interactions.create(
        model=VIDEO_MODEL,
        input=enhanced_prompt,
        response_format={"type": "video"},
    )

    video_bytes = None
    mime_type = "video/mp4"

    if hasattr(interaction, "output_video") and interaction.output_video is not None:
        ov = interaction.output_video
        if getattr(ov, "data", None):
            video_bytes = base64.b64decode(ov.data)
            if getattr(ov, "mime_type", None):
                mime_type = ov.mime_type
    elif getattr(interaction, "steps", None):
        for step in interaction.steps:
            if getattr(step, "type", None) == "model_output":
                for item in getattr(step, "content", []):
                    if getattr(item, "type", None) == "video" and getattr(item, "data", None):
                        video_bytes = base64.b64decode(item.data)
                        if getattr(item, "mime_type", None):
                            mime_type = item.mime_type
                        break

    if not video_bytes:
        return {
            "success": False,
            "error": "No video was returned by the Omni model.",
        }

    # Prepare Part object for ToolContext.save_artifact
    video_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)

    # Unique filename
    clean_name = "".join(c if c.isalnum() else "_" for c in spot_name_or_prompt.lower()[:30]).strip("_")
    filename = f"{clean_name}_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4"

    # (1) Save artifact in session context so it shows up in Playground's Artifacts panel
    artifact_version = await tool_context.save_artifact(
        filename=filename,
        artifact=video_part,
        custom_metadata={"prompt": spot_name_or_prompt, "model": VIDEO_MODEL},
    )

    # (2) Upload video bytes directly to public Cloud Storage bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

    return {
        "success": True,
        "spot_name_or_prompt": spot_name_or_prompt,
        "filename": filename,
        "artifact_version": artifact_version,
        "public_url": public_url,
        "mime_type": mime_type,
    }
