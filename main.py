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

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DAILY_QUOTA = int(os.getenv("DAILY_QUOTA", "10"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(_HERE, "data", "db.json")

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
        _db = {"users": [], "suggestions": [], "tokens": {}}

    # Seed default users on first run
    if not _db["users"]:
        default_users = [
            ("senior1",    "senior123", "senior"),
            ("annotator1", "ann123",    "annotator"),
            ("annotator2", "ann456",    "annotator"),
        ]
        for uid, (username, password, role) in enumerate(default_users, start=1):
            _db["users"].append({
                "id":            uid,
                "username":      username,
                "password_hash": hashlib.sha256(password.encode()).hexdigest(),
                "role":          role,
                "quota_used":    0,
                "quota_date":    "",
            })
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
    translation: str
    verification_type: str
    verification_content: str
    verification_polarity: str = 'positive'


class SuggestionReq(BaseModel):
    source_text: str
    translation: str
    source_lang: str = "en"
    target_lang: str = "de"
    verification_type: str
    verification_content: str
    verification_polarity: str = 'positive'


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
            (u for u in _db["users"] if u["username"] == req.username and u["password_hash"] == phash),
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
            s["points"] for s in _db["suggestions"]
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

async def _call_mymemory(
    client: httpx.AsyncClient, text: str, src: str, tgt: str
) -> dict:
    try:
        resp = await client.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text, "langpair": f"{src}|{tgt}"},
            timeout=10,
        )
        data = resp.json()
        if data.get("responseStatus") == 200:
            return {"api": "MyMemory", "translation": data["responseData"]["translatedText"], "error": None}
        return {"api": "MyMemory", "translation": None, "error": "API returned an error"}
    except Exception as exc:
        return {"api": "MyMemory", "translation": None, "error": str(exc)}


async def _call_libretranslate(
    client: httpx.AsyncClient, text: str, src: str, tgt: str
) -> dict:
    try:
        resp = await client.post(
            "https://translate.argosopentech.com/translate",
            json={"q": text, "source": src, "target": tgt, "format": "text"},
            timeout=10,
        )
        data = resp.json()
        if "translatedText" in data:
            return {"api": "LibreTranslate", "translation": data["translatedText"], "error": None}
        return {"api": "LibreTranslate", "translation": None, "error": data.get("error", "API error")}
    except Exception as exc:
        return {"api": "LibreTranslate", "translation": None, "error": str(exc)}


@app.post("/api/translate")
async def translate(req: TranslateReq, user=Depends(_auth)):
    if user["role"] != "annotator":
        raise HTTPException(status_code=403, detail="Only annotators can use translation quota")

    today = date.today().isoformat()
    with _lock:
        quota_used = user["quota_used"] if user["quota_date"] == today else 0
        if quota_used >= DAILY_QUOTA:
            raise HTTPException(status_code=429, detail="Daily quota exceeded")

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _call_mymemory(client, req.text, req.source_lang, req.target_lang),
            _call_libretranslate(client, req.text, req.source_lang, req.target_lang),
        )

    with _lock:
        user["quota_used"] = quota_used + 1
        user["quota_date"] = today
        _save_data()
    return {"results": list(results), "quota_remaining": DAILY_QUOTA - quota_used - 1}


@app.post("/api/verify")
async def verify(req: VerifyReq, user=Depends(_auth)):
    if req.verification_type == "regex":
        try:
            matched = bool(re.search(req.verification_content, req.translation, re.IGNORECASE))
        except re.error as exc:
            raise HTTPException(status_code=400, detail=f"Invalid regex: {exc}") from exc
        if req.verification_polarity == "negative":
            verified = not matched
            detail = "not matched (passes)" if verified else "matched (fails)"
        else:
            verified = matched
            detail = "matched" if verified else "no match"
        return {"verified": verified, "detail": detail}

    if req.verification_type == "llm":
        if not OPENAI_API_KEY:
            return {"verified": True, "detail": "LLM verification skipped (no API key configured)"}
        try:
            async with httpx.AsyncClient() as client:
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
                                    f"Translation to verify: {req.translation}"
                                ),
                            },
                        ],
                        "max_tokens": 5,
                    },
                    timeout=15,
                )
            answer = resp.json()["choices"][0]["message"]["content"].strip().upper()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"LLM API error: {exc}") from exc
        return {"verified": "YES" in answer, "detail": f"LLM: {answer}"}

    raise HTTPException(status_code=400, detail="verification_type must be 'regex' or 'llm'")


# ---------------------------------------------------------------------------
# Routes — suggestions
# ---------------------------------------------------------------------------

@app.post("/api/suggestions")
async def create_suggestion(req: SuggestionReq, user=Depends(_auth)):
    if user["role"] != "annotator":
        raise HTTPException(status_code=403, detail="Only annotators can submit suggestions")
    with _lock:
        sid = _next_id(_db["suggestions"])
        _db["suggestions"].append({
            "id":                   sid,
            "user_id":              user["id"],
            "username":             user["username"],
            "source_text":          req.source_text,
            "translation":          req.translation,
            "source_lang":          req.source_lang,
            "target_lang":          req.target_lang,
            "verification_type":    req.verification_type,
            "verification_content": req.verification_content,
            "verification_polarity": req.verification_polarity,
            "points":               -1,
            "created_at":           datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        })
        _save_data()
    return {"ok": True}


@app.get("/api/suggestions")
async def get_suggestions(user=Depends(_auth)):
    with _lock:
        if user["role"] == "senior":
            rows = sorted(
                _db["suggestions"],
                key=lambda s: (s["points"], s["created_at"]),
            )
        else:
            rows = sorted(
                [s for s in _db["suggestions"] if s["user_id"] == user["id"]],
                key=lambda s: s["created_at"],
                reverse=True,
            )
    return rows


@app.post("/api/suggestions/{sid}/score")
async def score_suggestion(sid: int, req: ScoreReq, user=Depends(_auth)):
    if user["role"] != "senior":
        raise HTTPException(status_code=403, detail="Only senior users can score suggestions")
    if req.points not in (0, 1, 2, 3):
        raise HTTPException(status_code=400, detail="Points must be 0, 1, 2, or 3")
    with _lock:
        suggestion = next((s for s in _db["suggestions"] if s["id"] == sid), None)
        if suggestion is None:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        suggestion["points"] = req.points
        _save_data()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Static frontend — must be mounted last
# ---------------------------------------------------------------------------

app.mount(
    "/",
    StaticFiles(directory=os.path.join(_HERE, "static"), html=True),
    name="static",
)
