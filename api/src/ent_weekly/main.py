from datetime import date

from pydantic import BaseModel
from fastapi import Depends, FastAPI, Header, HTTPException

from .database import Database
from .settings import settings
from .pipeline import DailyPipeline

app = FastAPI(title="ENT Weekly API", version="0.1.0")
database = Database(settings.db_path)


class DailyRunRequest(BaseModel):
    target_edat: date


@app.on_event("startup")
def startup() -> None:
    database.initialize()


def require_internal(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {settings.regen_token}"
    if not settings.regen_token or authorization != expected:
        raise HTTPException(status_code=401, detail="Internal token required")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", **database.health()}


@app.get("/api/articles")
def articles(limit: int = 100) -> list[dict]:
    return database.list_articles(min(max(limit, 1), 250))


@app.get("/api/articles/{pmid}")
def article(pmid: str) -> dict:
    result = database.get_article(pmid)
    if not result:
        raise HTTPException(status_code=404, detail="Article not found")
    return result


@app.post("/internal/run-daily", dependencies=[Depends(require_internal)])
async def run_daily(request: DailyRunRequest) -> dict:
    return await DailyPipeline(settings, database).run(request.target_edat)


@app.post("/internal/run-weekly", dependencies=[Depends(require_internal)])
def run_weekly() -> dict:
    return {"status": "queued", "message": "Weekly pipeline module will run this job."}
