"""
backend/main.py — Phase 16: FastAPI Wiring (+ CORS setup)

The actual running web server. Run with:

    uvicorn backend.main:app --reload

Then visit http://127.0.0.1:8000/docs for FastAPI's interactive API
explorer (click "Authorize" after logging in to test the protected
/chat and /conditions routes from the browser).
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.models import Base
from backend.db.session import engine
from backend.routes import (
    auth_routes,
    chat_routes,
    conditions_routes,
    dashboard_routes,
    medication_routes,
    profile_routes,
)
from src.chatbot import HealthcareChatbot


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once when the server starts, and once when it shuts down — the
    code before `yield` is startup, the code after is shutdown.

    Two things happen at startup:

    1. Base.metadata.create_all(engine) — makes sure sehatai.db and its
       tables exist even if someone starts the server without ever having
       run `python -m backend.db.init_db` manually. Safe to call every
       startup: it only creates tables that don't already exist.

    2. HealthcareChatbot() is instantiated exactly ONCE here, not inside
       any route. Its __init__ loads a real language model into memory —
       expensive in both time and RAM/VRAM. If a chatbot were created
       inside the /chat route instead, every single incoming chat request
       would reload the entire model from scratch, which would make the
       API unusably slow (and eventually crash from repeated memory
       allocation). Loading it once here and stashing it on app.state
       means every request reuses the same already-warm model — this is
       also exactly why chatbot.py's Phase 13 refactor made
       HealthcareChatbot instances stateless per-conversation: one shared
       instance safely serves every user's /chat requests at once,
       because it holds no per-conversation state itself anymore.
    """
    print("[STARTUP] Ensuring database tables exist...")
    Base.metadata.create_all(engine)

    print("[STARTUP] Loading HealthcareChatbot (this can take a while)...")
    app.state.bot = HealthcareChatbot()
    print("[STARTUP] Ready.")

    yield

    print("[SHUTDOWN] Server shutting down.")


app = FastAPI(
    title="SehatAI API",
    description="Multilingual rural healthcare assistant — Phase 16 API layer.",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# Browsers block cross-origin requests by default (a frontend running on,
# say, http://localhost:5173 can't call an API on http://localhost:8000
# unless the API explicitly allows it). This isn't optional or a bug to
# work around — it's why every request from a browser-based frontend
# would otherwise fail with a CORS error the moment Phase 17 exists.
#
# SEHATAI_CORS_ORIGINS lets you override the allowed origins via an
# environment variable (comma-separated, e.g.
# "https://sehatai.app,https://www.sehatai.app") once there's a real
# deployed frontend. Until then, the defaults below cover the dev servers
# of the frontend tooling you're most likely to reach for: Vite
# (5173), Create React App (3000), and plain http-server/live-server
# (8080, 5500).
_DEFAULT_DEV_ORIGINS = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:8080", "http://127.0.0.1:8080",
    "http://localhost:5500", "http://127.0.0.1:5500",
]
_env_origins = os.environ.get("SEHATAI_CORS_ORIGINS")
ALLOWED_ORIGINS = (
    [origin.strip() for origin in _env_origins.split(",") if origin.strip()]
    if _env_origins else _DEFAULT_DEV_ORIGINS
)

app.add_middleware(
    CORSMiddleware,
    # Deliberately an explicit list, never "*" — allow_credentials=True
    # (needed so the Authorization header actually reaches the server on
    # a cross-origin request) and a wildcard origin are mutually
    # exclusive by browser spec; using "*" here would make the browser
    # silently reject every credentialed request rather than relax
    # anything.
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(conditions_routes.router)
app.include_router(profile_routes.router)
app.include_router(medication_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(chat_routes.router)


@app.get("/health", tags=["meta"])
def health_check():
    """Plain liveness check — no auth required. Useful for confirming the
    server is up before trying anything else (e.g. from test_api.py, or
    a load balancer / uptime monitor later)."""
    return {"status": "ok"}