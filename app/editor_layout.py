"""Small, validated layout preferences scoped to the authenticated identity."""
import json
import math
import os
from pathlib import Path
import tempfile
import threading

from fastapi import HTTPException, Request

from . import auth

LOCK = threading.RLock()


def validate(value):
    if not isinstance(value, dict) or set(value) - {"rows", "job_position"}:
        raise ValueError("Invalid editor layout")
    rows = value.get("rows", [])
    if not isinstance(rows, list) or len(rows) > 6:
        raise ValueError("Choose up to six toolbar rows")
    ids = []
    for row in rows:
        if not isinstance(row, list):
            raise ValueError("Invalid toolbar row")
        for name in row:
            if not isinstance(name, str) or not name or len(name) > 80 or not all(c.isalnum() or c in "_-" for c in name):
                raise ValueError("Invalid toolbar item")
            ids.append(name)
    if len(ids) > 100 or len(set(ids)) != len(ids):
        raise ValueError("Invalid or duplicate toolbar items")
    result = {"rows": rows}
    position = value.get("job_position")
    if position is not None:
        if not isinstance(position, dict) or set(position) != {"x", "y"}:
            raise ValueError("Invalid AI monitor position")
        if any(isinstance(n, bool) or not isinstance(n, (float, int)) or not math.isfinite(n) or not 0 <= n <= 1 for n in position.values()):
            raise ValueError("AI monitor position must be inside the window")
        result["job_position"] = position
    return result


def native_path():
    return Path(auth.data_root()) / "native-editor-layout.json"


def load(actor, native=False):
    with LOCK:
        if native:
            try:
                path = native_path()
                if path.is_symlink() or path.stat().st_size > 16384:
                    return {"rows": []}
                return validate(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError):
                return {"rows": []}
        with auth.db() as con:
            con.execute("CREATE TABLE IF NOT EXISTS editor_layout_preferences (user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, payload TEXT NOT NULL)")
            row = con.execute("SELECT payload FROM editor_layout_preferences WHERE user_id=?", (actor["id"],)).fetchone()
            return validate(json.loads(row[0])) if row else {"rows": []}


def save(actor, value, native=False):
    value = validate(value)
    payload = json.dumps(value, allow_nan=False)
    with LOCK:
        if native:
            path = native_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=".editor-layout-", dir=path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(value, stream, allow_nan=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, path)
            finally:
                Path(name).unlink(missing_ok=True)
        else:
            load(actor)
            with auth.db() as con:
                con.execute("INSERT INTO editor_layout_preferences(user_id,payload) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload", (actor["id"], payload))
    return value


def register_routes(app):
    def identity(request):
        actor = auth.require_user(request)
        return actor, os.getenv("MTA_NATIVE_SINGLE_USER", "").lower() == "true"

    @app.get("/api/account/editor-layout")
    def get_layout(request: Request):
        actor, native = identity(request)
        return load(actor, native)

    @app.put("/api/account/editor-layout")
    def put_layout(request: Request, body: dict):
        actor, native = identity(request)
        try:
            return save(actor, body, native)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
