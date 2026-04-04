from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import asyncio
import json
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from bson import ObjectId
from dotenv import load_dotenv
from backend.models.database import db
from backend.api.simulation import sim_controller

# Resolve .env from project root (2 levels up from this file)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=5)


class GenerateRequest(BaseModel):
    prompt: str
    stream: bool = False


class ChatRequest(BaseModel):
    message: str
    stream: bool = False


OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "https://api.groq.com/openai/v1/chat/completions")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama-3.1-8b-instant")

print(f"[LLM Config] URL={OLLAMA_API_URL}  Model={MODEL_NAME}  Key={'set (' + OLLAMA_API_KEY[:8] + '...)' if OLLAMA_API_KEY else 'MISSING'}")

# Build a requests session with automatic retries for connection resets
_http_session = requests.Session()
_retry = Retry(total=3, backoff_factor=1, allowed_methods=["POST"],
               status_forcelist=[429, 500, 502, 503, 504])
_http_session.mount("https://", HTTPAdapter(max_retries=_retry))


def _serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, bytes):
            result[key] = value.hex()
        else:
            result[key] = value
    return result


def get_mongodb_context() -> str:
    """Query all collections in port_db and build a summary for the LLM."""
    context_parts = []
    try:
        collection_names = db.list_collection_names()
        if not collection_names:
            return "The MongoDB database 'port_db' has no collections yet."

        context_parts.append(f"Database: port_db")
        context_parts.append(f"Collections: {', '.join(collection_names)}")
        context_parts.append("")

        for coll_name in collection_names:
            collection = db[coll_name]
            total_count = collection.estimated_document_count()
            context_parts.append(f"--- Collection: {coll_name} (Total documents: {total_count}) ---")

            # Get sample documents (up to 3) to keep prompt within token limits
            sample_docs = list(collection.find().sort("_id", -1).limit(3))
            if sample_docs:
                serialized = [_serialize_doc(doc) for doc in sample_docs]
                context_parts.append(f"Sample records (latest {len(serialized)}):")
                for i, doc in enumerate(serialized, 1):
                    context_parts.append(f"  {i}. {json.dumps(doc, default=str, ensure_ascii=False)}")
            else:
                context_parts.append("  (empty collection)")
            context_parts.append("")

        return "\n".join(context_parts)
    except Exception as e:
        return f"Error reading MongoDB: {str(e)}"


def get_collection_stats() -> str:
    """Get high-level stats about all collections."""
    try:
        stats_parts = []
        collection_names = db.list_collection_names()
        for coll_name in collection_names:
            collection = db[coll_name]
            count = collection.estimated_document_count()
            stats_parts.append(f"  - {coll_name}: {count} documents")
        return "\n".join(stats_parts) if stats_parts else "No collections found."
    except Exception as e:
        return f"Error: {str(e)}"


def get_live_simulation_context() -> str:
    """Build a snapshot of the live simulation state for the LLM."""
    if not sim_controller.is_running and not sim_controller.is_paused:
        return ""

    parts = []
    parts.append("=== LIVE SIMULATION STATE ===")
    clock_min = sim_controller.global_clock_ms / 60000
    parts.append(f"Simulation clock: {clock_min:.1f} virtual minutes elapsed")
    parts.append(f"Status: {'PAUSED' if sim_controller.is_paused else 'RUNNING'} at {sim_controller.playback_speed}x speed")
    parts.append(f"Anomaly mode: {sim_controller.anomaly_mode}")

    # Ship summary by zone
    zone_counts = {}
    for s in sim_controller.ships:
        z = s.zone.value
        zone_counts[z] = zone_counts.get(z, 0) + 1
    parts.append(f"\nShips by zone: {json.dumps(zone_counts)}")
    parts.append(f"Total ships: {len(sim_controller.ships)}")

    # Per-ship details (compact)
    parts.append("\nShip details:")
    for s in sim_controller.ships:
        line = (f"  {s.name or 'Ship-'+str(s.ship_id)} | zone={s.zone.value} | type={s.ship_type.value} "
                f"| score={s.priority_score:.3f} | fuel_crit={s.fuel_criticality:.2f} "
                f"| eta={s.eta_minutes:.0f}min | berth={s.assigned_berth_id or 'none'}")
        parts.append(line)

    # Berth status
    occupied = [b for b in sim_controller.berths if b.status == "Occupied"]
    free = [b for b in sim_controller.berths if b.status == "Free"]
    parts.append(f"\nBerths: {len(occupied)} occupied, {len(free)} free (total {len(sim_controller.berths)})")
    for b in sim_controller.berths:
        ship_info = f"ship={b.currently_docked_ship_id}, progress={b.cargo_processed_pct:.0f}%" if b.status == "Occupied" else "empty"
        parts.append(f"  Berth {b.berth_id} ({b.name}): {b.status} | {ship_info} | equip={b.equipment_types}")

    # Metrics
    m = sim_controller.metrics
    parts.append(f"\nMetrics:")
    parts.append(f"  Ships processed: {m.get('total_ships_processed', 0)}")
    parts.append(f"  Avg waiting time: {m.get('avg_waiting_time_min', 0):.1f} min")
    parts.append(f"  Berth utilization: {m.get('berth_utilization_pct', 0):.1f}%")
    parts.append(f"  Throughput/hour: {m.get('throughput_per_hour', 0):.1f}")
    parts.append(f"  Reshuffles: {m.get('total_reshuffles', 0)}")
    parts.append(f"  Deadlocks: {m.get('total_deadlocks', 0)}")

    # Recent events (last 10)
    recent = sim_controller.events_log[-10:]
    if recent:
        parts.append(f"\nRecent events (last {len(recent)}):")
        for ev in recent:
            parts.append(f"  [{ev.timestamp_ms}ms] {ev.event_type}: ship={ev.ship_id} {ev.details}")

    return "\n".join(parts)


def sync_ollama_call(prompt: str, stream: bool = False):
    if not OLLAMA_API_KEY:
        raise HTTPException(status_code=500, detail="Ollama API key is missing. Set OLLAMA_API_KEY.")

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "You are a smart database assistant. Answer accurately using provided context."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "stream": stream,
    }
    headers = {
        "Authorization": f"Bearer {OLLAMA_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = _http_session.post(OLLAMA_API_URL, json=payload, headers=headers, timeout=60)
        if response.status_code != 200:
            body = response.text[:500]
            print(f"[LLM ERROR] HTTP {response.status_code}: {body}")
        response.raise_for_status()
        data = response.json()

        # OpenAI-compatible responses
        if isinstance(data, dict) and data.get("choices"):
            first = data["choices"][0]
            message = first.get("message", {})
            content = message.get("content", "")
            return {"response": content}

        # Fallback for alternate payload formats
        if isinstance(data, dict) and "response" in data:
            return {"response": data.get("response", "")}

        return {"response": str(data)}
    except requests.exceptions.RequestException as e:
        print(f"[LLM ERROR] Request failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Ollama request failed: {str(e)}")


def build_db_fallback_reply(user_message: str, mongo_context: str) -> str:
    """Provide a useful answer when Ollama is unavailable."""
    try:
        collection_names = db.list_collection_names()
        summary_lines = []
        for name in collection_names:
            summary_lines.append(f"- {name}: {db[name].estimated_document_count()} records")

        summary_text = "\n".join(summary_lines) if summary_lines else "- no collections found"
        preview = mongo_context[:1200].strip()
        if not preview:
            preview = "No data preview available."

        return (
            "I can access your MongoDB data, but the Ollama API request failed, so advanced AI generation is unavailable right now.\n\n"
            f"Your question: {user_message}\n\n"
            "Current database summary:\n"
            f"{summary_text}\n\n"
            "Data preview:\n"
            f"{preview}\n\n"
            "To enable full AI answers, verify OLLAMA_API_KEY, OLLAMA_API_URL, and OLLAMA_MODEL."
        )
    except Exception as e:
        return (
            "I could not contact Ollama, and fallback formatting failed. "
            f"Please check backend logs. Details: {str(e)}"
        )


@router.post("/generate")
async def generate_text(request: GenerateRequest):
    loop = asyncio.get_event_loop()
    response_data = await loop.run_in_executor(
        executor, sync_ollama_call, request.prompt, request.stream
    )
    return response_data


@router.post("/chat")
async def chat_with_db(request: ChatRequest):
    """Chat endpoint that includes MongoDB data + live simulation state as context for the LLM."""
    loop = asyncio.get_event_loop()

    # Fetch MongoDB context in a thread to avoid blocking
    mongo_context = await loop.run_in_executor(executor, get_mongodb_context)

    # Fetch live simulation snapshot (synchronous, no I/O)
    live_context = get_live_simulation_context()

    sim_section = ""
    if live_context:
        sim_section = f"""

[LIVE SIMULATION DATA]:
{live_context}
"""

    prompt = f"""You are a smart port operations assistant connected to a MongoDB database AND a live ship-docking simulation.
Your job is to answer the user's questions based on the actual data provided below.
When a simulation is running, prioritize live simulation data for questions about current ship positions,
berth occupancy, queue status, metrics, and real-time operations.
Use the database content for historical records and configuration data.
Be accurate, concise, and helpful. If the data does not contain the answer, say so.

[DATABASE CONTENT]:
{mongo_context}
{sim_section}
[USER QUESTION]: {request.message}

Answer based on the data above:"""

    try:
        response_data = await loop.run_in_executor(
            executor, sync_ollama_call, prompt, request.stream
        )
        return response_data
    except HTTPException as exc:
        # Do not fail chatbot UI when Ollama is down; return DB-based fallback.
        if "Ollama request failed" in str(exc.detail):
            fallback = await loop.run_in_executor(
                executor, build_db_fallback_reply, request.message, mongo_context
            )
            return {"response": fallback, "fallback": True}
        raise


@router.get("/db-info")
async def get_db_info():
    """Return collection names and document counts from MongoDB."""
    try:
        collection_names = db.list_collection_names()
        info = {}
        for name in collection_names:
            info[name] = db[name].estimated_document_count()
        return {"database": "port_db", "collections": info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {str(e)}")
