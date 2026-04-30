"""
Last Translation Benchmark — FastAPI backend
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .db import get_users, init_db
from .routers import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("\n=== Magic login links ===")
    host_public = os.getenv("HOST_PUBLIC")
    for user in await get_users():
        print(
            f"  {user['username']:12s}  {host_public}/?user={user['username']}&token={user['magic_token']}"
        )
    print("=========================\n")
    yield


# ---------------------------------------------------------------------------
# App + middleware
# ---------------------------------------------------------------------------

app = FastAPI(title="Last Translation Benchmark", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ---------------------------------------------------------------------------
# Static frontend — must be mounted last
# ---------------------------------------------------------------------------

app.mount(
    "/",
    StaticFiles(
        directory=os.path.dirname(os.path.abspath(__file__)) + "/static", html=True
    ),
    name="static",
)
