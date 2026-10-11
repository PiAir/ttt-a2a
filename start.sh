#!/usr/bin/env bash
# Start de complete demo: scorebord + 2 spelers (A2A-servers) + scheidsrechter.
#
#   ./start.sh                         interactief (TUI), typ daarna bv. "Speel 3 potjes"
#   ./start.sh "Speel 3 potjes"        TUI, met direct een opdracht
#   ./start.sh --exec "Speel 1 potje"  zonder TUI, alleen tekstuitvoer
#
# Gebruik je de losse docker-agent binary i.p.v. de Docker Desktop-plugin:
#   DOCKER_AGENT=./docker-agent ./start.sh
# Variant met de ingebouwde A2A-tool (zie ttt_v2.yaml):
#   CONFIG=ttt_v2.yaml ./start.sh
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "Geen .env gevonden. Doe eerst:  cp .env.example .env   en vul NOLAI_API_KEY in."
  exit 1
fi

DA=${DOCKER_AGENT:-"docker agent"}
CONFIG=${CONFIG:-ttt.yaml}          # CONFIG=ttt_v2.yaml ./start.sh  voor de variant met de ingebouwde A2A-tool
mkdir -p logs

# Poorten moeten vrij zijn; anders praat de scheidsrechter met oude spelers
# (bv. van een eerdere run met een andere docker agent-versie).
for port in 8080 8081 9000; do
  if python3 -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1',$port))==0 else 1)"; then
    echo "Poort $port is al in gebruik (oude speler/scorebord?). Stop die eerst, bv.:"
    echo "  pkill -f 'serve a2a'; pkill -f 'ttt.py serve'"
    exit 1
  fi
done

# Bij afsluiten de hele procesgroep stoppen, inclusief docker-plugin-kindprocessen.
trap 'trap - EXIT INT TERM; kill 0 2>/dev/null' EXIT INT TERM

python3 ttt.py serve 9000 >logs/board.log 2>&1 &
$DA serve a2a "$CONFIG" -a player_x --listen 127.0.0.1:8080 --env-from-file .env >logs/player_x.log 2>&1 &
$DA serve a2a "$CONFIG" -a player_o --listen 127.0.0.1:8081 --env-from-file .env >logs/player_o.log 2>&1 &

echo -n "Spelers opstarten"
for port in 8080 8081; do
  for _ in $(seq 1 30); do
    python3 -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:$port/.well-known/agent-card.json', timeout=1)" 2>/dev/null && break
    echo -n "."; sleep 1
  done
done
echo " klaar."
echo "  docker agent: $($DA version 2>/dev/null | head -1)"
echo "  speler X  -> http://127.0.0.1:8080  (log: logs/player_x.log)"
echo "  speler O  -> http://127.0.0.1:8081  (log: logs/player_o.log)"
echo "  scorebord -> http://localhost:9000"

python3 ttt.py reset >/dev/null   # elke run begint met een schone reeksstand
$DA run "$CONFIG" --yolo --env-from-file .env "$@"
