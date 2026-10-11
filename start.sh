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
# Adres van de LM Studio-server (host:poort) voor het lokale model; leeg = geen lokaal model.
LMSTUDIO_HOST=${LMSTUDIO_HOST:-$(sed -n 's/^LMSTUDIO_HOST=//p' .env | tr -d '\r"' | tail -1)}
# Optioneel: denk-instelling die het doorgeefluik meestuurt (bv. none); leeg = model beslist zelf.
export LMSTUDIO_REASONING=${LMSTUDIO_REASONING:-$(sed -n 's/^LMSTUDIO_REASONING=//p' .env | tr -d '\r"' | tail -1)}

# Poorten moeten vrij zijn; anders praat de scheidsrechter met oude spelers
# (bv. van een eerdere run met een andere docker agent-versie).
for port in 8080 8081 9000 ${LMSTUDIO_HOST:+1235}; do
  if python3 -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1',$port))==0 else 1)"; then
    echo "Poort $port is al in gebruik (oude speler/scorebord?). Stop die eerst, bv.:"
    echo "  pkill -f 'serve a2a'; pkill -f 'ttt.py serve'; pkill -f lm_relay.py"
    exit 1
  fi
done

# Modelnamen voor het scorebord, uit de YAML gelezen (agent -> models-sleutel -> model).
model_name() {
  python3 - "$CONFIG" "$1" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
def model(key):
    m = re.search(rf"^  {key}:[ ]*\r?\n(?:(?:    .*)?\r?\n)*?    model: *(\S+)", text, re.M)
    return m.group(1) if m else ""
name = model(model(sys.argv[2])) or model(sys.argv[2])
print(re.sub(r"^CLUSTER\.|^.*/|:latest$", "", name))
PY
}
export TTT_NAME_X=${TTT_NAME_X:-$(model_name player_x)}
export TTT_NAME_O=${TTT_NAME_O:-$(model_name player_o)}
export TTT_NAME_REF=${TTT_NAME_REF:-$(model_name root)}

# Bij afsluiten de hele procesgroep stoppen, inclusief docker-plugin-kindprocessen.
trap 'trap - EXIT INT TERM; kill 0 2>/dev/null' EXIT INT TERM

python3 ttt.py serve 9000 >logs/board.log 2>&1 &
# Lokaal model: via een doorgeefluik op 127.0.0.1, zie lm_relay.py voor het waarom.
if [ -n "$LMSTUDIO_HOST" ]; then
  python3 lm_relay.py "$LMSTUDIO_HOST" 1235 >logs/lm_relay.log 2>&1 &
fi
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
[ -n "$LMSTUDIO_HOST" ] && echo "  LM Studio -> $LMSTUDIO_HOST (via 127.0.0.1:1235, log: logs/lm_relay.log)"

python3 ttt.py reset >/dev/null   # elke run begint met een schone reeksstand
$DA run "$CONFIG" --yolo --env-from-file .env "$@"
