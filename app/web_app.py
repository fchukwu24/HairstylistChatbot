"""
Simple FastAPI web frontend for the Haircare & Appointment Assistant.

This keeps the existing chatbot logic intact:
- llm.py loads the model/backend
- rag.py loads the FAISS vector DB
- agent.py/run_turn handles the conversation and tools

Run locally:
    uvicorn web_app:app --host 0.0.0.0 --port 8080 --reload

Then open:
    http://localhost:8080
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from llm import load_llm
from agent import run_turn
import rag

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class ResetRequest(BaseModel):
    session_id: Optional[str] = None


class ResetResponse(BaseModel):
    session_id: str
    message: str

class IntroResponse(BaseModel):
    reply: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()


    print("Loading model/backend...")
    app.state.llm, app.state.tokenizer = load_llm()

    print("Building/loading the haircare knowledge index...")
    rag.load_vector_db()

    app.state.histories: Dict[str, List[dict[str, str]]] = {}
    app.state.chat_lock = asyncio.Lock()

    print("Web assistant ready at http://localhost:8080")
    yield


app = FastAPI(
    title="Haircare & Appointment Assistant",
    description="Simple web frontend for the haircare RAG and booking chatbot.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    message = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    session_id = request.session_id or str(uuid.uuid4())
    history = app.state.histories.setdefault(session_id, [])

    # The chatbot state/history is mutable, and some LLM clients are not thread-safe.
    # This keeps conversations stable for a simple class-project web UI.
    async with app.state.chat_lock:
        reply = await asyncio.to_thread(
            run_turn,
            app.state.llm,
            app.state.tokenizer,
            history,
            message,
        )

    return ChatResponse(reply=reply, session_id=session_id)


@app.post("/api/reset", response_model=ResetResponse)
def reset(request: ResetRequest):
    session_id = request.session_id or str(uuid.uuid4())
    app.state.histories[session_id] = []

    return ResetResponse(
        session_id=session_id,
        message="Conversation reset.",
    )

@app.get("/api/intro", response_model=IntroResponse)
async def intro():
    intro_history = []

    intro_prompt = (
        "Briefly introduce yourself to a new salon customer. "
        "Mention that you can help with haircare advice, salon services, "
        "hours, availability, and appointments. Keep it short and friendly."
    )

    async with app.state.chat_lock:
        reply = await asyncio.to_thread(
            run_turn,
            app.state.llm,
            app.state.tokenizer,
            intro_history,
            intro_prompt,
        )

    return IntroResponse(reply=reply)