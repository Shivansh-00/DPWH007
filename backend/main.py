"""
Smart Docking System — FastAPI Entry Point

Starts the decision-intelligence engine with CORS enabled
for frontend communication.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from backend.api.simulation import router as simulation_router
from backend.api.llm import router as llm_router
from backend.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Smart Docking Decision Intelligence Engine starting...")
    from backend.utils.seed_db import seed_if_empty
    seed_if_empty()
    yield
    logger.info("Engine shutting down.")


app = FastAPI(
    title="Smart Docking System Engine",
    description="Decision-intelligence engine for optimizing ship docking operations",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(simulation_router)
app.include_router(llm_router, prefix="/api/llm", tags=["LLM"])


@app.get("/")
def health_check():
    return {"status": "operating", "engine": "Smart Docking System v1.0"}


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
