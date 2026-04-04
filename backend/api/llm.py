from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from bson import ObjectId
from backend.models.database import db

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=5)


class GenerateRequest(BaseModel):
    prompt: str
    stream: bool = False


class ChatRequest(BaseModel):
    message: str
    stream: bool = False


OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma4:e2b"


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

            # Get sample documents (up to 10) to show data structure and content
            sample_docs = list(collection.find().sort("_id", -1).limit(10))
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


def sync_ollama_call(prompt: str, stream: bool = False):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": stream
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
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
            "I can access your MongoDB data, but Ollama is not running, so advanced AI generation is unavailable right now.\n\n"
            f"Your question: {user_message}\n\n"
            "Current database summary:\n"
            f"{summary_text}\n\n"
            "Data preview:\n"
            f"{preview}\n\n"
            "To enable full AI answers, start Ollama and load model 'gemma4:e2b'."
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
    """Chat endpoint that includes MongoDB data as context for the LLM."""
    loop = asyncio.get_event_loop()

    # Fetch MongoDB context in a thread to avoid blocking
    mongo_context = await loop.run_in_executor(executor, get_mongodb_context)

    prompt = f"""You are a smart database assistant connected to a MongoDB database.
Your job is to answer the user's questions based ONLY on the actual data provided below from the database.
Be accurate, concise, and helpful. If the data does not contain the answer, say so.

[DATABASE CONTENT]:
{mongo_context}

[USER QUESTION]: {request.message}

Answer based on the database content above:"""

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
