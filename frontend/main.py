"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.

Why A2A: agents-cli 1.1.0 (GA) deploys ADK agents to Agent Runtime as A2A agents
and no longer registers the reasoning-engine operation schema the old
`agent_engines.get(...).stream_query()` path relied on (operation_schemas() comes
back empty). The container serves the A2A protocol over the Agent Engine HTTP
passthrough, so this proxy fetches the agent's card and sends messages with the
a2a-sdk client (the same path `agents-cli run --mode a2a` uses). This works for
both A2A and plain ADK 1.1.0 deployments (the container serves A2A either way).

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  export AGENT_DIRECTORY="app"   # your agent's app directory (agents-cli-manifest.yaml)
  python main.py                 # -> http://localhost:8080
"""

import os
import uuid

import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    FilePart,
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TextPart,
    TransportProtocol,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

RESOURCE = os.environ.get("AGENT_ENGINE_RESOURCE_NAME")
# The agent's app directory (matches agent_directory in agents-cli-manifest.yaml).
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")

LOCAL_A2A_URL = os.environ.get("LOCAL_A2A_URL")

if LOCAL_A2A_URL:
    A2A_BASE = LOCAL_A2A_URL.rstrip("/")
    A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"
elif RESOURCE:
    # Location is embedded in the resource name: projects/<p>/locations/<loc>/reasoningEngines/<id>.
    LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]
    A2A_BASE = (
        f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
        f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
    )
    A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"
else:
    raise ValueError("Must set AGENT_ENGINE_RESOURCE_NAME or LOCAL_A2A_URL")


# The agent tags its A2UI data parts with this mime type.
_A2UI_MIME = "application/json+a2ui"

# One set of ADC credentials, refreshed per request (access tokens expire ~1h).
_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    # Always return JSON so the browser never receives a plain-text 500 page
    # (which shows up in the chat as "Unexpected token 'I', "Internal S"... is
    # not valid JSON"). Any server-side failure now surfaces as a readable
    # message in the chat bubble instead.
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


# Reuse ONE A2A context per user so the agent remembers the conversation.
_contexts: dict[str, str] = {}
# Cache the agent card after the first fetch.
_card: AgentCard | None = None


async def _get_card(client: httpx.AsyncClient) -> AgentCard:
    global _card
    if _card is None:
        resp = await client.get(A2A_CARD_URL)
        resp.raise_for_status()
        card = AgentCard(**resp.json())
        # Agent Runtime does not serve a public card URL, so point the client at
        # the passthrough base for message sends.
        card.url = A2A_BASE
        _card = card
    return _card


def _extract_parts(parts: list) -> list[dict]:
    """Turn A2A response parts into structured parts for the chat UI.

    Text parts pass through as {"kind": "text"}. A2UI data parts (tagged
    application/json+a2ui) become {"kind": "a2ui", "data": <message>} so the UI
    renders the card; each data part is one A2UI message (beginRendering or
    surfaceUpdate).
    """
    out: list[dict] = []
    for p in parts:
        root = getattr(p, "root", p)
        if isinstance(root, TextPart) and getattr(root, "text", None):
            out.append({"kind": "text", "text": root.text})
        elif getattr(root, "data", None) is not None:
            data_val = root.data
            meta = getattr(root, "metadata", None) or {}
            # Check if root.data itself is a wrapped dict like {'metadata': {'mimeType': ...}, 'data': ...}
            if isinstance(data_val, dict) and "data" in data_val:
                inner_meta = data_val.get("metadata") or {}
                mime = inner_meta.get("mimeType") if isinstance(inner_meta, dict) else None
                if mime == _A2UI_MIME:
                    out.append({"kind": "a2ui", "data": data_val["data"]})
                    continue
            mime = meta.get("mimeType") if isinstance(meta, dict) else None
            if mime == _A2UI_MIME:
                out.append({"kind": "a2ui", "data": data_val})
        elif isinstance(root, FilePart):
            uri = getattr(getattr(root, "file", None), "uri", None)
            if uri:
                out.append({"kind": "text", "text": uri})
    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        card = await _get_card(client)
        factory = ClientFactory(
            ClientConfig(
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                httpx_client=client,
            )
        )
        a2a_client = factory.create(card)

        msg = Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text=message))],
            context_id=_contexts.get(user_id),
        )

        last_task = None
        got_artifact_update = False
        async for event in a2a_client.send_message(msg):
            if not isinstance(event, tuple):
                continue
            task, update = event
            if task is not None:
                last_task = task
                if getattr(task, "context_id", None):
                    _contexts[user_id] = task.context_id
            if isinstance(update, TaskArtifactUpdateEvent):
                got_artifact_update = True
                parts.extend(_extract_parts(update.artifact.parts))

        # Non-streaming fallback: pull parts from the final task's artifacts.
        if not got_artifact_update and last_task is not None:
            for artifact in getattr(last_task, "artifacts", None) or []:
                parts.extend(_extract_parts(artifact.parts))

    if not parts:
        # The turn produced no text or UI (e.g. the agent only ran tools, or a
        # tool stalled). Be honest rather than silent.
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


async def _run_agent_query(user_query: str, user_id: str = "webhook-user") -> str:
    """Helper to query the agent engine and return a clean text response for bots/webhooks."""
    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        card = await _get_card(client)
        factory = ClientFactory(
            ClientConfig(
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                httpx_client=client,
            )
        )
        a2a_client = factory.create(card)
        msg = Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text=user_query))],
            context_id=_contexts.get(user_id),
        )

        extracted_texts = []
        async for event in a2a_client.send_message(msg):
            if not isinstance(event, tuple):
                continue
            task, update = event
            if task is not None and getattr(task, "context_id", None):
                _contexts[user_id] = task.context_id
            if isinstance(update, TaskArtifactUpdateEvent):
                for p in _extract_parts(update.artifact.parts):
                    if p.get("kind") == "text":
                        extracted_texts.append(p["text"])
                    elif p.get("kind") == "a2ui":
                        # Flatten A2UI components into clean text for chat apps
                        su = p.get("data", {}).get("surfaceUpdate", {})
                        for comp in su.get("components", []):
                            txt = comp.get("component", {}).get("Text", {}).get("text", {})
                            val = txt.get("literalString") if isinstance(txt, dict) else str(txt)
                            if val:
                                extracted_texts.append(val)

        reply = "\n".join(extracted_texts).strip()
        if not reply:
            reply = "SpotScout: No parking spots found matching your query."
        return reply


@app.post("/webhook/telegram")
async def webhook_telegram(req: Request):
    """Webhook endpoint for Telegram Bot API updates."""
    try:
        body = await req.json()
        message = body.get("message") or body.get("channel_post") or {}
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        user_id = str(message.get("from", {}).get("id", chat_id or "telegram-user"))

        if not text or not chat_id:
            return JSONResponse({"ok": True, "status": "ignored_non_text"})

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        reply_text = await _run_agent_query(text, user_id=f"tg-{user_id}")

        if bot_token:
            async with httpx.AsyncClient(timeout=10) as http_client:
                await http_client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": reply_text},
                )

        return JSONResponse({"ok": True, "chat_id": chat_id, "reply": reply_text})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/webhook/whatsapp")
@app.post("/webhook/sms")
async def webhook_twilio_whatsapp(req: Request):
    """Twilio SMS / WhatsApp Messaging Webhook endpoint."""
    form_data = await req.form()
    incoming_msg = form_data.get("Body", "")
    from_number = form_data.get("From", "twilio-user")

    reply = await _run_agent_query(incoming_msg, user_id=f"tw-{from_number}")
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply}</Message>
</Response>"""
    return JSONResponse(
        content={"reply": reply, "twiml": twiml_response},
        headers={"Content-Type": "application/json"}
    )


@app.post("/api/v1/query")
async def api_generic_query(req: Request):
    """Universal REST API endpoint for third-party bots, iOS shortcuts, and smart assistant webhooks."""
    body = await req.json()
    query = body.get("query") or body.get("message", "")
    user_id = body.get("user_id", "api-user")

    if not query:
        return JSONResponse({"error": "Missing 'query' parameter"}, status_code=400)

    reply = await _run_agent_query(query, user_id=user_id)
    return JSONResponse({
        "status": "success",
        "query": query,
        "reply": reply,
        "source": "SpotScout Vertex AI Agent Engine"
    })


# Serve the chat UI (keep this mount last so /chat and webhooks win).
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
