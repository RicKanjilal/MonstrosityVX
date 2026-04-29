# Monstrosity VX ♟️

A pure-Python chess engine built from scratch — with iterative deepening, alpha-beta pruning, null-move pruning, late move reductions, transposition tables, killer moves, history heuristics, tapered evaluation, quiescence search, and a Pygame GUI.

No Stockfish under the hood. No external engines called. Every decision the bot makes comes from code in this repo.

---

## Why this exists

Most "I built a chess bot" projects on GitHub call out to Stockfish via the `python-chess` engine wrapper and slap a UI on top. That's fine, but it doesn't teach you anything about how chess engines actually think.

I wanted to write the search and the evaluation myself. Every idea in this engine — every line of the move ordering, every term in the eval function, every pruning condition — came from sitting down and asking *why does Stockfish do it this way?* and then implementing my own version.

The result isn't going to beat Stockfish. But it'll absolutely embarrass a casual player, and the code is something you can actually read and learn from.

---

## What's in the engine

### Search

| Technique | What it does |
|-----------|--------------|
| **Iterative deepening** | Searches depth 1, then 2, then 3... up to `MAX_DEPTH=32` or the time limit |
| **Negamax + alpha-beta** | Standard minimax variant with cutoffs — the backbone of every modern engine |
| **Quiescence search** | At leaf nodes, keep searching captures and promotions to avoid the horizon effect |
| **Null Move Pruning** | "If I skip my turn and the position is *still* good, this branch is winning anyway." Aggressive but huge speedup |
| **Late Move Reductions** | Search later moves at reduced depth — they're usually worse anyway |
| **Check extensions** | Don't reduce depth when in check — these positions deserve more thought |
| **Transposition table** | Zobrist-hashed cache of evaluated positions with exact/lower/upper flags. Capped at 200K entries |

### Move ordering (the thing that makes alpha-beta actually work)

Moves are scored *before* searching, so the best moves get tried first and produce the most cutoffs:

1. **TT move** (the best move from this position last time we saw it) — score 10,000,000
2. **Captures via MVV-LVA** — Most Valuable Victim / Least Valuable Attacker — score 5,000,000+
3. **Promotions** — score 4,000,000+
4. **Killer moves** — quiet moves that caused beta cutoffs at this depth recently — score 80–90K
5. **History heuristic** — depth-squared bonuses for moves that have been historically good

### Evaluation (Tapered)

The eval blends a **middlegame score** and an **endgame score** smoothly based on remaining material:

- **Material values** — standard P=100, N=320, B=330, R=500, Q=900
- **Piece-square tables** — separate MG and EG tables. Knights are weaker in endgames; kings *centralize* in endgames instead of hiding
- **Pawn structure** — penalties for doubled and isolated pawns (middlegame-weighted), bonuses for passed pawns (endgame-weighted)
- **King safety** — castled-king bonus and central-king penalty, both phase-weighted (irrelevant when most pieces are gone)
- **Mobility** — small bonus for legal moves, scaled lightly

The tapered eval is what makes the engine play differently in different phases. In the opening it cares about king safety and piece activity. In the endgame it forgets king safety and pushes its king to the center.

### Other niceties

- **History heuristic decay** — old scores get halved every few moves so the engine doesn't get stuck on outdated patterns
- **Repetition / fivefold / insufficient material** — properly recognized as draws inside search
- **Move-ordering decay** — killer moves cleared at every root search

---

## Running it

```bash
git clone https://github.com/RicKanjilal/MonstrosityVX.git
cd MonstrosityVX
pip install pygame python-chess
python monstrosity.py
```

You play **White**. The engine plays **Black**. Click a piece to select it, click a destination to move. Right-click to undo.

By default the engine searches up to **depth 32** or **10 seconds per move**, whichever comes first. Tweak `MAX_DEPTH` and `TIME_LIMIT_MS` at the top of the file.

> **Asset note:** Piece images go in an `assets/` folder, named `wP.png`, `wR.png`, ..., `bK.png`. If they're missing the engine still runs — you'll just see blank squares where pieces should be.

---

## Configuration

All tuning constants are at the top of the file:

```python
MAX_DEPTH       = 32       # max iterative-deepening depth
TIME_LIMIT_MS   = 10000    # ms per move
TT_MAX_SIZE     = 200_000  # transposition table entry cap
NULL_MOVE_R     = 2        # null-move pruning reduction
LMR_MIN_DEPTH   = 3        # don't reduce shallower than this
LMR_MIN_MOVES   = 4        # only reduce after this many moves tried
HISTORY_DECAY   = 4        # halve history scores every N fullmoves
```

---

## Things I learned building this

- **Move ordering matters more than search depth.** A perfectly-ordered alpha-beta search at depth 6 beats a random-ordered search at depth 8
- **Null move pruning is dangerous.** Skip it when in check or it'll hallucinate winning lines that don't exist
- **Tapered eval is the difference between "decent middlegame engine" and "engine that knows what it's doing."** A flat eval gets crushed in endgames because it keeps the king on the back rank when it should be in the center
- **The horizon effect is real.** Without quiescence search, the engine happily walks into "I just took your queen!" lines that lose to a recapture one ply deeper
- **Pure Python is slow.** A C++ port of this exact engine would be 50–100× faster. The math isn't the bottleneck — the interpreter is

---

## What's next (if I revisit)

- [ ] Aspiration windows on iterative deepening (narrow alpha-beta around the previous score)
- [ ] Proper opening book (Polyglot format)
- [ ] Endgame tablebase support for ≤7 pieces (Syzygy)
- [ ] Static Exchange Evaluation (SEE) for more accurate capture pruning
- [ ] A real UCI interface so it can plug into Arena, Cute Chess, lichess-bot
- [ ] Port the search to C++ via Cython or pybind11 for actual speed

---

## License

MIT — fork it, hack it, beat my engine, send a PR.

---

Built by **Ric Kanjilal** · Grade 10, Don Bosco School, Liluah · Kolkata

*If you read the source: the engine is named "Monstrocity" inside the code window title — that's an old typo from before I renamed the project. I'll fix it eventually.*
