# surge_server.py

import logging
import os
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware   # <-- ADD THIS
from pydantic import BaseModel

from surge_predict import agent_executor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_TITLE = os.getenv("SURGE_APP_TITLE", "SURGE-SENSE Agent API")

app = FastAPI(title=APP_TITLE)

# -------------------  CORS FIX  --------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:3000"] for tighter security
    allow_credentials=True,
    allow_methods=["*"],  # allows POST, GET, OPTIONS automatically
    allow_headers=["*"],
)
# ----------------------------------------------------


class SurgeRequest(BaseModel):
    query: str
    city: Optional[str] = None


class SurgeResponse(BaseModel):
    query: str
    city: Optional[str]
    agent_output: Any
    intermediate_steps: Optional[List[Any]] = None


@app.get("/")
def root() -> dict:
    return {"message": "SURGE-SENSE Agent API is running ✔"}


@app.post("/surge", response_model=SurgeResponse)
def run_surge_agent(req: SurgeRequest) -> SurgeResponse:
    try:
        if req.city:
            question = f"{req.query} (city: {req.city})"
        else:
            question = req.query

        logger.info("Invoking agent with question: %s", question)

        result = agent_executor.invoke({"input": question})
        print("Intermediate Steps:", result.get("intermediate_steps"))

        return SurgeResponse(
            query=req.query,
            city=req.city,
            agent_output=result.get("output"),
            intermediate_steps=result.get("intermediate_steps"),
        )
    except Exception as exc:
        logger.exception("Error while running surge agent.")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def main() -> None:
    import uvicorn

    host = os.getenv("SURGE_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SURGE_SERVER_PORT", "8000"))
    reload = os.getenv("SURGE_SERVER_RELOAD", "true").lower() == "true"

    uvicorn.run("surge_server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
