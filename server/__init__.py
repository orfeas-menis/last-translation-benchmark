"""
Last Translation Benchmark — FastAPI backend
"""

import asyncio
import hashlib
import json
import os
import re
import secrets
import threading
from datetime import date, datetime, timezone
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .utils import (
    DAILY_QUOTA,
    DATA_PATH,
    OPENAI_API_KEY,
    _call_deepl,
    _call_google,
    _call_libre,
    _call_mymemory,
)

# ---------------------------------------------------------------------------
# JSON data store
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_db: dict = {}


def _load_data() -> None:
    global _db
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            _db = json.load(f)
    else:
        _db = {"users": [], "submissions": [], "tokens": {}}

    # Seed default users on first run
    if not _db["users"]:
        default_users = [
            ("r1", "r1", "reviewer"),
            ("c1", "c1", "contributor"),
            ("c2", "c2", "contributor"),
        ]
        for uid, (username, password, role) in enumerate(default_users, start=1):
            _db["users"].append(
                {
                    "id": uid,
                    "username": username,
                    "password_hash": hashlib.sha256(password.encode()).hexdigest(),
                    "role": role,
                    "quota_used": 0,
                    "quota_date": "",
                }
            )
        _save_data()


def _save_data() -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(_db, f, indent=2, ensure_ascii=False)


def _next_id(collection: list) -> int:
    return max((item["id"] for item in collection), default=0) + 1


_load_data()

# ---------------------------------------------------------------------------
# App + middleware
# ---------------------------------------------------------------------------

app = FastAPI(title="Last Translation Benchmark")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def _auth(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:]
    with _lock:
        user_id = _db["tokens"].get(token)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = next((u for u in _db["users"] if u["id"] == user_id), None)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class LoginReq(BaseModel):
    username: str
    password: str


class TranslateReq(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "de"


class VerifyReq(BaseModel):
    translations: list[str]
    verification_content: str


class SubmissionReq(BaseModel):
    source_text: str
    translation: str
    source_lang: str = "en"
    target_lang: str = "de"
    verification_content: str


class ScoreReq(BaseModel):
    points: int


# ---------------------------------------------------------------------------
# Routes — auth
# ---------------------------------------------------------------------------


@app.post("/api/login")
async def login(req: LoginReq):
    phash = hashlib.sha256(req.password.encode()).hexdigest()
    with _lock:
        user = next(
            (
                u
                for u in _db["users"]
                if u["username"] == req.username and u["password_hash"] == phash
            ),
            None,
        )
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = secrets.token_hex(32)
        _db["tokens"][token] = user["id"]
        _save_data()
    return {"token": token, "role": user["role"], "username": user["username"]}


@app.post("/api/logout")
async def logout(user=Depends(_auth), authorization: Optional[str] = Header(None)):
    token = authorization[7:]
    with _lock:
        _db["tokens"].pop(token, None)
        _save_data()
    return {"ok": True}


@app.get("/api/me")
async def me(user=Depends(_auth)):
    today = date.today().isoformat()
    quota_used = user["quota_used"] if user["quota_date"] == today else 0
    with _lock:
        total_points = sum(
            s["points"]
            for s in _db["submissions"]
            if s["user_id"] == user["id"] and s["points"] >= 0
        )
    return {
        "username": user["username"],
        "role": user["role"],
        "quota_used": quota_used,
        "quota_remaining": max(0, DAILY_QUOTA - quota_used),
        "daily_quota": DAILY_QUOTA,
        "total_points": total_points,
    }


# ---------------------------------------------------------------------------
# Routes — translation + verification
# ---------------------------------------------------------------------------


@app.post("/api/translate")
async def translate(req: TranslateReq, user=Depends(_auth)):
    if user["role"] != "contributor":
        raise HTTPException(
            status_code=403, detail="Only contributors can use translation quota"
        )

    today = date.today().isoformat()
    with _lock:
        quota_used = user["quota_used"] if user["quota_date"] == today else 0
        if quota_used >= DAILY_QUOTA:
            raise HTTPException(status_code=429, detail="Daily quota exceeded")

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _call_mymemory(client, req.text, req.source_lang, req.target_lang),
            asyncio.to_thread(_call_google, req.text, req.source_lang, req.target_lang),
            asyncio.to_thread(_call_deepl, req.text, req.source_lang, req.target_lang),
            asyncio.to_thread(_call_libre, req.text, req.source_lang, req.target_lang),
        )

    with _lock:
        user["quota_used"] = quota_used + 1
        user["quota_date"] = today
        _save_data()
    return {"results": list(results), "quota_remaining": DAILY_QUOTA - quota_used - 1}


@app.post("/api/verify")
async def verify(req: VerifyReq, user=Depends(_auth)):
    content_stripped = req.verification_content.strip()
    is_regex = False

    if content_stripped.startswith("#!regex"):
        is_regex = True
        lines = content_stripped.split("\n", 1)
        req.verification_content = lines[1].strip() if len(lines) > 1 else ""

    if is_regex:
        results = []
        try:
            pattern = re.compile(req.verification_content, re.IGNORECASE)
            for t in req.translations:
                results.append(bool(pattern.search(t)))
        except re.error as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid regex: {exc}"
            ) from exc
        pass_count = sum(results)
        return {
            "results": results,
            "detail": f"{pass_count} passing, {len(results) - pass_count} failing",
        }

    if not OPENAI_API_KEY:
        results = [True for _ in req.translations]
        return {
            "results": results,
            "detail": "LLM verification skipped (no API key configured)",
        }
    try:
        results = []
        async with httpx.AsyncClient() as client:

            async def _verify_llm(t: str) -> bool:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You verify if a translation satisfies a criterion. Reply only YES or NO.",
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"Criterion: {req.verification_content}\n\n"
                                    f"Translation to verify: {t}"
                                ),
                            },
                        ],
                        "max_tokens": 5,
                    },
                    timeout=15,
                )
                answer = resp.json()["choices"][0]["message"]["content"].strip().upper()
                return "YES" in answer

            results = await asyncio.gather(*[_verify_llm(t) for t in req.translations])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM API error: {exc}") from exc

    pass_count = sum(results)
    return {
        "results": results,
        "detail": f"{pass_count} passing, {len(results) - pass_count} failing",
    }


# ---------------------------------------------------------------------------
# Routes — submissions
# ---------------------------------------------------------------------------


@app.post("/api/submissions")
async def create_submission(req: SubmissionReq, user=Depends(_auth)):
    if user["role"] != "contributor":
        raise HTTPException(
            status_code=403, detail="Only contributors can submit submissions"
        )

    with _lock:
        sid = _next_id(_db["submissions"])
        _db["submissions"].append(
            {
                "id": sid,
                "user_id": user["id"],
                "username": user["username"],
                "source_text": req.source_text,
                "translation": req.translation,
                "source_lang": req.source_lang,
                "target_lang": req.target_lang,
                "verification_content": req.verification_content,
                "points": -1,
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        _save_data()
    return {"ok": True}


@app.get("/api/submissions")
async def get_submissions(user=Depends(_auth)):
    with _lock:
        if user["role"] == "reviewer":
            rows = sorted(
                _db["submissions"],
                key=lambda s: (s["points"], s["created_at"]),
            )
        else:
            rows = sorted(
                [s for s in _db["submissions"] if s["user_id"] == user["id"]],
                key=lambda s: s["created_at"],
                reverse=True,
            )
    return rows


@app.post("/api/submissions/{sid}/score")
async def score_submission(sid: int, req: ScoreReq, user=Depends(_auth)):
    if user["role"] != "reviewer":
        raise HTTPException(
            status_code=403, detail="Only reviewer users can score submissions"
        )
    if req.points not in (0, 1, 2):
        raise HTTPException(status_code=400, detail="Points must be 0, 1, or 2")
    with _lock:
        submission = next((s for s in _db["submissions"] if s["id"] == sid), None)
        if submission is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        submission["points"] = req.points
        _save_data()
    return {"ok": True}


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
