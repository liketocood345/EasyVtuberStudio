"""In-app silent command channel (no cmd.exe window).

The agent writes one JSON object per line to runtime/agent_cmd.jsonl.
The UI thread executes commands and appends JSON replies to
runtime/agent_reply.jsonl plus the session debug log.
"""
from __future__ import annotations
from portable_process_env import debug_log_path

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

_DEBUG_LOG = debug_log_path('86a17c')
_SESSION = "86a17c"


def _agent_paths(portable_root: Path) -> tuple[Path, Path]:
    runtime = Path(r"e:\easyvtuberstudio-develop\runtime")
    if portable_root:
        candidate = Path(portable_root) / "runtime"
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            runtime = candidate
        except OSError:
            runtime.mkdir(parents=True, exist_ok=True)
    else:
        runtime.mkdir(parents=True, exist_ok=True)
    return runtime / "agent_cmd.jsonl", runtime / "agent_reply.jsonl"


def _debug_ndjson(location: str, message: str, data: dict, hypothesis_id: str = "CMD") -> None:
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "sessionId": _SESSION,
                "runId": "post-fix-agent-cmd",
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
                "timestamp": int(time.time() * 1000),
            }) + "\n")
    except Exception:
        pass


class AgentCmdTerminal:
    """Poll a JSONL command file and run handlers on the UI thread."""

    def __init__(self, portable_root: Path, dispatch: Callable[[str, dict], dict]):
        self.cmd_path, self.reply_path = _agent_paths(portable_root)
        self._dispatch = dispatch
        self._offset = 0
        if self.cmd_path.is_file():
            try:
                self._offset = self.cmd_path.stat().st_size
            except OSError:
                self._offset = 0

    def poll(self) -> list[dict]:
        replies: list[dict] = []
        try:
            size = self.cmd_path.stat().st_size if self.cmd_path.is_file() else 0
        except OSError:
            return replies
        if size < self._offset:
            self._offset = 0
        if size <= self._offset:
            return replies
        try:
            with open(self.cmd_path, "r", encoding="utf-8") as handle:
                handle.seek(self._offset)
                chunk = handle.read()
                self._offset = handle.tell()
        except OSError:
            return replies
        for raw in chunk.splitlines():
            line = raw.strip().lstrip("\ufeff")
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = {"cmd": line}
            cmd = str(payload.get("cmd") or payload.get("command") or "").strip()
            started = time.perf_counter()
            try:
                result = self._dispatch(cmd, payload if isinstance(payload, dict) else {})
            except Exception as exc:
                result = {"ok": False, "error": repr(exc)}
            reply = {
                "cmd": cmd,
                "ok": bool(result.get("ok", True)),
                "ms": round((time.perf_counter() - started) * 1000.0, 1),
                "result": result,
                "timestamp": int(time.time() * 1000),
            }
            replies.append(reply)
            self._append_reply(reply)
            _debug_ndjson(
                "agent_cmd_terminal.py:poll",
                "agent cmd executed",
                {"cmd": cmd, "ok": reply["ok"], "keys": list(result.keys())[:12]},
            )
        return replies

    def _append_reply(self, reply: dict) -> None:
        try:
            with open(self.reply_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(reply, ensure_ascii=False) + "\n")
        except OSError:
            pass


def write_agent_cmd(portable_root: Path, cmd: str, **fields: Any) -> None:
    cmd_path, _ = _agent_paths(portable_root)
    payload = {"cmd": cmd, "timestamp": int(time.time() * 1000)}
    payload.update(fields)
    with open(cmd_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
