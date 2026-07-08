#!/usr/bin/env python3
"""Live-currency gate: skill-doc claims vs a RUNNING DKAN site.

evals/live/checks.json pins factual claims from the skill docs (tool surface,
metastore schemas, site/auth posture) as deterministic checks against a live
DKAN dev site, reached over MCP stdio (tools/list + read-only tools/call) plus
HTTP curl probes. Doc-tripwire regexes guard the claim text itself. No LLM,
no tokens, no writes — the writer session is used for tools/list ONLY (there
is no rw tools/call code path). Complements /check-skill-currency, which
checks pinned claims against upstream DOCS; this gate checks the running
SYSTEM.

Env (see docs/EVALS.md):
  EVAL_DKAN_SITE_DIR       DKAN site checkout (DDEV). Unset -> clean SKIP, exit 0.
  EVAL_DKAN_MCP_CMD_RO/_RW stdio command overrides (default: ddev drush
                           dkan-mcp-server:serve --user=mcp_reader|mcp_writer).
  EVAL_DKAN_SITE_URL       site base URL; default derived from .ddev/config.yaml.
  EVAL_DKAN_MCP_HTTP_PATH  MCP endpoint path (default /mcp; per-site base_path).

Exit: 0 = pass or SKIP; 1 = gate failure (any check fail/error, incl. vacuous
doc negatives and extraction failures — a check can never pass because its
path stopped resolving); 2 = bad config or configured-but-unreachable site.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from mcp_stdio import McpError, McpStdioSession

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LIVE_DIR = ROOT / "evals" / "live"

DEFAULT_CMD_RO = "ddev drush dkan-mcp-server:serve --user=mcp_reader"
DEFAULT_CMD_RW = "ddev drush dkan-mcp-server:serve --user=mcp_writer"
PRM_PATH = "/.well-known/oauth-protected-resource"
OPS = {"equals", "count", "contains", "absent", "subset", "matches", "named"}
PROBES = {
    "mcp_ro.tools_list", "mcp_ro.call.get_site_status", "mcp_ro.call.list_schemas",
    "mcp_ro.call.get_schema_dataset", "mcp_rw.tools_list",
    "http.anon", "http.prm", "doc",
}
INIT_BODY = json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-03-26", "capabilities": {},
               "clientInfo": {"name": "live-gate-probe", "version": "1.0"}},
})
HTTP_MARK = "\n__HTTP_STATUS__:"


class ExtractError(Exception):
    pass


# ---------------------------------------------------------------- config

class Config:
    def __init__(self, site_dir, cmd_ro, cmd_rw, ro_default, rw_default, site_url, mcp_path):
        self.site_dir = site_dir
        self.cmd_ro, self.cmd_rw = cmd_ro, cmd_rw
        self.ro_default, self.rw_default = ro_default, rw_default
        self.site_url, self.mcp_path = site_url, mcp_path


def derive_url(site_dir: Path):
    cfg = site_dir / ".ddev" / "config.yaml"
    if cfg.is_file():
        for line in cfg.read_text().splitlines():
            m = re.match(r"^name:\s*['\"]?([\w.-]+)", line)
            if m:
                return f"https://{m.group(1)}.ddev.site"
    return None


def resolve_config():
    """Returns Config, or None for a clean SKIP. Exits 2 on bad config."""
    site_dir = os.environ.get("EVAL_DKAN_SITE_DIR", "").strip()
    if not site_dir:
        print("  SKIP  live-currency gate — EVAL_DKAN_SITE_DIR not set "
              "(point it at a DKAN site checkout, e.g. ~/Sites/dkan-site)")
        return None
    p = Path(site_dir).expanduser()
    if not p.is_dir():
        print(f"ERROR: EVAL_DKAN_SITE_DIR is not a directory: {site_dir}", file=sys.stderr)
        sys.exit(2)
    cmd_ro = os.environ.get("EVAL_DKAN_MCP_CMD_RO", "").strip() or DEFAULT_CMD_RO
    cmd_rw = os.environ.get("EVAL_DKAN_MCP_CMD_RW", "").strip() or DEFAULT_CMD_RW
    site_url = (os.environ.get("EVAL_DKAN_SITE_URL", "").strip() or derive_url(p) or "").rstrip("/") or None
    mcp_path = os.environ.get("EVAL_DKAN_MCP_HTTP_PATH", "").strip() or "/mcp"
    return Config(p, cmd_ro, cmd_rw, cmd_ro == DEFAULT_CMD_RO, cmd_rw == DEFAULT_CMD_RW,
                  site_url, mcp_path)


# ---------------------------------------------------------------- probes

class ProbeRunner:
    """Lazily runs each probe at most once; results cached and shared."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cache = {}
        self.sessions = {}

    def session(self, which: str) -> McpStdioSession:
        if which not in self.sessions:
            cmd = self.cfg.cmd_ro if which == "ro" else self.cfg.cmd_rw
            self.sessions[which] = McpStdioSession(cmd, cwd=str(self.cfg.site_dir)).start()
        return self.sessions[which]

    def close_all(self):
        for s in self.sessions.values():
            s.close()

    def _curl(self, args):
        cmd = ["curl", "-k", "-s", "-m", "10", "-w", HTTP_MARK + "%{http_code}"] + args
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError(f"curl rc={r.returncode}: {r.stderr.strip()[:200]}")
        body, _, status = r.stdout.rpartition(HTTP_MARK)
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = None
        return {"status": int(status), "json": parsed, "body": body}

    def _run(self, pid: str):
        """Returns {"data": ...} | {"skip": reason} | {"error": msg}."""
        c = self.cfg
        if pid.startswith("http.") and not c.site_url:
            return {"skip": "no site URL (set EVAL_DKAN_SITE_URL)"}
        try:
            if pid == "mcp_ro.tools_list":
                return {"data": self.session("ro").tools_list()}
            if pid == "mcp_rw.tools_list":
                # The ONLY rw operation in this gate — listing, never calling.
                return {"data": self.session("rw").tools_list()}
            if pid.startswith("mcp_ro.call."):
                tool = pid.split(".")[-1]
                args = {}
                if tool == "get_schema_dataset":
                    tool, args = "get_schema", {"schemaId": "dataset"}
                s = self.session("ro")
                return {"data": s.tool_payload(s.call_tool(tool, args))}
            post = ["-X", "POST", c.site_url + c.mcp_path,
                    "-H", "Content-Type: application/json",
                    "-H", "Accept: application/json, text/event-stream",
                    "-d", INIT_BODY]
            if pid == "http.anon":
                return {"data": self._curl(post)}
            if pid == "http.prm":
                return {"data": self._curl([c.site_url + PRM_PATH])}
        except (McpError, RuntimeError, subprocess.TimeoutExpired, OSError) as e:
            return {"error": f"{pid}: {e}"}
        return {"error": f"unknown probe {pid}"}

    def get(self, pid: str):
        if pid not in self.cache:
            self.cache[pid] = self._run(pid)
        return self.cache[pid]


# ---------------------------------------------------------------- checks

def extract(data, path: str):
    def index(obj, key):
        if isinstance(obj, dict):
            if key not in obj:
                raise ExtractError(f"key '{key}' missing")
            return obj[key]
        raise ExtractError(f"cannot index {type(obj).__name__} with '{key}'")

    def walk(obj, parts):
        if not parts:
            return obj
        head, rest = parts[0], parts[1:]
        if head.endswith("[]"):
            seq = index(obj, head[:-2]) if head[:-2] else obj
            if not isinstance(seq, list):
                raise ExtractError(f"'{head}' is not a list")
            return [walk(item, rest) for item in seq]
        return walk(index(obj, head), rest)

    return walk(data, path.split("."))


def apply_op(check: dict, actual):
    op, exp = check["op"], check.get("expected")
    pool = list(actual.keys()) if isinstance(actual, dict) else actual
    if op == "equals":
        if check.get("unordered") and isinstance(actual, list) and isinstance(exp, list):
            return sorted(map(str, actual)) == sorted(map(str, exp))
        return actual == exp
    if op == "count":
        return len(actual) == exp
    if op == "contains":
        return all(e in pool for e in exp)
    if op == "absent":
        if not pool:
            raise ExtractError("empty extraction for 'absent' (vacuous)")
        return not any(e in pool for e in exp)
    if op == "subset":
        vals = actual if isinstance(actual, list) else [actual]
        if not vals:
            raise ExtractError("empty extraction for 'subset' (vacuous)")
        return all(v in exp for v in vals)
    if op == "matches":
        vals = actual if isinstance(actual, list) else [actual]
        if not vals:
            raise ExtractError("empty extraction for 'matches' (vacuous)")
        return all(isinstance(v, str) and re.search(exp, v) for v in vals)
    raise ExtractError(f"unknown op {op}")


# Named checks: cross-probe or filtered comparisons awkward as pure data.
# Each returns (passed, actual); `expected` stays declarative in checks.json.

def _names(runner, pid):
    pr = runner.get(pid)
    if "data" not in pr:
        raise ExtractError(pr.get("error") or pr.get("skip") or f"{pid} unavailable")
    return pr["data"]["tools"]


def named_rw_write_tool_names(runner, check):
    actual = sorted(t["name"] for t in _names(runner, "mcp_rw.tools_list")
                    if not (t.get("annotations") or {}).get("readOnlyHint", False))
    return actual == sorted(check["expected"]), actual


def named_ro_subset_of_rw(runner, check):
    ro = {t["name"] for t in _names(runner, "mcp_ro.tools_list")}
    rw = {t["name"] for t in _names(runner, "mcp_rw.tools_list")}
    actual = sorted(ro - rw)  # reader tools missing from the writer
    return actual == check["expected"], actual


def named_dkan_modules_enabled(runner, check):
    pr = runner.get("mcp_ro.call.get_site_status")
    if "data" not in pr:
        raise ExtractError(pr.get("error") or pr.get("skip") or "site status unavailable")
    mods = extract(pr["data"], "dkan.modules")
    actual = {m: mods.get(m, "absent") for m in check["expected"]}
    return all(v == "enabled" for v in actual.values()), actual


NAMED_CHECKS = {
    "rw_write_tool_names": named_rw_write_tool_names,
    "ro_subset_of_rw": named_ro_subset_of_rw,
    "dkan_modules_enabled": named_dkan_modules_enabled,
}


def evaluate_doc(check: dict):
    path = ROOT / check["path"]
    if not path.is_file():
        return "error", f"doc file not found: {check['path']}"
    text = path.read_text()
    pat = check["re"]
    if check["assert"] == "must_match":
        return ("pass", "matched") if re.search(pat, text) else ("fail", "no match in file")
    # must_not_match — liveness first: a negative must catch its own example.
    if not re.search(pat, check["neg_example"]):
        return "error", f"VACUOUS: /{pat}/ fails to match its own neg_example {check['neg_example']!r}"
    hit = re.search(pat, text)
    if hit:
        line = text.count("\n", 0, hit.start()) + 1
        return "fail", f"matched at line {line}: {hit.group(0)!r}"
    return "pass", "no match (stale text absent)"


def evaluate(check: dict, runner: ProbeRunner):
    row = {k: check.get(k) for k in ("id", "group", "probe", "op", "expected", "note", "skill", "doc_ref")}
    if check["probe"] == "doc":
        row["op"] = check["assert"]
        row["expected"] = check["re"]
        row["status"], row["actual"] = evaluate_doc(check)
        return row
    pr = runner.get(check["probe"])
    if "skip" in pr:
        row["status"], row["actual"] = "skip", pr["skip"]
        return row
    if "error" in pr:
        row["status"], row["actual"] = "error", pr["error"]
        return row
    try:
        if check["op"] == "named":
            ok, actual = NAMED_CHECKS[check["id"]](runner, check)
        else:
            actual = extract(pr["data"], check["extract"])
            ok = apply_op(check, actual)
            if isinstance(actual, list) and len(actual) > 40:
                actual = f"[{len(actual)} items]"
    except (ExtractError, McpError) as e:
        row["status"], row["actual"] = "error", str(e)
        return row
    row["status"], row["actual"] = ("pass" if ok else "fail"), actual
    return row


def validate(checks: list) -> list:
    """Config errors in checks.json itself -> exit 2 (mirrors scaffold gate)."""
    problems = []
    for c in checks:
        cid = c.get("id", "?")
        if c.get("probe") not in PROBES:
            problems.append(f"{cid}: unknown probe {c.get('probe')!r}")
        if c.get("probe") == "doc":
            if c.get("assert") not in ("must_match", "must_not_match"):
                problems.append(f"{cid}: bad assert {c.get('assert')!r}")
            if c.get("assert") == "must_not_match" and "neg_example" not in c:
                problems.append(f"{cid}: must_not_match requires a neg_example")
            if not c.get("path") or not c.get("re"):
                problems.append(f"{cid}: doc check needs path + re")
        else:
            if c.get("op") not in OPS:
                problems.append(f"{cid}: unknown op {c.get('op')!r}")
            if c.get("op") == "named" and cid not in NAMED_CHECKS:
                problems.append(f"{cid}: no NAMED_CHECKS entry")
            if c.get("op") != "named" and not c.get("extract"):
                problems.append(f"{cid}: missing extract path")
    return problems


# ---------------------------------------------------------------- main

def site_fingerprint(runner: ProbeRunner):
    pr = runner.get("mcp_ro.call.get_site_status")
    if "data" not in pr:
        return None
    d = pr["data"]
    try:
        return {
            "dkan": d["dkan"]["version"], "drupal": d["drupal"]["version"],
            "datasets_total": d["datasets"]["total"],
            "distributions_total": d["distributions"]["total"],
            "harvest_plans": d["harvest"]["plans"],
        }
    except (KeyError, TypeError):
        return None


def main() -> int:
    cfg = resolve_config()
    if cfg is None:
        return 0  # clean SKIP

    checks = json.loads((LIVE_DIR / "checks.json").read_text())["checks"]
    problems = validate(checks)
    if problems:
        for p in problems:
            print(f"ERROR: checks.json: {p}", file=sys.stderr)
        return 2

    runner = ProbeRunner(cfg)
    try:
        runner.session("ro")  # preflight: configured-but-unreachable -> exit 2
    except McpError as e:
        print(f"ERROR: cannot reach the DKAN MCP server: {e}", file=sys.stderr)
        print(f"  hint: is ddev running? (cd {cfg.site_dir} && ddev start)", file=sys.stderr)
        return 2

    try:
        rows = [evaluate(c, runner) for c in checks]
        fingerprint = site_fingerprint(runner)
        ro_session = runner.sessions.get("ro")
    finally:
        runner.close_all()

    n = {s: sum(1 for r in rows if r["status"] == s) for s in ("pass", "fail", "skip", "error")}
    by_group = {}
    for r in rows:
        by_group.setdefault(r["group"], {"pass": 0, "fail": 0, "skip": 0, "error": 0})
        by_group[r["group"]][r["status"]] += 1
    negs = [c for c in checks if c.get("assert") == "must_not_match"]
    neg_live = sum(1 for c in negs if re.search(c["re"], c["neg_example"]))

    results = {
        "eval": "live_currency",
        "method": "Deterministic probes of a running DKAN dev site over MCP stdio (tools/list + "
                  "read-only tools/call) plus HTTP probes via curl, compared against expected "
                  "values pinned from the skill docs' claims. Doc-tripwire regexes guard the claim "
                  "text itself. No LLM, no writes; the writer session is used for tools/list only.",
        "provenance": {
            "date": date.today().isoformat(),
            "site_url": cfg.site_url,
            "mcp_http_path": cfg.mcp_path,
            "transport": {
                "ro": cfg.cmd_ro if cfg.ro_default else "$EVAL_DKAN_MCP_CMD_RO (override)",
                "rw": (cfg.cmd_rw if cfg.rw_default else "$EVAL_DKAN_MCP_CMD_RW (override)")
                      + " — tools/list only",
            },
            "protocol": {"client": McpStdioSession.PROTOCOL,
                         "server": ro_session.server_protocol if ro_session else None},
            "site_fingerprint": fingerprint,
            "probes_run": sorted(runner.cache.keys()),
            "caveats": [
                "Snapshot of one pinned dev site (dkan_mcp_server 1.0.x on dkan-site DDEV), not "
                "upstream truth; counts will legitimately drift as the module evolves — that "
                "drift is the signal, but expect maintenance.",
                "HTTP posture checks are three shallow probes scoped to the MCP endpoint only "
                "(deliberately silent on /api/1/*), not a security audit.",
                "Deterministic = no LLM and stable given fixed site state; the site itself is "
                "mutable, so results are dated, not byte-reproducible forever.",
            ],
        },
        "summary": {
            "checks": len(rows), "passed": n["pass"], "failed": n["fail"],
            "skipped": n["skip"], "errors": n["error"], "by_group": by_group,
            "negatives_with_example": len(negs), "negatives_live": neg_live,
        },
        "per_check": rows,
    }
    (LIVE_DIR / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    # ---- console summary ----
    print(f"LIVE GATE  {n['pass']}/{len(rows)} checks pass   "
          f"({n['fail']} failed, {n['error']} errors, {n['skip']} skipped)   "
          f"negatives live {neg_live}/{len(negs)}\n")
    print(f"{'id':30} {'group':18} {'probe':30} status")
    for r in rows:
        print(f"{r['id']:30} {r['group']:18} {r['probe']:30} {r['status'].upper()}")

    bad = [r for r in rows if r["status"] in ("fail", "error")]
    if bad:
        print("\n--- failures ---")
        for r in bad:
            print(f"  {r['id']} [{r['status']}]")
            print(f"    expected: {json.dumps(r['expected'])[:120]}")
            print(f"    actual:   {json.dumps(r.get('actual'), default=str)[:240]}")
            if r.get("note"):
                print(f"    note:     {r['note']}")
    print(f"\nwrote {LIVE_DIR / 'results.json'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
