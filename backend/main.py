import logging

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.ai import process_chat


# --------------------------------------------------
# APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="Bundle Data Assistant"
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# PATH CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_BUILD = BASE_DIR / "frontend" / "build"


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],

    allow_methods=["POST"],

    allow_headers=["Content-Type"],
)


# --------------------------------------------------
# CHAT REQUEST MODEL
# --------------------------------------------------

class ChatRequest(BaseModel):

    message: str = Field(
        min_length=1
    )


# --------------------------------------------------
# CHAT API
# --------------------------------------------------

@app.post("/api/chat")
def chat(request: ChatRequest):

    try:

        result = process_chat(
            request.message
        )

        return result

    except (ValueError, KeyError, TypeError) as error:

        logger.exception(
            "Invalid reporting request"
        )

        raise HTTPException(
            status_code=400,
            detail="Invalid reporting parameters. Check the requested dates and grouping."
        ) from error

    except Exception as error:

        logger.exception(
            "Chat processing failed"
        )

        raise HTTPException(
            status_code=502,
            detail="Unable to process the request. Please try again."
        ) from error


# --------------------------------------------------
# SERVE FRONTEND
# --------------------------------------------------

if FRONTEND_BUILD.exists():

    app.mount(
        "/_app",

        StaticFiles(
            directory=FRONTEND_BUILD / "_app"
        ),

        name="frontend-assets"
    )

    @app.get("/")
    def serve_frontend():

        return FileResponse(
            FRONTEND_BUILD / "index.html"
        )

    @app.get("/favicon.svg")
    def serve_favicon():

        return FileResponse(
            FRONTEND_BUILD / "favicon.svg"
        )

    @app.get("/robots.txt")
    def serve_robots():

        return FileResponse(
            FRONTEND_BUILD / "robots.txt"
        )