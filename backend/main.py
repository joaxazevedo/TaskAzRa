from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from common.db import init_db
from common.version import VERSION
from backend.routers import users, tasks, reports, reminders, tags

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="TaskAzRa", version=VERSION, lifespan=lifespan)

app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(reports.router)
app.include_router(reminders.router)
app.include_router(tags.router)


@app.get("/version")
def get_version():
    return {"version": VERSION}


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    from common.config import load_config

    config = load_config()
    uvicorn.run(app, host=config["api_host"], port=config["api_port"])
