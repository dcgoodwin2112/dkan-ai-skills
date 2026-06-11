#!/usr/bin/env python3
"""Minimal JSON-RPC-over-stdio MCP client for the live-currency gate.

Speaks newline-delimited JSON-RPC 2.0 to an MCP server subprocess (e.g.
`ddev drush dkan-mcp-server:serve --user=mcp_reader`). Stdlib only — no MCP
SDK, no pip deps — so the gate stays deterministic and runs anywhere python3
does. The server is expected to exit on stdin EOF (the dkan_mcp_server drush
command does); close() escalates to terminate/kill if it doesn't.
"""

from __future__ import annotations

import json
import queue
import shlex
import subprocess
import threading
import time
from collections import deque


class McpError(RuntimeError):
    """Transport failure or JSON-RPC error reply."""

    def __init__(self, message: str, error: dict | None = None):
        super().__init__(message)
        self.error = error or {}


class McpStdioSession:
    """One MCP server subprocess: spawn, handshake, request, close."""

    PROTOCOL = "2025-03-26"

    def __init__(self, cmd, cwd=None, init_timeout=45.0, call_timeout=20.0):
        self.cmd = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
        self.cwd = cwd
        self.init_timeout = init_timeout
        self.call_timeout = call_timeout
        self.proc = None
        self._id = 0
        self._msgs = queue.Queue()
        # drush logs a [notice] line to stderr on start; keep a tail for error
        # messages so e.g. "project is not running" surfaces in diagnostics.
        self.stderr_tail = deque(maxlen=20)
        self.skipped_stdout_lines = 0
        self.server_info = {}
        self.server_protocol = None

    def start(self):
        try:
            self.proc = subprocess.Popen(
                self.cmd, cwd=self.cwd, text=True, bufsize=1,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except OSError as e:
            raise McpError(f"failed to spawn {' '.join(self.cmd)!r}: {e}")
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        threading.Thread(target=self._drain_stdout, daemon=True).start()
        init = self._request("initialize", {
            "protocolVersion": self.PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "dkan-ai-skills-live-gate", "version": "1.0"},
        }, timeout=self.init_timeout)
        # Server may reply with a newer protocol revision; record, don't assert.
        self.server_protocol = init.get("protocolVersion")
        self.server_info = init.get("serverInfo", {})
        self._notify("notifications/initialized")
        return self

    # ---- transport ----

    def _drain_stderr(self):
        for line in self.proc.stderr:
            self.stderr_tail.append(line.rstrip())

    def _drain_stdout(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._msgs.put(json.loads(line))
            except ValueError:
                self.skipped_stdout_lines += 1
        self._msgs.put(None)  # EOF sentinel

    def stderr(self) -> str:
        return " | ".join(list(self.stderr_tail)[-5:]) or "(no stderr)"

    def _send(self, obj):
        try:
            self.proc.stdin.write(json.dumps(obj) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as e:
            raise McpError(f"server stdin closed ({e}); stderr: {self.stderr()}")

    def _notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        self._send(msg)

    def _request(self, method, params=None, timeout=None):
        self._id += 1
        rid = self._id
        msg = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)
        end = time.monotonic() + (timeout or self.call_timeout)
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise McpError(f"timeout awaiting {method} reply; stderr: {self.stderr()}")
            try:
                m = self._msgs.get(timeout=remaining)
            except queue.Empty:
                raise McpError(f"timeout awaiting {method} reply; stderr: {self.stderr()}")
            if m is None:
                raise McpError(f"server exited before replying to {method}; stderr: {self.stderr()}")
            if m.get("id") == rid:
                if "error" in m:
                    err = m["error"]
                    raise McpError(f"{method}: {err.get('message', 'JSON-RPC error')}", err)
                return m.get("result", {})
            # Server notifications / unrelated ids: ignore.

    # ---- MCP operations ----

    def tools_list(self) -> dict:
        tools, cursor = [], None
        while True:
            r = self._request("tools/list", {"cursor": cursor} if cursor else {})
            tools.extend(r.get("tools", []))
            cursor = r.get("nextCursor")
            if not cursor:
                return {"tools": tools}

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        r = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        if r.get("isError"):
            raise McpError(f"tool {name} returned isError: {self.tool_payload(r)!r}")
        return r

    @staticmethod
    def tool_payload(result: dict):
        """Prefer structuredContent; fall back to content[0].text parsed as JSON."""
        if "structuredContent" in result:
            return result["structuredContent"]
        for c in result.get("content") or []:
            if c.get("type") == "text":
                try:
                    return json.loads(c["text"])
                except ValueError:
                    return c["text"]
        return result

    def close(self):
        if not self.proc:
            return
        try:
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        except (OSError, ValueError):
            pass
