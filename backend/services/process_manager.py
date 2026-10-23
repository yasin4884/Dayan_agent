"""مدیریت سرویس‌های محلی برای پنل دولوپر (لاگ + ری‌استارت)."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]

SERVICES: dict[str, dict[str, Any]] = {
    "api": {
        "label": "Backend API",
        "cwd": str(ROOT),
        "port": 8000,
        "command": [sys.executable, "-u", "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        "env": {
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "REDIS_URL": "redis://127.0.0.1:6379/0",
            "QDRANT_URL": "http://127.0.0.1:6333",
            "QDRANT_PATH": "",
            "TEMPORAL_HOST": "127.0.0.1:7233",
        },
    },
    "frontend": {
        "label": "Frontend (دانشجو)",
        "cwd": str(ROOT / "frontend"),
        "port": 3000,
        "command": ["npm", "run", "dev"],
        "env": {},
    },
    "admin": {
        "label": "Admin",
        "cwd": str(ROOT / "admin"),
        "port": 3001,
        "command": ["npm", "run", "dev", "--", "-p", "3001"],
        "env": {},
    },
    "developer": {
        "label": "Developer",
        "cwd": str(ROOT / "developer"),
        "port": 4000,
        "command": ["npm", "run", "dev", "--", "-p", "4000"],
        "env": {},
    },
    "temporal-worker": {
        "label": "Temporal Worker",
        "cwd": str(ROOT),
        "port": 0,
        "command": [sys.executable, "-u", "-m", "temporal.worker"],
        "env": {
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "REDIS_URL": "redis://127.0.0.1:6379/0",
            "QDRANT_URL": "http://127.0.0.1:6333",
            "QDRANT_PATH": "",
            "TEMPORAL_HOST": "127.0.0.1:7233",
        },
    },
    "temporal-server": {
        "label": "Temporal Server",
        "cwd": str(ROOT),
        "port": 7233,
        "command": [str(ROOT / "tools" / "temporal-cli" / "temporal.exe"), "server", "start-dev", "--ip", "127.0.0.1", "--port", "7233", "--ui-port", "8080"],
        "env": {},
    },
}


def _state_path() -> Path:
    p = get_settings().data_root / "dev" / "processes.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _log_path(name: str) -> Path:
    p = get_settings().data_root / "logs" / f"{name}.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    _state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return str(pid) in (out.stdout or "")
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _port_pid(port: int) -> int | None:
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess",
                ],
                capture_output=True,
                text=True,
                timeout=8,
            )
            text = (out.stdout or "").strip()
            return int(text) if text.isdigit() else None
        out = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5)
        text = (out.stdout or "").strip().splitlines()
        return int(text[0]) if text and text[0].isdigit() else None
    except Exception:
        return None


def status() -> list[dict[str, Any]]:
    state = _load_state()
    rows = []
    for key, meta in SERVICES.items():
        port = int(meta["port"] or 0)
        stored = int(state.get(key, {}).get("pid") or 0) or None
        listening = _port_pid(port) if port > 0 else None
        pid = listening or stored
        running = _pid_alive(pid) if pid else False
        if listening:
            running = True
            pid = listening
        rows.append(
            {
                "id": key,
                "label": meta["label"],
                "port": port or None,
                "pid": pid,
                "running": running,
                "log_file": str(_log_path(key)),
            }
        )
    return rows


def stop(name: str) -> dict[str, Any]:
    if name not in SERVICES:
        return {"ok": False, "error": "سرویس ناشناخته"}
    if name == "api":
        # ری‌استارت API را با اسکریپت تأخیری انجام بده؛ stop مستقیم پروسهٔ جاری را می‌کشد
        return {"ok": False, "error": "برای API از restart استفاده کن (stop مستقیم قطع می‌کند)."}
    meta = SERVICES[name]
    port = int(meta["port"])
    pid = _port_pid(port)
    state = _load_state()
    if not pid:
        pid = int(state.get(name, {}).get("pid") or 0) or None
    if pid:
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception as exc:
            logger.warning("stop %s failed: %s", name, exc)
    state.pop(name, None)
    _save_state(state)
    return {"ok": True, "id": name, "stopped": True}


def start(name: str) -> dict[str, Any]:
    if name not in SERVICES:
        return {"ok": False, "error": "سرویس ناشناخته"}
    meta = SERVICES[name]
    port = int(meta["port"] or 0)
    if port > 0:
        existing = _port_pid(port)
        if existing:
            return {"ok": True, "id": name, "already_running": True, "pid": existing}

    log_file = _log_path(name)
    env = os.environ.copy()
    env.update({k: str(v) for k, v in (meta.get("env") or {}).items()})
    env.setdefault("PYTHONIOENCODING", "utf-8")

    log_fh = open(log_file, "a", encoding="utf-8", errors="replace")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]

    proc = subprocess.Popen(
        meta["command"],
        cwd=meta["cwd"],
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=sys.platform != "win32",
    )
    state = _load_state()
    state[name] = {"pid": proc.pid, "started_at": time.time()}
    _save_state(state)
    return {"ok": True, "id": name, "pid": proc.pid, "log_file": str(log_file)}


def restart(name: str) -> dict[str, Any]:
    if name not in SERVICES:
        return {"ok": False, "error": "سرویس ناشناخته"}
    if name == "api":
        return _restart_api_deferred()
    stop(name)
    time.sleep(1.2)
    return start(name)


def _restart_api_deferred() -> dict[str, Any]:
    """API جاری را با اسکریپت جدا بعد از ۱٫۵ثانیه دوباره بالا می‌آورد."""
    log_file = _log_path("api")
    root = str(ROOT).replace("\\", "\\\\")
    log_escaped = str(log_file).replace("\\", "\\\\")
    script = (
        "import time,subprocess,sys,os\n"
        "time.sleep(1.5)\n"
        "env=os.environ.copy();env['PYTHONUNBUFFERED']='1';env['PYTHONIOENCODING']='utf-8';env.setdefault('REDIS_URL','redis://127.0.0.1:6379/0')\n"
        f"log=open(r'{log_escaped}','a',encoding='utf-8')\n"
        "flags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS if sys.platform=='win32' else 0\n"
        "subprocess.Popen([sys.executable,'-u','-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000'],"
        f"cwd=r'{root}',env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)\n"
    )
    if sys.platform == "win32":
        kill_cmd = (
            "powershell -NoProfile -Command "
            "\"Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | "
            "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }\""
        )
        subprocess.Popen(kill_cmd, shell=True)
    else:
        pid = _port_pid(8000)
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
    subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=str(ROOT),
        creationflags=flags,
        close_fds=sys.platform != "win32",
    )
    return {"ok": True, "id": "api", "deferred": True, "message": "API تا چند ثانیه دیگر ری‌استارت می‌شود."}


def read_log(name: str, lines: int = 200) -> dict[str, Any]:
    path = _log_path(name)
    if not path.exists():
        # fallback audit / empty
        return {"id": name, "lines": [], "path": str(path), "missing": True}
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        return {"id": name, "lines": [str(exc)], "path": str(path)}
    return {"id": name, "lines": content[-max(1, min(lines, 2000)) :], "path": str(path)}


def read_audit_tail(lines: int = 100) -> list[str]:
    path = get_settings().data_root / "logs" / "audit.jsonl"
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except Exception:
        return []


def db_snapshot() -> dict[str, Any]:
    """وضعیت سریع دیتابیس‌ها."""
    out: dict[str, Any] = {}
    try:
        from databases.psql.client import check_postgres

        out["postgres"] = check_postgres()
    except Exception as exc:
        out["postgres"] = {"ok": False, "error": str(exc)[:120]}
    try:
        from databases.mongo.memory import get_memory

        mem = get_memory()
        out["mongo"] = {"ok": mem._col is not None}
    except Exception as exc:
        out["mongo"] = {"ok": False, "error": str(exc)[:120]}
    try:
        from core.vector_db import get_vector_db

        vdb = get_vector_db()
        out["qdrant"] = {"ok": True, "chunks": int(vdb.count() or 0)}
    except Exception as exc:
        out["qdrant"] = {"ok": False, "error": str(exc)[:120]}
    try:
        import redis

        settings = get_settings()
        if settings.redis_url:
            r = redis.from_url(settings.redis_url, socket_connect_timeout=0.5)
            out["redis"] = {"ok": bool(r.ping()), "url": settings.redis_url}
        else:
            out["redis"] = {"ok": False, "note": "REDIS_URL خالی است"}
    except Exception as exc:
        out["redis"] = {"ok": False, "error": str(exc)[:120]}
    return out
