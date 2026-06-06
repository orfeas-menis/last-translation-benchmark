import asyncio
import functools
import inspect
import os
import secrets
import time
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import get_current_user, require_admin
from .db import (
    create_submission as db_create_submission,
)
from .db import (
    create_user as db_create_user,
)
from .db import (
    delete_submission,
    delete_user,
    get_submission_by_id,
    get_user_by_id,
    get_user_by_username,
    get_users,
    save_submission,
    save_user,
)
from .db import (
    get_submissions as db_get_submissions,
)
from .models import (
    CommentReq,
    NotificationActionReq,
    ProfileReq,
    QuotaReq,
    RecoverLinkReq,
    ReviewScopeReq,
    RolesReq,
    ScoreReq,
    SubmissionReq,
    TranslateReq,
    VerifyReq,
)
from .services import (
    translate_google,
    translate_lara,
    translate_openrouter,
    verify_llm,
)
from .utils import CONTRIBUTOR_QUOTA_DEFAULT, send_email

router = APIRouter()

# --- Users ---


@router.get("/api/me")
async def me(user=Depends(get_current_user)):
    submissions = await db_get_submissions(user_id=user["id"])
    total_accepted = sum(1 for s in submissions if s["status"] == "accept")
    return {
        "username": user["username"],
        "roles": user["roles"],
        "quota": user["quota"],
        "quota_used": user["quota_used"],
        "total_accepted": total_accepted,
        "total_submitted": len(submissions),
        "name": user["name"],
        "affiliation": user["affiliation"],
        "email": user["email"],
        "credit_consent": user["credit_consent"],
        "notification_consent": user["notification_consent"],
        "notifications": user["notifications"],
        "review_langs": user.get("review_langs", []),
    }


@router.put("/api/profile")
async def update_profile(req: ProfileReq, user=Depends(get_current_user)):
    if not req.name.strip() or not req.email.strip():
        raise HTTPException(status_code=400, detail="Name and email are required")
    new_email = req.email.strip().lower()
    if new_email != user["email"].strip().lower():
        users = await get_users()
        if any(
            u["email"].strip().lower() == new_email
            for u in users
            if u["id"] != user["id"]
        ):
            raise HTTPException(status_code=400, detail="Email already taken")

    user.update(
        {
            "name": req.name,
            "affiliation": req.affiliation,
            "email": req.email,
            "credit_consent": req.credit_consent,
            "notification_consent": req.notification_consent,
        }
    )
    await save_user(user)
    return {"ok": True}


@router.post("/api/register", status_code=201)
async def register_user(req: ProfileReq):
    if not req.name.strip() or not req.email.strip():
        raise HTTPException(status_code=400, detail="Name and email are required")

    users = await get_users()

    # Check if email already exists
    if any(u["email"].strip().lower() == req.email.strip().lower() for u in users):
        raise HTTPException(status_code=400, detail="User already registered")

    # Generate username from email prefix
    username = req.email.split("@")[0].lower()
    username = "".join(c for c in username if c.isalnum() or c in "._-")
    if not username:
        raise HTTPException(
            status_code=400, detail="Cannot generate username from email"
        )

    original_username = username
    while True:
        # Check if username already exists
        if all(u["username"] != username for u in users):
            break

        if username == original_username:
            username += "-"

        # add random suffix to avoid collisions
        username += secrets.token_hex(5)[:2]

    new_user = {
        "username": username,
        "magic_token": secrets.token_urlsafe(24),
        "roles": ["contributor"],
        "quota": CONTRIBUTOR_QUOTA_DEFAULT,
        "quota_used": 0,
        "name": req.name,
        "affiliation": req.affiliation,
        "email": req.email,
        "credit_consent": req.credit_consent,
        "notification_consent": req.notification_consent,
        "notifications": [],
        "review_langs": [],
        "last_active": "",
    }
    await db_create_user(new_user)

    # Send registration email directly
    host_public = os.getenv("HOST_PUBLIC") or ""
    host_url = host_public.rstrip("/")
    link = f"{host_url}/?user={username}&token={new_user['magic_token']}"
    email_body = f"""Dear {req.name},

Thank you for registering for the Last Translation Benchmark.

Use this passwordless login link to access the platform and submit hard-to-translate inputs:
{link}

Please make sure that you read the instructions in detail.
Let us know if you have any questions or need to increase your quota.

Best regards, the LTB Team"""

    await send_email(
        to_email=req.email,
        subject="Last Translation Benchmark - Login Link",
        body=email_body,
        user_obj=new_user,
    )

    return {"ok": True}


@router.post("/api/recover-link")
async def recover_link(req: RecoverLinkReq):
    users = await get_users()
    target_email = req.email.strip().lower()

    for user in users:
        if user["email"].strip().lower() == target_email:
            host_url = (os.getenv("HOST_PUBLIC") or "").rstrip("/")
            link = f"{host_url}/?user={user['username']}&token={user['magic_token']}"
            email_body = f"""Dear {user['name']},

You requested a login link for the Last Translation Benchmark.

Use this passwordless login link to access the platform:
{link}

Best regards, the LTB Team"""
            asyncio.create_task(send_email(
                to_email=target_email,
                subject="Last Translation Benchmark - Login Link",
                body=email_body,
                user_obj=user,
            ))
            break

    return {"ok": True}


@router.get("/api/unsubscribe")
async def unsubscribe(user: str, token: str):
    u = await get_user_by_username(user)
    if u is None or not secrets.compare_digest(u["magic_token"], token):
        raise HTTPException(status_code=400, detail="Invalid unsubscribe link")

    u["notification_consent"] = False
    await save_user(u)

    return {"ok": True, "message": "Successfully unsubscribed"}


async def _admin_user_view(u: dict) -> dict:
    submissions = await db_get_submissions(user_id=u["id"])
    total_accepted = sum(1 for s in submissions if s["status"] == "accept")
    return {
        "id": u["id"],
        "username": u["username"],
        "roles": u["roles"],
        "magic_token": u["magic_token"],
        "name": u["name"],
        "affiliation": u["affiliation"],
        "email": u["email"],
        "credit_consent": u["credit_consent"],
        "quota": u["quota"],
        "quota_used": u["quota_used"],
        "review_langs": u["review_langs"],
        "total_accepted": total_accepted,
        "total_submitted": len(submissions),
        "last_active": u["last_active"],
    }


@router.get("/api/admin/users")
async def admin_users(user=Depends(get_current_user)):
    require_admin(user)
    users = await get_users()
    return await asyncio.gather(*[_admin_user_view(u) for u in users])


@router.get("/api/public-dashboard")
async def public_dashboard():
    users = await get_users()
    submissions = await db_get_submissions()
    accepted_by_user: dict[int, int] = {}
    for submission in submissions:
        if submission["status"] != "accept":
            continue
        user_id = submission["user_id"]
        accepted_by_user[user_id] = accepted_by_user.get(user_id, 0) + 1

    users_by_id = {u["id"]: u for u in users if isinstance(u["id"], int)}
    rows: list[dict] = []
    anonymous_submissions = 0
    anonymous_users = set()
    anonymous_affiliations = set()

    for user_id, accepted in accepted_by_user.items():
        user = users_by_id.get(user_id)
        # We keep submissions of deleted users, so user might be None.
        # In that case, default to anonymous (credit_consent=False).
        credit_consent = user["credit_consent"] if user else False

        if credit_consent and user:
            rows.append(
                {
                    "name": user["name"],
                    "affiliation": user["affiliation"],
                    "accepted_submissions": accepted,
                }
            )
        else:
            anonymous_submissions += accepted
            anonymous_users.add(user_id)
            if user:
                anonymous_affiliations.add(user["affiliation"])

    if anonymous_submissions > 0:
        rows.append(
            {
                "name": f"Anonymous ({len(anonymous_users)} users)",
                "affiliation": f"Multiple affiliations ({len(anonymous_affiliations)})",
                "accepted_submissions": anonymous_submissions,
            }
        )

    rows.sort(
        key=lambda row: (
            int(row["accepted_submissions"]),
            str(row["name"]),
        ),
        reverse=True,
    )
    return rows


@router.delete("/api/admin/users/{uid}", status_code=200)
async def admin_delete_user(uid: int, user=Depends(get_current_user)):
    require_admin(user)
    if user["id"] == uid:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    await delete_user(uid)
    return {"ok": True}


@router.post("/api/admin/users/{uid}/adjust-quota")
async def admin_adjust_quota(uid: int, req: QuotaReq, user=Depends(get_current_user)):
    require_admin(user)
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target["quota"] = max(0, target["quota"] + req.delta)
    await save_user(target)
    return {"quota": target["quota"], "quota_used": target["quota_used"]}


@router.post("/api/admin/users/{uid}/roles")
async def admin_update_roles(uid: int, req: RolesReq, user=Depends(get_current_user)):
    require_admin(user)
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    valid_roles = {"admin", "contributor", "reviewer"}
    bad = [r for r in req.roles if r not in valid_roles]
    if bad:
        raise HTTPException(status_code=400, detail=f"Invalid roles: {bad}")
    target["roles"] = req.roles
    await save_user(target)
    return await _admin_user_view(target)


@router.post("/api/admin/users/{uid}/review-scope")
async def admin_update_review_scope(
    uid: int, req: ReviewScopeReq, user=Depends(get_current_user)
):
    require_admin(user)
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target["review_langs"] = req.review_langs
    await save_user(target)
    return await _admin_user_view(target)


def _submission_matches_scope(submission: dict, review_langs: set[str]) -> bool:
    if not review_langs:
        return True
    langs_lower = {lang.lower() for lang in review_langs}
    source_lang = submission["source_lang"].lower()
    target_lang = submission["target_lang"].lower()
    return any(source_lang in lang or lang in source_lang for lang in langs_lower) or any(
        target_lang in lang or lang in target_lang for lang in langs_lower
    )


def _filter_reviewer_submissions(
    rows: list[dict],
    status: str,
    source_langs: list[str],
    target_langs: list[str],
    username: str,
) -> list[dict]:
    if status == "pending":
        rows = [s for s in rows if s["status"] == "pending"]
    elif status == "accepted_or_returned":
        rows = [s for s in rows if s["status"] in ("accept", "return")]
    elif status == "accepted":
        rows = [s for s in rows if s["status"] == "accept"]
    elif status == "returned":
        rows = [s for s in rows if s["status"] == "return"]
    if source_langs:
        s_lower = {lang.lower() for lang in source_langs}
        rows = [
            s for s in rows 
            if any(s["source_lang"].lower() in lang or lang in s["source_lang"].lower() for lang in s_lower)
        ]
    if target_langs:
        t_lower = {lang.lower() for lang in target_langs}
        rows = [
            s for s in rows 
            if any(s["target_lang"].lower() in lang or lang in s["target_lang"].lower() for lang in t_lower)
        ]
    if username:
        rows = [s for s in rows if s["username"] == username]
    return rows


# --- Translate ---


@router.post("/api/translate-submission")
async def translate_submission(req: TranslateReq, user=Depends(get_current_user)):
    if not req.text and not req.source_media:
        raise HTTPException(
            status_code=400, detail="Enter source text or add media first"
        )

    if (
        not req.source_lang
        or not req.source_lang.strip()
        or not req.target_lang
        or not req.target_lang.strip()
    ):
        raise HTTPException(status_code=400, detail="Both languages must be specified")
    if len(req.source_lang) > 50 or len(req.target_lang) > 50:
        raise HTTPException(
            status_code=400, detail="Language has to be at most 50 characters long"
        )

    source_name = req.source_lang
    target_name = req.target_lang

    quota_used = user["quota_used"]
    quota = user["quota"]
    if quota_used >= quota:
        raise HTTPException(status_code=429, detail="Quota exceeded")

    user["quota_used"] = quota_used + 1
    await save_user(user)

    async def _run_translate(
        name: str,
        func,
        text: str,
        src_lang: str,
        tgt_lang: str,
        source_media: str | None = None,
        source_instructions: str | None = None,
    ):
        time_start = time.time()
        try:
            if inspect.iscoroutinefunction(func):
                res = await func(
                    text=text,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                    source_media=source_media,
                    source_instructions=source_instructions,
                )
            else:
                res = await asyncio.to_thread(
                    func,
                    text=text,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                    source_media=source_media,
                    source_instructions=source_instructions,
                )
            return {
                "model": name,
                "translation": res,
                "error": None,
                "time": round(time.time() - time_start, 1),
            }
        except Exception as exc:
            # skip unsupported models
            if str(exc).startswith("No endpoints found that support"):
                return {"model": name, "translation": None, "error": None}
            return {"model": name, "translation": None, "error": str(exc)}

    tasks = [
        _run_translate(
            "Lara",
            translate_lara,
            req.text,
            source_name,
            target_name,
            req.source_media,
            req.source_instructions,
        ),
        _run_translate(
            "Google Translate",
            translate_google,
            req.text,
            source_name,
            target_name,
            req.source_media,
            req.source_instructions,
        ),
        _run_translate(
            "Gemini 2.5 Flash",
            functools.partial(translate_openrouter, model="google/gemini-2.5-flash"),
            req.text,
            source_name,
            target_name,
            req.source_media,
            req.source_instructions,
        ),
        _run_translate(
            "Gemma 4",
            functools.partial(translate_openrouter, model="google/gemma-4-31b-it"),
            req.text,
            source_name,
            target_name,
            req.source_media,
            req.source_instructions,
        ),
        _run_translate(
            "Llama 4 Maverick",
            functools.partial(
                translate_openrouter, model="meta-llama/llama-4-maverick"
            ),
            req.text,
            source_name,
            target_name,
            req.source_media,
            req.source_instructions,
        ),
        _run_translate(
            "GPT-5.4 Mini",
            functools.partial(translate_openrouter, model="openai/gpt-5.4-mini"),
            req.text,
            source_name,
            target_name,
            req.source_media,
            req.source_instructions,
        ),
        _run_translate(
            "Deepseek V4 Pro",
            functools.partial(translate_openrouter, model="deepseek/deepseek-v4-pro"),
            req.text,
            source_name,
            target_name,
            req.source_media,
            req.source_instructions,
        ),
        _run_translate(
            "Claude Haiku 4.5",
            functools.partial(translate_openrouter, model="anthropic/claude-haiku-4.5"),
            req.text,
            source_name,
            target_name,
            req.source_media,
            req.source_instructions,
        ),
        _run_translate(
            "Claude Sonnet 4.5",
            functools.partial(
                translate_openrouter, model="anthropic/claude-sonnet-4.5"
            ),
            req.text,
            source_name,
            target_name,
            req.source_media,
            req.source_instructions,
        ),
        _run_translate(
            "Cohere Command A",
            functools.partial(translate_openrouter, model="cohere/command-a"),
            req.text,
            source_name,
            target_name,
            req.source_media,
            req.source_instructions,
        ),
    ]
    results = await asyncio.gather(*tasks)

    # filter out translations that did not pass because of language incompatibility
    results = [
        r for r in results if r["translation"] is not None or r["error"] is not None
    ]

    return {"results": results, "quota": quota, "quota_used": quota_used + 1}


@router.post("/api/verify-submission")
async def verify_submission(req: VerifyReq, user=Depends(get_current_user)):
    quota_used = user["quota_used"]
    quota = user["quota"]
    if quota_used >= quota:
        raise HTTPException(status_code=429, detail="Quota exceeded")

    if not req.verification_rules:
        return {"results": [[]] * len(req.translations)}

    user["quota_used"] = quota_used + 1
    await save_user(user)

    async def _verify_single(
        source_text: str, translation: str, source_media: str | None = None
    ) -> list[bool]:
        results = []
        for rule in req.verification_rules:
            try:
                res = await verify_llm(
                    source_text, translation, rule.value, source_media
                )
                results.append(res)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"LLM API error: {exc}")
        return results

    unique_translations = list(set(req.translations))
    unique_results = await asyncio.gather(
        *[
            _verify_single(req.source_text, t, req.source_media)
            for t in unique_translations
        ]
    )

    translation_to_result = dict(zip(unique_translations, unique_results))
    results = [translation_to_result[t] for t in req.translations]

    return {"results": results, "quota": quota, "quota_used": quota_used + 1}


# --- Submissions ---


@router.post("/api/submissions")
async def create_submission(req: SubmissionReq, user=Depends(get_current_user)):
    if "contributor" not in user["roles"]:
        raise HTTPException(
            status_code=403, detail="Only contributors can submit submissions"
        )

    if (
        not req.source_lang
        or not req.source_lang.strip()
        or not req.target_lang
        or not req.target_lang.strip()
        or not (req.source_text or req.source_media)
        or not req.translations
        or not req.verification_rules
    ):
        raise HTTPException(status_code=400, detail="Field missing")

    submission = {
        "user_id": user["id"],
        "username": user["username"],
        "source_text": req.source_text,
        "source_media": req.source_media,
        "source_lang": req.source_lang.strip(),
        "target_lang": req.target_lang.strip(),
        "verification_rules": [r.model_dump() for r in req.verification_rules],
        "translations": [t.model_dump() for t in req.translations],
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_instructions": req.source_instructions,
        "comments": [],
        "reviewed_by": None,
    }
    await db_create_submission(submission)
    return {"ok": True}


@router.put("/api/submissions/{sid}")
async def update_submission(
    sid: int, req: SubmissionReq, user=Depends(get_current_user)
):
    submission = await get_submission_by_id(sid)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission["user_id"] != user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this submission"
        )

    if submission["status"] == "accept":
        raise HTTPException(
            status_code=403, detail="Cannot edit an accepted submission"
        )

    update: dict = {
        "source_text": req.source_text,
        "source_lang": req.source_lang,
        "target_lang": req.target_lang,
        "verification_rules": [r.model_dump() for r in req.verification_rules],
        "translations": [t.model_dump() for t in req.translations],
        "status": "pending",
        "reviewed_by": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_instructions": req.source_instructions,
        "source_media": req.source_media,
    }
    submission.update(update)
    await save_submission(submission)
    return {"ok": True}


@router.delete("/api/submissions/{sid}")
async def delete_submission_endpoint(sid: int, user=Depends(get_current_user)):
    require_admin(user)
    submission = await get_submission_by_id(sid)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    await delete_submission(sid)
    return {"ok": True}


@router.get("/api/submissions")
async def list_submissions(
    user=Depends(get_current_user),
    mode: Literal["contributor", "reviewer"] = "contributor",
    status: Literal["pending", "accepted_or_returned", "accepted", "returned", "all"] = "all",
    source_langs: list[str] = Query(default=[]),
    target_langs: list[str] = Query(default=[]),
    username: str = "",
):
    if mode == "reviewer" and "reviewer" in user["roles"]:
        rows = await db_get_submissions()
        review_langs = {lang.lower() for lang in user["review_langs"]}
        is_admin = "admin" in user["roles"]
        
        if review_langs and not is_admin:
            rows = [s for s in rows if _submission_matches_scope(s, review_langs)]
            
        rows = _filter_reviewer_submissions(
            rows=rows,
            status=status,
            source_langs=source_langs,
            target_langs=target_langs,
            username=username,
        )
        
        # prevent non-admins from listing accepted submissions
        if not is_admin:
            rows = [
                s
                for s in rows
                # either not accepted
                if s["status"] != "accept"
                # or own submission
                or s["user_id"] == user["id"]
                # or reviewed by reviewer
                or s["reviewed_by"] == user["username"]
                # or commented by reviewer
                or any(
                    c["author"] == user["username"]
                    for c in s["comments"]
                )
            ]
    else:
        rows = await db_get_submissions(user_id=user["id"])
    return rows


@router.post("/api/submissions/{sid}/score")
async def score_submission(sid: int, req: ScoreReq, user=Depends(get_current_user)):
    if "reviewer" not in user["roles"]:
        raise HTTPException(
            status_code=403, detail="Only reviewer users can score submissions"
        )
    if req.action not in ("return", "accept", "pending"):
        raise HTTPException(
            status_code=400, detail="Action must be return, accept, or pending"
        )
    submission = await get_submission_by_id(sid)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission["user_id"] == user["id"] and "admin" not in user["roles"]:
        raise HTTPException(
            status_code=403,
            detail="Reviewers who are not admins cannot change the status of their own submissions",
        )

    if req.action == "accept":
        submission["status"] = "accept"
    elif req.action == "return":
        submission["status"] = "return"
    elif req.action == "pending":
        submission["status"] = "pending"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    submission["reviewed_by"] = user["username"]

    if req.action in ("accept", "return"):
        author = await get_user_by_id(submission["user_id"])
        if author:
            prefix = submission["source_text"][:70].replace("\n", " ")
            if not prefix and submission["source_media"]:
                prefix = "Media submission"
            content = (
                f"#{submission['id']}: {prefix}..."
                if len(submission["source_text"]) > 40
                else f"#{submission['id']}: {prefix}"
            )
            author["notifications"].append(
                {
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "type": "accepted" if req.action == "accept" else "returned",
                    "status": "unread",
                    "content": content,
                }
            )
            await save_user(author)

    await save_submission(submission)
    return {"ok": True}


@router.post("/api/submissions/{sid}/comment")
async def add_comment(sid: int, req: CommentReq, user=Depends(get_current_user)):
    submission = await get_submission_by_id(sid)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    is_reviewer = "reviewer" in user["roles"]
    is_owner = submission["user_id"] == user["id"]

    if not (is_reviewer or is_owner):
        raise HTTPException(status_code=403, detail="Not authorized to comment")

    submission["comments"].append(
        {
            "author": user["username"],
            "text": req.comment,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )

    if not is_owner:
        author = await get_user_by_id(submission["user_id"])
        if author:
            prefix = submission["source_text"][:40]
            if not prefix and submission["source_media"]:
                prefix = "Media submission"
            content = (
                f"#{submission['id']}: {prefix}..."
                if len(submission["source_text"]) > 40
                else f"#{submission['id']}: {prefix}"
            )
            author["notifications"].append(
                {
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "type": "commented",
                    "status": "unread",
                    "content": content,
                }
            )
            await save_user(author)

    await save_submission(submission)
    return {"ok": True}


@router.post("/api/notifications")
async def handle_notifications(
    req: NotificationActionReq, user=Depends(get_current_user)
):
    if req.action == "view":
        for n in user["notifications"]:
            n["status"] = "viewed"
    elif req.action == "clear":
        user["notifications"] = []
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await save_user(user)
    return {"ok": True}
