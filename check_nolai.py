#!/usr/bin/env python3
"""Rooktest voor de NOLAI-endpoint vóór je de demo start.

Controleert per model: (1) gewoon antwoord, (2) tool calling.
Tool calling is nodig voor de scheidsrechter; de spelers hebben alleen (1) nodig.

  python3 check_nolai.py
"""
import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://chat.nolai.nl/api/v1"
MODELS = ["CLUSTER.qwen3.8:latest", "CLUSTER.ornith-1.5:35b"]


def load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def post(path, body, key):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def main():
    load_env()
    key = os.environ.get("NOLAI_API_KEY", "")
    if not key or key.startswith("sk-xxx"):
        raise SystemExit("NOLAI_API_KEY ontbreekt (zet hem in .env).")
    tool = {"type": "function", "function": {
        "name": "ttt_move", "description": "Doe een zet in boter-kaas-eieren",
        "parameters": {"type": "object", "properties": {"cell": {"type": "string"}},
                       "required": ["cell"]}}}
    for m in MODELS:
        print(f"\n== {m}")
        try:
            t = time.time()
            r = post("/chat/completions", {"model": m, "messages": [
                {"role": "user", "content": "Antwoord met precies: MOVE: B2"}]}, key)
            txt = (r["choices"][0]["message"].get("content") or "").strip()
            print(f"  [1] tekst      OK ({time.time()-t:.1f}s): {txt[:80]!r}")
            t = time.time()
            r = post("/chat/completions", {"model": m, "tools": [tool], "messages": [
                {"role": "user", "content": "Doe de zet B2 met de tool ttt_move."}]}, key)
            calls = r["choices"][0]["message"].get("tool_calls") or []
            if calls:
                f = calls[0]["function"]
                print(f"  [2] tool call  OK ({time.time()-t:.1f}s): {f['name']}({f['arguments']})")
            else:
                print("  [2] tool call  GEEN tool call -> ongeschikt als scheidsrechter")
        except urllib.error.HTTPError as e:
            print(f"  FOUT HTTP {e.code}: {e.read()[:300]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"  FOUT: {e}")


if __name__ == "__main__":
    main()
