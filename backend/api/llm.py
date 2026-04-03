from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=5)

class GenerateRequest(BaseModel):
    prompt: str
    stream: bool = False

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma4:e2b"

def sync_ollama_call(prompt: str, stream: bool = False):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": stream
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ollama request failed: {str(e)}")

@router.post("/generate")
async def generate_text(request: GenerateRequest):
    loop = asyncio.get_event_loop()
    # Run the synchronous request in a thread pool to avoid blocking the event loop
    response_data = await loop.run_in_executor(
        executor, sync_ollama_call, request.prompt, request.stream
    )
    return response_data
