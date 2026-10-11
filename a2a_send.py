#!/usr/bin/env python3
"""Minimale A2A-client: stuur één bericht naar een A2A-agent en print het antwoord.

  python3 a2a_send.py http://127.0.0.1:8080 "Hallo"

Waarom niet de ingebouwde `type: a2a`-tool van docker agent? In recente versies
(gezien in v1.150) serveert `docker agent serve a2a` het A2A v1.0-protocol
(methode `SendMessage`), terwijl de ingebouwde client nog v0.3 spreekt
(`message/send`) en dan faalt met "no compatible transports found".
Dit script probeert v1.0 en valt terug op v0.3, dus het werkt met beide.
Alleen standaardbibliotheek; geen extra pakketten nodig.
"""
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

TIMEOUT = int(os.environ.get("A2A_TIMEOUT", "300"))


def http_json(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def invoke_url(base):
    card = http_json(base.rstrip("/") + "/.well-known/agent-card.json")
    for itf in card.get("supportedInterfaces") or []:  # A2A v1.0
        if itf.get("url"):
            return itf["url"]
    return card.get("url") or base.rstrip("/") + "/invoke"  # A2A v0.3


def texts(node, out):
    """Verzamel alle tekstdelen uit een A2A-resultaat (Task of Message), los van versie."""
    if isinstance(node, dict):
        if (node.get("metadata") or {}).get("adk_partial"):
            return  # streaming-fragmenten overslaan
        if isinstance(node.get("text"), str) and ("parts" not in node):
            out.append(node["text"])
        for key in ("artifacts", "parts", "status", "message", "task"):
            if key in node:
                texts(node[key], out)
    elif isinstance(node, list):
        for item in node:
            texts(item, out)


def send(base, text):
    url = invoke_url(base)
    mid = str(uuid.uuid4())
    v1 = {"jsonrpc": "2.0", "id": 1, "method": "SendMessage",
          "params": {"message": {"role": "ROLE_USER", "messageId": mid, "parts": [{"text": text}]}}}
    resp = http_json(url, v1)
    if (resp.get("error") or {}).get("code") == -32601:  # methode onbekend -> oude server
        v03 = {"jsonrpc": "2.0", "id": 1, "method": "message/send",
               "params": {"message": {"kind": "message", "role": "user", "messageId": mid,
                                      "parts": [{"kind": "text", "text": text}]}}}
        resp = http_json(url, v03)
    if "error" in resp:
        raise RuntimeError(json.dumps(resp["error"])[:500])
    out = []
    texts(resp.get("result"), out)
    answer = "\n".join(t for t in out if t.strip()).strip()
    if not answer:
        raise RuntimeError("leeg antwoord van agent")
    return answer


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    message = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("message", "")
    try:
        print(send(sys.argv[1], message))
    except (urllib.error.URLError, OSError) as e:
        sys.exit(f"A2A-FOUT: {sys.argv[1]} niet bereikbaar ({e}). Draait de speler?")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"A2A-FOUT: {e}")
