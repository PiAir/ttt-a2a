#!/usr/bin/env python3
"""HTTP-doorgeefluik van 127.0.0.1 naar een LM Studio-server elders in het netwerk.

  python3 lm_relay.py 192.168.0.154:1234 [lokale poort, standaard 1235]

Het doet twee dingen:

1. Omweg rond de Docker Desktop-proxy. De plugin (`docker agent`) stuurt elk
   verzoek naar een niet-lokaal adres door de HTTP-proxy van Docker Desktop.
   Die weigert het tweede verzoek op dezelfde verbinding met "HTTP 400: Bad
   Request". Verkeer naar 127.0.0.1 gaat niet door die proxy, dus de YAML
   wijst naar dit doorgeefluik.
2. Optioneel het denken sturen. Met LMSTUDIO_REASONING=none voegt het
   `reasoning_effort: none` toe aan elk chatverzoek. Sommige lokale modellen
   doen met denken aan minuten over één zet. Dit staat hier en niet in de
   YAML, omdat oudere docker agent-versies (v1.128.0)
   `provider_opts.extra_body` negeren.

Alleen standaardbibliotheek; geen extra pakketten nodig.
"""
import http.client
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REASONING = os.environ.get("LMSTUDIO_REASONING", "")
TIMEOUT = int(os.environ.get("A2A_TIMEOUT", "300"))
SKIP = {"host", "content-length", "connection", "transfer-encoding", "keep-alive"}
TARGET = ("127.0.0.1", 1234)


class Relay(BaseHTTPRequestHandler):
    def forward(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        if body and REASONING and self.path.endswith("/chat/completions"):
            try:
                data = json.loads(body)
                data.setdefault("reasoning_effort", REASONING)
                body = json.dumps(data).encode()
            except ValueError:
                pass  # geen JSON: ongewijzigd doorsturen
        headers = {k: v for k, v in self.headers.items() if k.lower() not in SKIP}
        upstream = http.client.HTTPConnection(*TARGET, timeout=TIMEOUT)
        try:
            upstream.request(self.command, self.path, body or None, headers)
            resp = upstream.getresponse()
        except OSError as e:
            print(f"LM Studio niet bereikbaar op {TARGET[0]}:{TARGET[1]} ({e})", flush=True)
            self.send_error(502, "LM Studio niet bereikbaar")
            return
        # Antwoord ongebufferd doorgeven (streaming); einde = verbinding sluiten.
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in SKIP:
                self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            while True:
                chunk = resp.read1(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except OSError:
            pass  # client haakte af; upstream sluiten stopt de generatie in LM Studio
        finally:
            upstream.close()

    do_GET = do_POST = forward

    def log_message(self, *a):
        pass


def main():
    global TARGET
    if len(sys.argv) < 2 or ":" not in sys.argv[1]:
        sys.exit(__doc__)
    host, port = sys.argv[1].rsplit(":", 1)
    TARGET = (host, int(port))
    listen = int(sys.argv[2]) if len(sys.argv) > 2 else 1235
    print(f"LM Studio-doorgeefluik: 127.0.0.1:{listen} -> {host}:{port}"
          f" (reasoning_effort: {REASONING or 'ongewijzigd'})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", listen), Relay).serve_forever()


if __name__ == "__main__":
    main()
