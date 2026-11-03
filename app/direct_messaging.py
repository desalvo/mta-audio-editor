"""Private conversations for registered server accounts."""
from pathlib import Path
from typing import Annotated
import re
import tempfile
import time

from fastapi import APIRouter, HTTPException, Path as PathParam, Query, Request, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import account_lifecycle, auth
from .project_collaboration import _validate_media

router = APIRouter(prefix="/api/messages")
MAX_ATTACHMENT = 20 * 1024 * 1024
ATTACHMENT_QUOTA = 512 * 1024 * 1024
AccountPathId = Annotated[int, PathParam(ge=1, le=2**63 - 1)]


def user_id(request: Request) -> int:
    uid = int(auth.require_user(request)["id"])
    if uid <= 0:
        raise HTTPException(403, "Messaging requires a registered account")
    return uid


def contact(row):
    return {key: row[key] for key in ("id", "username", "display_name")}


class TextMessage(BaseModel):
    text: str = Field(max_length=4000)


class ReadThrough(BaseModel):
    through: int = Field(ge=1, le=2**63 - 1)


@router.get("/unread")
def unread(request: Request):
    uid = user_id(request)
    with auth.db() as con:
        count = con.execute(
            "SELECT count(*) FROM direct_messages WHERE recipient=? AND read_at IS NULL", (uid,)
        ).fetchone()[0]
    return {"unread": count}


@router.get("/contacts")
def contacts(request: Request, q: str = Query(min_length=2, max_length=64)):
    uid = user_id(request)
    query = q.strip()
    if len(query) < 2:
        return []
    with auth.db() as con:
        rows = con.execute(
            """SELECT id,username,display_name FROM users WHERE id!=? AND active=1 AND email_confirmed=1
               AND (substr(username,1,length(?))=? COLLATE NOCASE OR
                    substr(display_name,1,length(?))=? COLLATE NOCASE)
               ORDER BY username LIMIT 25""",
            (uid, query, query, query, query),
        ).fetchall()
    return [contact(row) for row in rows]


@router.get("/threads")
def threads(request: Request, before: int = Query(default=2**63 - 1, ge=1, le=2**63 - 1)):
    uid = user_id(request)
    with auth.db() as con:
        rows = con.execute(
            """WITH activity AS (
                   SELECT recipient AS peer,id,0 AS unread FROM direct_messages WHERE sender=?
                   UNION ALL
                   SELECT sender AS peer,id,read_at IS NULL FROM direct_messages WHERE recipient=?
               ), threads AS (
                   SELECT peer,max(id) AS latest,sum(unread) AS unread FROM activity GROUP BY peer
               )
               SELECT u.id,u.username,u.display_name,t.unread,t.latest,m.created_at
               FROM threads t JOIN users u ON u.id=t.peer JOIN direct_messages m ON m.id=t.latest
               WHERE t.latest<? ORDER BY t.latest DESC LIMIT 51""", (uid, uid, before)
        ).fetchall()
    return {
        "items": [{**contact(row), "unread": row["unread"], "latest": row["latest"],
                   "created_at": row["created_at"]} for row in rows[:50]],
        "next_before": rows[49]["latest"] if len(rows) > 50 else None,
    }


@router.get("/threads/{peer}")
def history(request: Request, peer: AccountPathId, before: int = Query(default=2**63 - 1, ge=1, le=2**63 - 1)):
    uid = user_id(request)
    with auth.db() as con:
        row = con.execute(
            "SELECT id,username,display_name,active,email_confirmed FROM users WHERE id=? AND id!=?", (peer, uid)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Conversation unavailable")
        rows = con.execute(
            """SELECT id,sender,text,mime,created_at FROM direct_messages WHERE id<? AND
               ((sender=? AND recipient=?) OR (sender=? AND recipient=?)) ORDER BY id DESC LIMIT 51""",
            (before, uid, peer, peer, uid),
        ).fetchall()
        if not rows and (not row["active"] or not row["email_confirmed"]):
            raise HTTPException(404, "Conversation unavailable")
    return {
        "peer": contact(row), "viewer": uid, "can_send": bool(row["active"] and row["email_confirmed"]),
        "items": [dict(item) for item in reversed(rows[:50])],
        "next_before": rows[49]["id"] if len(rows) > 50 else None,
    }


def publish(uid, peer, text="", mime=None, data=None):
    if peer == uid:
        raise HTTPException(400, "Choose another account")
    now = int(time.time())
    with auth.db() as con:
        account_lifecycle.init(con)
        con.execute("BEGIN IMMEDIATE")
        target = con.execute(
            "SELECT email,language,browser_language FROM users WHERE id=? AND active=1 AND email_confirmed=1", (peer,)
        ).fetchone()
        if not target:
            raise HTTPException(404, "Recipient unavailable")
        count = con.execute(
            "SELECT count(*) FROM direct_messages WHERE sender=? AND created_at>?", (uid, now - 60)
        ).fetchone()[0]
        if count >= 30:
            raise HTTPException(429, "Messaging rate limit reached", headers={"Retry-After": "60"})
        size = len(data) if data is not None else 0
        if size:
            used = con.execute("SELECT coalesce(sum(size),0) FROM direct_messages WHERE sender=?", (uid,)).fetchone()[0]
            if used + size > ATTACHMENT_QUOTA:
                raise HTTPException(413, "Messaging attachment quota reached")
        cur = con.execute(
            """INSERT INTO direct_messages(sender,recipient,text,mime,media,size,created_at)
               VALUES(?,?,?,?,?,?,?)""", (uid, peer, text, mime, data, size, now)
        )
        mid = cur.lastrowid
        language = target["language"] if target["language"] in ("it", "en") else target["browser_language"]
        subject = "Nuovo messaggio su MTA Audio Editor" if language == "it" else "New message in MTA Audio Editor"
        body = ("Apri la dashboard Messaggi per leggere il messaggio."
                if language == "it" else "Open the Messages dashboard to read your message.")
        account_lifecycle.enqueue(con, f"direct-message:{mid}", target["email"], subject, body, uid=peer)
    return {"id": mid}


@router.post("/threads/{peer}", status_code=201)
def send_text(request: Request, peer: AccountPathId, body: TextMessage):
    uid = user_id(request)
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Write a message")
    return publish(uid, peer, text=text)


def publish_attachment(uid, peer, data):
    with tempfile.TemporaryDirectory(prefix="mta-message-") as folder:
        path = Path(folder) / "attachment"
        path.write_bytes(data)
        mime = _validate_media(path, allow_video=True)
        return publish(uid, peer, mime=mime, data=bytes(data))


@router.post("/threads/{peer}/attachment", status_code=201)
async def send_attachment(request: Request, peer: AccountPathId):
    uid = user_id(request)
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_ATTACHMENT:
            raise HTTPException(413, "Attachment exceeds 20 MiB")
        data.extend(chunk)
    if not data:
        raise HTTPException(400, "Attachment is empty")
    return await run_in_threadpool(publish_attachment, uid, peer, data)


@router.post("/threads/{peer}/read")
def mark_read(request: Request, peer: AccountPathId, body: ReadThrough):
    uid = user_id(request)
    with auth.db() as con:
        con.execute(
            """UPDATE direct_messages SET read_at=? WHERE sender=? AND recipient=? AND id<=?
               AND read_at IS NULL""", (int(time.time()), peer, uid, body.through)
        )
    return {"ok": True}


def byte_range(header, size):
    if not header:
        return 0, size - 1
    match = re.fullmatch(r"bytes=(\d{0,20})-(\d{0,20})", header)
    if match:
        first, last = match.groups()
        if first:
            start, end = int(first), min(size - 1, int(last)) if last else size - 1
            if start <= end:
                return start, end
        elif last and int(last):
            return max(0, size - int(last)), size - 1
    raise HTTPException(416, "Invalid byte range", headers={"Content-Range": f"bytes */{size}"})


@router.get("/attachments/{message_id}")
def attachment(request: Request, message_id: AccountPathId):
    uid = user_id(request)
    with auth.db() as con:
        con.execute("BEGIN")
        row = con.execute(
            "SELECT mime,size FROM direct_messages WHERE id=? AND (sender=? OR recipient=?) AND mime IS NOT NULL",
            (message_id, uid, uid),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Attachment unavailable")
        header = request.headers.get("range")
        start, end = byte_range(header, row["size"])
        data = con.execute(
            "SELECT substr(media,?,?) FROM direct_messages WHERE id=?", (start + 1, end - start + 1, message_id)
        ).fetchone()[0]
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if header:
        headers["Content-Range"] = f"bytes {start}-{end}/{row['size']}"
    return Response(data, status_code=206 if header else 200, media_type=row["mime"], headers=headers)
