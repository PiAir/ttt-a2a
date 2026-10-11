# Boter-kaas-eieren via A2A — docker agent demo

Twee modellen op de NOLAI-server spelen tegen elkaar. Elk model draait als
**eigen agent in een eigen proces** en is alleen via **A2A** bereikbaar. Een
derde agent (de scheidsrechter) leidt de wedstrijd. Het opzet is hetzelfde
als de Battleship-demo uit de
[Better Stack-video](https://www.youtube.com/watch?v=Mph1H5u3yeA).

![Scorebord en scheidsrechter na drie potjes met ttt.yaml](screenshots/ttt-2.png)

```
                      ┌──────────────────────────────┐
                      │ root = scheidsrechter        │  docker agent run
                      │ CLUSTER.qwen3.8 (temp 0.1)   │
                      └──┬──────────┬────────────┬───┘
            A2A (JSON-RPC)          │            │ A2A (JSON-RPC)
   ┌─────────────────────▼┐   ttt_* tools   ┌───▼──────────────────┐
   │ player_x  :8080      │        │        │ player_o  :8081      │
   │ CLUSTER.qwen3.8      │        ▼        │ CLUSTER.ornith-1.5   │
   │ docker agent serve   │  ttt.py engine  │ docker agent serve   │
   └──────────────────────┘  (state.json)   └──────────────────────┘
                                   │
                         scorebord :9000 (browser)
```

* **De spelers** krijgen het bord en de legale zetten. Ze antwoorden met
  `MOVE: B2` plus `SAY: <trash talk>`. Ze hebben geen tools en zijn stateless.
* **De scheidsrechter** bedient de engine (`ttt.py`) via script-tools en
  stuurt de spelers berichten via A2A.
* **De engine** bewaakt de regels. Een model kan dus niet valsspelen. Na 3
  ongeldige zetten op rij speelt de engine een willekeurige zet voor die
  speler. De beginspeler wisselt per potje.

## Bestanden

| Bestand | Wat |
|---|---|
| `ttt.yaml` | De drie agents, de NOLAI-provider en de tools (werkt met elke geteste versie) |
| `ttt_v2.yaml` | Zelfde, maar met de ingebouwde `type: a2a`-tool (werkt met docker agent v1.128.0, niet met v1.144/v1.150) |
| `ttt.py` | Spel-engine en live scorebord (alleen Python-standaardbibliotheek) |
| `a2a_send.py` | Kleine A2A-client die de scheidsrechter gebruikt (zie *Waarom geen `type: a2a`?*) |
| `start.sh` | Start alles in één keer en ruimt na afloop op |
| `check_nolai.py` | Rooktest: bereikt NOLAI de modellen en werkt tool calling? |
| `.env.example` | Sjabloon voor je API-key |
| `screenshots/` | Schermafbeeldingen van beide varianten |

## Draaien (WSL2)

Draai de demo in **WSL2, niet in PowerShell**. De script-tools gebruiken
bash-syntax (`"$player"`). Onder Windows voert docker agent ze uit in
PowerShell, en daar werkt die syntax niet.

```bash
cd ttt-a2a
cp .env.example .env              # vul NOLAI_API_KEY in
chmod +x start.sh

docker agent version              # werkt de Docker Desktop-plugin in WSL?
python3 check_nolai.py            # 1x: beide modellen + tool calling testen

./start.sh                        # TUI; typ: Speel 3 potjes
# of
./start.sh --exec "Speel 3 potjes"
```

Open het scorebord in je Windows-browser: <http://localhost:9000>. WSL2 stuurt
localhost automatisch door.

Wil je liever drie terminals, zoals in de video? Dat kan ook:

```bash
python3 ttt.py serve                                                                   # terminal 1
docker agent serve a2a ttt.yaml -a player_x --listen 127.0.0.1:8080 --env-from-file .env  # terminal 2
docker agent serve a2a ttt.yaml -a player_o --listen 127.0.0.1:8081 --env-from-file .env  # terminal 3
docker agent run ttt.yaml --yolo --env-from-file .env "Speel 3 potjes"                 # terminal 4
```

**Krijg je `docker: 'agent' is not a docker command` in WSL?** Zet dan in
Docker Desktop *Settings → Resources → WSL integration* aan voor je distro.
Je kunt ook de Linux-binary van
<https://github.com/docker/docker-agent/releases> nemen en starten met
`DOCKER_AGENT=./docker-agent ./start.sh`.

## Waarom geen `type: a2a`?

De video gebruikt de ingebouwde A2A-tool:
`toolsets: [{type: a2a, url: http://127.0.0.1:8080}]`. In de huidige
docker agent (getest met v1.150, de build van 9 okt 2026) werkt dat niet
tegen een agent die met `docker agent serve a2a` draait:

* de **server** spreekt A2A v1.0 (methode `SendMessage`);
* de ingebouwde **client** spreekt nog A2A v0.3 (`message/send`) en stopt met
  `failed to create A2A client: no compatible transports found`.

`a2a_send.py` spreekt v1.0 en valt terug op v0.3. Daardoor werkt de demo
met oudere én nieuwere versies.

`ttt_v2.yaml` is dezelfde demo met de ingebouwde `type: a2a`-tool. Getest:
die faalt in v1.144 én v1.150, maar werkt met de oudere v1.128.0. Download
daarvoor de losse Linux-binary van v1.128.0 van
<https://github.com/docker/docker-agent/releases>, zet hem als `docker-agent`
in deze map en start met:

```bash
chmod +x docker-agent
DOCKER_AGENT=./docker-agent CONFIG=ttt_v2.yaml ./start.sh "Speel 1 potje"
```

![ttt_v2.yaml met de ingebouwde A2A-tool in docker agent v1.128.0](screenshots/ttt-1.png)

Zie je meteen `no compatible transports found`, dan gebruik je een versie
waarin client en server niet bij elkaar passen. Gebruik dan `ttt.yaml`.

## Aanpassen

* **Ander model of een andere scheidsrechter:** pas `models:` aan in
  `ttt.yaml`. Zet je de scheidsrechter op een derde model, dan beoordeelt geen
  enkele speler zijn eigen partij. Verander je namen, pas dan ook de
  weergavenamen voor het scorebord aan (`TTT_NAME_X` / `TTT_NAME_O`, of
  bovenin `ttt.py`).
* **Spelers sterker of zwakker maken:** de strategie staat in de instructie
  van de spelers (YAML-anchor `&player`).
* **Tool calling werkt niet via NOLAI?** Alleen de scheidsrechter heeft tool
  calling nodig. Kies daarvoor een model waarbij `check_nolai.py` stap [2] OK
  geeft.

## Problemen oplossen

| Symptoom | Oorzaak / oplossing |
|---|---|
| `A2A-FOUT: ... niet bereikbaar` | Speler draait niet; zie `logs/player_x.log` |
| Scheidsrechter verzint zelf zetten of stopt halverwege | Model te zwak voor de tool-loop: lagere temperature, of een ander model als `referee_model` |
| 401/403 van NOLAI | Key niet geladen: staat `.env` in deze map en gebruik je `--env-from-file .env`? |
| Erg traag | Denkende modellen redeneren lang per zet; de A2A-timeout is 300 s (`A2A_TIMEOUT`) |
| Poort al in gebruik | Oude processen draaien nog: `pkill -f "serve a2a"` |
