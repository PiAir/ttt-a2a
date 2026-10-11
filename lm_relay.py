#!/usr/bin/env python3
"""TCP-doorgeefluik van 127.0.0.1 naar een LM Studio-server elders in het netwerk.

  python3 lm_relay.py 192.168.0.154:1234 [lokale poort, standaard 1235]

Waarom? De Docker Desktop-plugin (`docker agent`) stuurt elk verzoek naar een
niet-lokaal adres door de HTTP-proxy van Docker Desktop. Die proxy weigert het
tweede verzoek op dezelfde verbinding met "HTTP 400: Bad Request", waardoor de
scheidsrechter na zijn eerste tool call stopt. Verkeer naar 127.0.0.1 gaat niet
door die proxy, dus de YAML wijst naar dit doorgeefluik.
Alleen standaardbibliotheek; geen extra pakketten nodig.
"""
import socket
import sys
import threading


def pump(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()


def main():
    if len(sys.argv) < 2 or ":" not in sys.argv[1]:
        sys.exit(__doc__)
    host, port = sys.argv[1].rsplit(":", 1)
    target = (host, int(port))
    listen = int(sys.argv[2]) if len(sys.argv) > 2 else 1235
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", listen))
    srv.listen(16)
    print(f"LM Studio-doorgeefluik: 127.0.0.1:{listen} -> {host}:{port}", flush=True)
    while True:
        client, _ = srv.accept()
        try:
            upstream = socket.create_connection(target, timeout=10)
            upstream.settimeout(None)
        except OSError as e:
            print(f"LM Studio niet bereikbaar op {host}:{port} ({e})", flush=True)
            client.close()
            continue
        threading.Thread(target=pump, args=(client, upstream), daemon=True).start()
        threading.Thread(target=pump, args=(upstream, client), daemon=True).start()


if __name__ == "__main__":
    main()
