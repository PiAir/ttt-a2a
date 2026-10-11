**English** | [Nederlands](README.nl.md)

# Tic-tac-toe over A2A — docker agent demo

A model on the NOLAI server plays against a local model in LM Studio. Each
model runs as **its own agent in its own process** and is reachable only over
**A2A**. A third agent (the referee) runs the match, on a third model that
does not play. The setup is the same as the Battleship demo in the
[Better Stack video](https://www.youtube.com/watch?v=Mph1H5u3yeA).

> **Language note.** The demo itself is in Dutch: the agent instructions in
> the YAML, the scoreboard, the trash talk and the messages printed by the
> scripts. "Boter-kaas-eieren" is tic-tac-toe, a "potje" is a game, and the
> "scheidsrechter" is the referee. The prompt `Speel 3 potjes` means "Play 3
> games". Error messages are quoted literally below so you can search for
> them.

![Five games of gemma-4-e4b (local) against qwen3.8 (NOLAI), with ornith as referee](screenshots/ttt-gemma-versus-qwen.png)

In this series of five, qwen3.8 won three games, gemma-4-e4b won one and one
game was a draw. With perfect play tic-tac-toe always ends in a draw, so every
win is a mistake by the loser.

```
                      ┌──────────────────────────────┐
                      │ root = referee               │  docker agent run
                      │ CLUSTER.ornith-1.5 (temp 0.1)│
                      └──┬──────────┬────────────┬───┘
            A2A (JSON-RPC)          │            │ A2A (JSON-RPC)
   ┌─────────────────────▼┐   ttt_* tools   ┌───▼──────────────────┐
   │ player_x  :8080      │        │        │ player_o  :8081      │
   │ CLUSTER.qwen3.8      │        ▼        │ gemma-4-e4b (local)  │
   │ docker agent serve   │  ttt.py engine  │ docker agent serve   │
   └──────────────────────┘  (state.json)   └──────────────────────┘
                                   │
                         scoreboard :9000 (browser)
```

* **The players** receive the board and the legal moves. They answer with
  `MOVE: B2` plus `SAY: <trash talk>`. They have no tools and are stateless.
* **The referee** operates the engine (`ttt.py`) through script tools and
  sends messages to the players over A2A.
* **The engine** enforces the rules, so a model cannot cheat. After 3 invalid
  moves in a row the engine plays a random move for that player. The starting
  player alternates each game.

## Files

| File | What |
|---|---|
| `ttt.yaml` | The three agents, the NOLAI provider and the tools (works with every tested version) |
| `ttt_v2.yaml` | The same, but with the built-in `type: a2a` tool (works with docker agent v1.128.0, not with v1.144/v1.150) |
| `ttt.py` | Game engine and live scoreboard (Python standard library only) |
| `a2a_send.py` | Small A2A client used by the referee (see *Why not `type: a2a`?*) |
| `start.sh` | Starts everything in one go and cleans up afterwards |
| `check_nolai.py` | Smoke test: can NOLAI reach the models and does tool calling work? |
| `lm_relay.py` | Relay to the LM Studio server (see *Local model via LM Studio*) |
| `.env.example` | Template for your API key and the LM Studio address |
| `screenshots/` | Screenshots of the different setups |

## Running it (WSL2)

Run the demo in **WSL2, not in PowerShell**. The script tools use bash syntax
(`"$player"`). On Windows, docker agent runs them in PowerShell, where that
syntax does not work.

```bash
cd ttt-a2a
cp .env.example .env              # fill in NOLAI_API_KEY; see also LM Studio below
chmod +x start.sh

docker agent version              # does the Docker Desktop plugin work in WSL?
python3 check_nolai.py            # once: test both models + tool calling

./start.sh                        # TUI; type: Speel 3 potjes
# or
./start.sh --exec "Speel 3 potjes"
```

Open the scoreboard in your Windows browser: <http://localhost:9000>. WSL2
forwards localhost automatically.

Prefer three terminals, as in the video? That works too:

```bash
python3 ttt.py serve                                                                   # terminal 1
docker agent serve a2a ttt.yaml -a player_x --listen 127.0.0.1:8080 --env-from-file .env  # terminal 2
docker agent serve a2a ttt.yaml -a player_o --listen 127.0.0.1:8081 --env-from-file .env  # terminal 3
docker agent run ttt.yaml --yolo --env-from-file .env "Speel 3 potjes"                 # terminal 4
```

**Getting `docker: 'agent' is not a docker command` in WSL?** Enable
*Settings → Resources → WSL integration* for your distro in Docker Desktop.
You can also use a standalone binary; see *Which docker agent version?*.

## Which docker agent version?

| Version | `ttt.yaml` | `ttt_v2.yaml` |
|---|---|---|
| Docker Desktop plugin v1.144.0 | works | does not work (`no compatible transports found`) |
| v1.150 | not tested in the current setup | does not work (same error) |
| Standalone binary [v1.128.0](https://github.com/docker/docker-agent/releases/tag/v1.128.0) | works | works |

So v1.128.0 is the only tested version that runs both variants. This is how
you get it (Linux/WSL2, x86-64; the
[release page](https://github.com/docker/docker-agent/releases/tag/v1.128.0)
also has builds for arm64, macOS and Windows):

```bash
curl -L -o docker-agent https://github.com/docker/docker-agent/releases/download/v1.128.0/docker-agent-linux-amd64
chmod +x docker-agent
DOCKER_AGENT="./docker-agent --data-dir $HOME/.cagent-v128" ./start.sh
```

The separate `--data-dir` is needed if you also use the newer plugin: it
upgrades the shared session database to a format that v1.128.0 refuses
(`session database was created by a newer version`).

![Three games with ttt.yaml and plugin v1.144.0 (earlier setup with two NOLAI players)](screenshots/ttt-2.png)

## Local model via LM Studio

Player O runs on a local model (`google/gemma-4-e4b`) in LM Studio. Put the
address of your LM Studio server in `.env` as `LMSTUDIO_HOST=<ip>:1234` and
start the server in LM Studio (*Developer → Start server*, with *Serve on
local network*).

For this, `start.sh` starts `lm_relay.py`, a relay on `127.0.0.1:1235` that
the YAML points to. It is needed because the Docker Desktop plugin sends every
non-local address through Docker Desktop's HTTP proxy, which rejects the
second request with `HTTP 400: Bad Request`. If you use the separate terminals
instead of `start.sh`, start the relay yourself:
`python3 lm_relay.py <ip>:1234`.

Settings in LM Studio when loading the model (tested on a graphics card with
8 GB):

* **Context Length 8192.** A player only gets the board each turn and
  remembers nothing, so more is not needed. With the default of 262144 tokens
  the model no longer fits in video memory and becomes unusably slow.
* **Max Concurrent 1.** Requests then wait for each other. With several at
  once, speed dropped from about 15 to 1–2 tokens per second.

**Which local model as a player?** Tested on four positions with one clearly
best move (three blocks, one win), on an RTX 2060 SUPER (8 GB):

| Model | Thinking off | Thinking on |
|---|---|---|
| `google/gemma-4-e4b` (Q4_K_M) | 1 of 4 correct, 1–2 s per move | 4 of 4 correct, 17 to 42 s per move |
| `qwen3.6-35b-a3b` (Q5_K_M) | 0 of 4 correct, partly unreadable | no move yet after 5000 tokens (5 minutes) |
| `qwen3.5-9b` (Q3_K_S) | valid but weak moves, 1–2 s | no move yet after 2500 tokens |

That is why the YAML uses `gemma-4-e4b`, with thinking on. For a model that
thinks too long, the relay can switch thinking off: set
`LMSTUDIO_REASONING=none` in `.env`. It then adds `reasoning_effort: none` to
every request. Setting this in the YAML only works in newer versions
(`provider_opts.extra_body.reasoning_effort`); v1.128.0 ignores it.

No local model? Set `model: ornith` again for `player_o` in `ttt.yaml` and
leave `LMSTUDIO_HOST` empty.

**Local model as referee?** That did not work with the tested models on a
graphics card with 8 GB:

| Model | Result as referee |
|---|---|
| `gemma-4-12b-it` (Q4_0) | Tool calls correct, but does not fit in 8 GB: less than 1 token per second |
| `qwen3.5-9b`, uncensored finetune (Q4_K_M) | Regularly writes tool calls out as plain text, after which the run stops |
| `qwen3.5-9b` (Q3_K_S) | Twelve to fifteen tool calls correct, then invents a result and stops |

## Why not `type: a2a`?

The video uses the built-in A2A tool:
`toolsets: [{type: a2a, url: http://127.0.0.1:8080}]`. In the current
docker agent (tested with v1.150, the build of 9 Oct 2026) that does not work
against an agent running with `docker agent serve a2a`:

* the **server** speaks A2A v1.0 (method `SendMessage`);
* the built-in **client** still speaks A2A v0.3 (`message/send`) and stops
  with `failed to create A2A client: no compatible transports found`.

`a2a_send.py` speaks v1.0 and falls back to v0.3. That makes the demo work
with both older and newer versions.

`ttt_v2.yaml` is the same demo with the built-in `type: a2a` tool. Tested: it
fails in both v1.144 and v1.150, but works with the older v1.128.0. Get that
binary as described under *Which docker agent version?* and start with:

```bash
DOCKER_AGENT="./docker-agent --data-dir $HOME/.cagent-v128" CONFIG=ttt_v2.yaml ./start.sh "Speel 1 potje"
```

The screenshot at the top was made with this variant.

By default the built-in A2A tool waits only 30 seconds for an answer. A
thinking model often takes longer; the referee then gets
`A2A call failed: ... context deadline exceeded`, retries, and the game gets
stuck. That is why both A2A toolsets in `ttt_v2.yaml` have `timeout: 300`.

If you immediately see `no compatible transports found`, you are using a
version in which client and server do not match. Use `ttt.yaml` instead.

## What went wrong along the way

The demo did not work on the first try. These are the problems we ran into, in
the order they appeared, with the cause and what was done about it.

| What we saw | Cause | Solution |
|---|---|---|
| `no compatible transports found` with the built-in A2A tool | In v1.144 and v1.150 the server speaks A2A v1.0 and the built-in client still v0.3 | `ttt.yaml` with its own client `a2a_send.py`, or v1.128.0 for `ttt_v2.yaml` |
| v1.128.0 does not start: `session database was created by a newer version` | The plugin and the standalone binary share one session database | Give it its own directory: `--data-dir $HOME/.cagent-v128` |
| Local model reaches 0.3 tokens per second | LM Studio loaded the model with 262144 tokens of context; that fills the video memory | Load with context 8192 |
| A 12B model stays slow, even with a small context | The model itself (7 GB) does not fit next to the context in 8 GB of video memory | Choose a smaller model |
| `HTTP 400: Bad Request` after the first tool call, while LM Studio handles the first request fine | The Docker Desktop plugin sends every non-local address through Docker Desktop's HTTP proxy (`http-proxy.sock`); it rejects the second request on the same connection. `NO_PROXY` does not help | `lm_relay.py`: the YAML points to `127.0.0.1` and the relay forwards |
| Referee writes `<tool_call>…` as plain text and stops | A finetune of qwen3.5-9b uses a tool-call format that LM Studio does not always recognise | Different model |
| Referee invents a result after four or five moves | A small local model cannot sustain the long tool loop; more context did not help | Referee on a larger model (NOLAI) |
| Local player gives no move; the A2A call times out | The model keeps thinking: 2500 to 5000 tokens without an answer | Switch thinking off (`LMSTUDIO_REASONING=none`) or choose a model that finishes thinking sooner |
| After one time-out there are two or three requests at once in LM Studio and everything gets even slower | The referee retries while the first request is still running; parallel requests share the GPU | *Max Concurrent 1* in LM Studio, and above all remove the cause of the time-out |
| With thinking off the local player loses almost everything, or plays invalid moves | Without thinking these models do not read the board properly | Choose a model that is fast enough with thinking on (gemma-4-e4b: 17 to 42 s) |
| Switching thinking off in the YAML works with the plugin but not with v1.128.0 | v1.128.0 ignores `provider_opts.extra_body` | The relay adds `reasoning_effort`, regardless of the version |
| `ttt_v2.yaml`: a player's first move succeeds, then repeated `context deadline exceeded` | The built-in A2A tool waits 30 seconds by default; the player took 25 to 49 seconds per move | `timeout: 300` on the A2A toolsets |
| `start.sh` gives strange errors or does not start in WSL | The script was edited on Windows while it was running, or had picked up CRLF line endings | Do not edit during a run; `.gitattributes` enforces LF |

Two things that helped while searching: docker agent's debug option
(`--debug --log-file <file>`) and the session database in the `--data-dir`,
which contains the literal error messages of failed tool calls.

## A different configuration from this one

This demo was built and tested on one setup: Windows 11 with WSL2 and Docker
Desktop, LM Studio on the same PC (RTX 2060 SUPER, 8 GB) and the NOLAI server
for the larger models. What follows about other setups is **not tested**,
unless stated otherwise.

* **A provider other than NOLAI.** Any OpenAI-compatible server should work.
  In the YAML, change `base_url` and `token_key` under `providers:` and the
  model names under `models:`, and put the key in `.env`. In `check_nolai.py`
  the address and the model names are at the top of the file.
* **Everything in the cloud, no local model.** Give `player_o` a cloud model
  and leave `LMSTUDIO_HOST` empty; the relay then does not start. The first
  version of this demo was tested this way (see the screenshot above).
* **LM Studio on the same PC as WSL2.** Use the PC's network address (e.g.
  `192.168.x.x:1234`) and enable *Serve on local network* in LM Studio.
  `127.0.0.1` inside WSL2 is not the Windows side. This is how this demo runs.
* **Ollama, llama.cpp or another local server.** The relay forwards every
  HTTP request, so `LMSTUDIO_HOST=<ip>:<port>` should be enough, with the
  right model name in the YAML. Whether `reasoning_effort: none` switches
  thinking off there differs per server.
* **Linux or macOS without Docker Desktop.** The proxy problem comes from
  Docker Desktop. With a standalone binary the relay is probably not needed,
  but it does no harm.
* **More video memory.** Larger models then fit and you can try a local model
  as referee. Count on four tool calls per move for the referee and a whole
  match in one context.
* **Choosing a different local model.** Rules of thumb from these tests: the
  model must fit entirely in video memory, a player must answer within the
  time-out (300 s), and a thinking model plays much better than the same model
  without thinking. Test a candidate separately with one board first and see
  how many tokens it spends on thinking.
* **Other ports.** 8080 and 8081 (players), 9000 (scoreboard) and 1235
  (relay) are set in `start.sh` and in the YAML.

## Customising

* **A different model or a different referee:** change `models:` in
  `ttt.yaml`. Keep the referee on a model that does not play, so no player
  judges its own game. `start.sh` reads the names on the scoreboard from the
  YAML itself; you can override them with `TTT_NAME_X`, `TTT_NAME_O` and
  `TTT_NAME_REF`.
* **Making players stronger or weaker:** the strategy is in the players'
  instruction (YAML anchor `&player`).
* **An English-language demo:** translate the instructions and the
  `welcome_message` in the YAML. The players are told to trash-talk in Dutch;
  that is one line in the same instruction.
* **Tool calling does not work via NOLAI?** Only the referee needs tool
  calling. Choose a model for which `check_nolai.py` reports OK at step [2].

## Troubleshooting

| Symptom | Cause / solution |
|---|---|
| `A2A-FOUT: ... niet bereikbaar` ("A2A error: not reachable") | Player is not running; see `logs/player_x.log` |
| Referee makes up moves itself or stops halfway | Model too weak for the tool loop: lower temperature, or a different model as `referee_model` |
| Player O does not respond or is extremely slow | LM Studio server off, wrong address in `LMSTUDIO_HOST`, the model was loaded with too large a context length, or several requests are running at once (see *Local model via LM Studio*) |
| `HTTP 400: Bad Request` after the first tool call | An agent is talking directly to a non-local address; use `lm_relay.py` (see *Local model via LM Studio*) |
| 401/403 from NOLAI | Key not loaded: is `.env` in this directory and are you using `--env-from-file .env`? |
| Very slow | Thinking models reason for a long time per move; the A2A time-out is 300 s (`A2A_TIMEOUT`) |
| `A2A call failed: ... context deadline exceeded` (`ttt_v2.yaml` only) | Player takes longer over a move than the A2A tool's time-out; raise `timeout` on the A2A toolsets |
| Port already in use | Old processes are still running: `pkill -f "serve a2a"` |
