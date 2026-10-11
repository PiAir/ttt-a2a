#!/usr/bin/env python3
"""Boter-kaas-eieren engine + live scorebord voor de docker-agent A2A-demo.

De engine is de enige bron van waarheid: de scheidsrechter-agent leest het bord
en voert zetten uit via deze CLI; modellen kunnen dus niet "valsspelen".

  python3 ttt.py new            nieuw potje (beginspeler wisselt per potje)
  python3 ttt.py reset          score + potje volledig wissen
  python3 ttt.py view X|O       bord + legale zetten voor speler X of O
  python3 ttt.py move X|O A1 ["sneer"]  zet doen (rij A-C, kolom 1-3), optioneel met trash talk
  python3 ttt.py status         stand van potje en reeks
  python3 ttt.py serve [poort]  live scorebord op http://localhost:9000
"""
import json
import os
import random
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")

# Namen op het scorebord (alleen weergave). start.sh leest ze uit de YAML en
# zet deze variabelen; de waarden hier gelden als je ttt.py los start.
NAMES = {
    "X": os.environ.get("TTT_NAME_X", "qwen3.8"),
    "O": os.environ.get("TTT_NAME_O", "qwen3.5-9b"),
    "R": os.environ.get("TTT_NAME_REF", "qwen3.8"),  # scheidsrechter
}
MAX_ILLEGAL = 3  # na zoveel ongeldige pogingen op rij doet de engine een willekeurige zet

ROWS, COLS = "ABC", "123"
CELLS = [r + c for r in ROWS for c in COLS]
LINES = [
    ["A1", "A2", "A3"], ["B1", "B2", "B3"], ["C1", "C2", "C3"],
    ["A1", "B1", "C1"], ["A2", "B2", "C2"], ["A3", "B3", "C3"],
    ["A1", "B2", "C3"], ["A3", "B2", "C1"],
]


def other(p):
    return "O" if p == "X" else "X"


def blank_game(first):
    return {"board": {c: "" for c in CELLS}, "turn": first, "first": first,
            "winner": None, "line": None, "moves": [], "illegal": {"X": 0, "O": 0},
            "illegal_total": {"X": 0, "O": 0}, "quote": {"X": "", "O": ""}}


def load():
    if not os.path.exists(STATE):
        return {"game_no": 0, "score": {"X": 0, "O": 0, "draw": 0}, "game": None,
                "updated": time.time()}
    with open(STATE, encoding="utf-8") as f:
        return json.load(f)


def save(s):
    s["updated"] = time.time()
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, STATE)


def legal(g):
    return [c for c in CELLS if not g["board"][c]] if not g["winner"] else []


def render(g):
    b = g["board"]
    out = ["      1   2   3"]
    for i, r in enumerate(ROWS):
        out.append(f"  {r}   " + " | ".join(b[r + c] or "." for c in COLS))
        if i < 2:
            out.append("     ---+---+---")
    return "\n".join(out)


def check(g):
    b = g["board"]
    for line in LINES:
        v = b[line[0]]
        if v and all(b[c] == v for c in line):
            g["winner"], g["line"] = v, line
            return
    if all(b.values()):
        g["winner"] = "draw"


def finish(s):
    g = s["game"]
    if g["winner"] == "draw":
        s["score"]["draw"] += 1
    else:
        s["score"][g["winner"]] += 1


def need_game(s):
    if not s["game"]:
        sys.exit("ERROR: geen potje bezig. Start er een met: python3 ttt.py new")
    return s["game"]


def status_text(s):
    g = s["game"]
    sc = s["score"]
    head = (f"Reeks: X ({NAMES['X']}) {sc['X']} - {sc['O']} O ({NAMES['O']}), "
            f"gelijk {sc['draw']}. Potje #{s['game_no']}.")
    if not g:
        return head + " Nog geen potje gestart."
    if g["winner"] == "draw":
        return head + " RESULT: DRAW (gelijkspel)."
    if g["winner"]:
        return head + f" RESULT: WIN {g['winner']} ({NAMES[g['winner']]}) via {'-'.join(g['line'])}."
    return head + f" Aan zet: {g['turn']} ({NAMES[g['turn']]})."


def cmd_new(s, _args):
    if s["game"] and not s["game"]["winner"] and s["game"]["moves"]:
        print("Let op: vorig potje was nog niet afgelopen; het telt niet mee.")
    first = "X" if s["game_no"] % 2 == 0 else "O"  # beginspeler wisselt
    s["game_no"] += 1
    s["game"] = blank_game(first)
    save(s)
    print(f"Nieuw potje #{s['game_no']} gestart. {first} ({NAMES[first]}) begint.")
    print(render(s["game"]))


def cmd_reset(s, _args):
    if os.path.exists(STATE):
        os.remove(STATE)
    print("Score en potje gewist.")


def cmd_view(s, args):
    p = args[0].upper() if args else ""
    if p not in ("X", "O"):
        sys.exit("ERROR: gebruik: view X|O")
    g = need_game(s)
    print(f"Jij speelt: {p}. Tegenstander: {other(p)}.")
    print(render(g))
    if g["winner"]:
        print(status_text(s))
        return
    if g["turn"] != p:
        print(f"Niet aan de beurt: {g['turn']} is aan zet.")
        return
    print(f"Aan zet: {p}")
    print("Legale zetten: " + ", ".join(legal(g)))


def cmd_move(s, args):
    if len(args) < 2 or args[0].upper() not in ("X", "O"):
        sys.exit("ERROR: gebruik: move X|O <cel>   bv. move X B2")
    p, cell = args[0].upper(), args[1].strip().upper()
    quote = " ".join(args[2:]).strip()[:200]
    g = need_game(s)
    if g["winner"]:
        print("ILLEGAL: potje is al afgelopen. " + status_text(s))
        return
    if g["turn"] != p:
        print(f"ILLEGAL: {p} is niet aan de beurt, {g['turn']} is aan zet.")
        return
    if cell not in CELLS or g["board"][cell]:
        g["illegal"][p] += 1
        g["illegal_total"][p] += 1
        why = "bestaat niet" if cell not in CELLS else "is al bezet"
        if g["illegal"][p] >= MAX_ILLEGAL:
            cell = random.choice(legal(g))
            print(f"ILLEGAL: {args[1]} {why}. {MAX_ILLEGAL}x ongeldig op rij -> "
                  f"de engine speelt een willekeurige zet voor {p}: {cell}.")
            penalty = True
        else:
            save(s)
            print(f"ILLEGAL: {args[1]} {why}. Probeer opnieuw "
                  f"({g['illegal'][p]}/{MAX_ILLEGAL}). Legale zetten: " + ", ".join(legal(g)))
            return
    else:
        penalty = False
    g["board"][cell] = p
    g["illegal"][p] = 0
    g["moves"].append({"p": p, "cell": cell, "penalty": penalty, "t": time.time(), "quote": quote})
    if quote:
        g["quote"][p] = quote
    check(g)
    if g["winner"]:
        finish(s)
    else:
        g["turn"] = other(p)
    save(s)
    print(f"OK: {p} speelt {cell}." + (f' {p} zegt: "{quote}"' if quote else ""))
    print(render(g))
    print(status_text(s))


def cmd_status(s, _args):
    if s["game"]:
        print(render(s["game"]))
    print(status_text(s))


# ----------------------------------------------------------------- scorebord
PAGE = """<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Boter-kaas-eieren A2A</title>
<style>
:root{--bg:#0b1020;--panel:#141a2e;--ink:#e7ebf5;--dim:#8a93ad;--x:#4cc2ff;--o:#ff6b8b;--win:#ffd166}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.4 ui-sans-serif,system-ui,Segoe UI,sans-serif;display:flex;justify-content:center;padding:24px 16px}
main{width:100%;max-width:720px}h1{font-size:15px;letter-spacing:.2em;text-transform:uppercase;
color:var(--dim);text-align:center;margin:0 0 18px}
.vs{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;margin-bottom:20px}
.p{background:var(--panel);border-radius:12px;padding:12px 14px;border:2px solid transparent}
.p.turn{border-color:currentColor}.p q{display:block;margin-top:6px;color:var(--ink);font-size:14px;font-style:italic;min-height:20px}.p b{font-size:28px;display:block}.p small{color:var(--dim)}
.px{color:var(--x)}.po{color:var(--o);text-align:right}.score{font-size:30px;font-weight:700;text-align:center}
.score small{display:block;font-size:12px;color:var(--dim);font-weight:400}
.board{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;width:min(360px,100%);margin:0 auto}
.c{aspect-ratio:1;background:var(--panel);border-radius:12px;display:flex;align-items:center;
justify-content:center;font-size:64px;font-weight:800;position:relative}
.c i{position:absolute;top:6px;left:9px;font-size:11px;color:var(--dim);font-style:normal;font-weight:400}
.c.X{color:var(--x)}.c.O{color:var(--o)}.c.win{background:#2a2412;box-shadow:inset 0 0 0 2px var(--win)}
.c.last{box-shadow:inset 0 0 0 2px #ffffff55}
#msg{text-align:center;margin:18px 0 6px;font-size:18px;min-height:26px}
#log{color:var(--dim);font-size:13px;text-align:center;min-height:18px}
.p q:empty::before,.p q:empty::after{content:none}
.ref{background:var(--panel);border-radius:12px;padding:10px 14px;width:min(360px,100%);margin:20px auto 0;
text-align:center;color:var(--win)}.ref small{display:block;color:var(--dim);font-size:11px;letter-spacing:.15em;text-transform:uppercase}
</style></head><body><main>
<h1>Boter-kaas-eieren &middot; live via A2A &middot; docker agent</h1>
<div class="vs"><div class="p px" id="px"><b>X</b><span id="nx"></span><br><small id="ix"></small><q id="qx"></q></div>
<div class="score" id="sc">0 - 0<small></small></div>
<div class="p po" id="po"><b>O</b><span id="no"></span><br><small id="io"></small><q id="qo"></q></div></div>
<div class="board" id="bd"></div><div id="msg"></div><div id="log"></div>
<div class="ref"><small>Scheidsrechter</small><span id="nr"></span></div>
<script>
const cells=["A1","A2","A3","B1","B2","B3","C1","C2","C3"];
async function tick(){
 let s;try{s=await (await fetch('state.json?'+Date.now())).json()}catch(e){return}
 const g=s.game, n=s.names;
 nx.textContent=n.X; no.textContent=n.O; nr.textContent=n.R;
 sc.innerHTML=`${s.score.X} - ${s.score.O}<small>gelijk ${s.score.draw} &middot; potje #${s.game_no}</small>`;
 if(!g){msg.textContent='Wachten op de scheidsrechter...';bd.innerHTML='';return}
 const bad=k=>g.illegal_total[k]?`ongeldige zetten: ${g.illegal_total[k]}`:'';
 ix.textContent=bad('X'); io.textContent=bad('O');
 qx.textContent=(g.quote||{}).X||''; qo.textContent=(g.quote||{}).O||'';
 px.classList.toggle('turn',!g.winner&&g.turn==='X'); po.classList.toggle('turn',!g.winner&&g.turn==='O');
 const last=g.moves.length?g.moves[g.moves.length-1].cell:null, win=g.line||[];
 bd.innerHTML=cells.map(c=>`<div class="c ${g.board[c]} ${win.includes(c)?'win':''} ${c===last?'last':''}"><i>${c}</i>${g.board[c]}</div>`).join('');
 msg.textContent = g.winner==='draw' ? 'Gelijkspel!' : g.winner ? `${g.winner} (${n[g.winner]}) wint!` : `${g.turn} (${n[g.turn]}) denkt na...`;
 log.textContent = g.moves.map(m=>m.p+':'+m.cell+(m.penalty?'*':'')).join('  ');
}
tick(); setInterval(tick,1000);
</script></main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/state.json"):
            s = load()
            s["names"] = NAMES
            body, ctype = json.dumps(s).encode(), "application/json"
        elif self.path in ("/", "/index.html"):
            body, ctype = PAGE.encode(), "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def cmd_serve(_s, args):
    port = int(args[0]) if args else 9000
    print(f"Scorebord: http://localhost:{port}  (Ctrl+C om te stoppen)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


COMMANDS = {"new": cmd_new, "reset": cmd_reset, "view": cmd_view, "move": cmd_move,
            "status": cmd_status, "serve": cmd_serve}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]](load(), sys.argv[2:])
