import secrets
from typing import Optional

from fastapi import Header, HTTPException

from .db import get_user_by_username


async def get_current_user(
    authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)
) -> dict:
    if not authorization or not authorization.startswith("Bearer ") or not x_user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:]
    user = await get_user_by_username(x_user_id)
    if user is None or not secrets.compare_digest(user.get("magic_token", ""), token):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user


def require_admin(user: dict) -> None:
    if "admin" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Admin access required")
