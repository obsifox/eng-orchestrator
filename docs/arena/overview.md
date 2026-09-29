# Arena Tournament - Integration Overview v2.0

> When Claude keeps giving you bad answers, make 100 versions fight to the death.

## Origin
Original skill: https://github.com/Jakeschincariol/arena-skill
Author: Jake Schincariol
Integrated into eng-orchestrator v2.0 as escalation mode.

## What it does
- Spins up N sub-agents (default 100, --quick 16) with Agent tool
- Gives every one exact same task + distinct strategy card (reasoning mode, workflow, strategy)
- 15 x 12 x 12 = 2160 distinct cards, dealer ensures no repeats, balanced even spread
- Single-elimination bracket: attack (2 per match) -> defend (2) -> judge (1) -> collect -> advance
- Until one solution survives
- Final blind check vs baseline if exists

## Strategy Cards
From `skills/arena/strategies.json`:

**Reasoning Modes (15):** first-principles, inversion, analogy, adversarial, constraint-first, worked-example, socratic, contrarian, systems-thinking, decomposition, working-backwards, probabilistic, dialectical, evidence-first, expert-panel

**Workflows (12):** draft-critique-rewrite, outline-first, test-first, research-then-synthesise, three-drafts, requirements-checklist, iterative-deepening, build-then-break, smallest-version-first, options-matrix, open-questions-first, write-then-restructure

**Strategies (12):** simplest, maximal-rigour, user-empathy, edge-cases-first, speed, defensive, etc.

Dealer: proper edge-coloring of bipartite graph, Konig + de Werra balancing, ensures every reasoning/workflow/strategy used evenly, no two agents share reasoning+workflow.

## Rubric
From `skills/arena/rubric.md`, mirrors `bracket.py` WEIGHTS:

- Correctness 30: Is it right? No false claims, bugs
- Completeness 25: Meets every requirement stated
- Specificity 15: Could user act immediately
- Robustness 20: Holds up against attacks
- Clarity 10: Easy to read, length fits task

Weighted total = (c*30 + comp*25 + spec*15 + rob*20 + clar*10)/10 = 0-100
Fatal rule: fatal solution cannot beat non-fatal
Tie breakers: fewer standing attacks, higher correctness, judge choice

## Bracket.py State Machine
Single JSON file `arena.json` holds whole tournament:

- `plan --agents N`: rounds, calls, waves
- `init --agents N --seed S --task-file`: deals cards, pairs round1
- `next`: what to do now, exact command
- `prompts <phase>`: writes briefs per job, lists jobs in waves
- `check <phase>`: missing outputs
- `pairings`: this round's matches + bye
- `collect`: read verdicts, record winners
- `record <match> <winner>`: manual fix
- `advance`: close round, eliminate losers
- `status`: alive/eliminated per round
- `winner`: champion + attacks survived
- `card <agent>`: one competitor's card

Phases: spawn once, then per round attack->defend->judge, final once if baseline, DONE

Waves: Claude Code max 10 tool calls concurrent, so 100 agents = 10 waves spawn, 70 waves total, 71 with final.

## Integration with eng-orchestrator Control Plane

### Run Manager
- Arena dir: `.eng/runs/RUN/arena/` not `.arena/` in root (configurable via `config/arena.yaml`)
- LATEST symlink inside arena dir + `.arena/LATEST` for compatibility
- Task file: `.eng/runs/RUN/arena/task.md` standalone, must include requirements, constraints, context, done criteria, baseline dislike reasons
- Baseline: `.eng/runs/RUN/arena/baseline.md` if previous answer rejected

### State Machine
- Arena runs inside EXECUTION or VERIFICATION state
- Events: ARENA_CREATED, SPAWN_STARTED, SPAWN_COMPLETED, ROUND_STARTED, ROUND_COMPLETED, CHAMPION_SELECTED, FINAL_CHECK
- Logged to `events.jsonl`

### Permissions
- Competitors: ephemeral agents extending worker but sandboxed to arena_dir only
- Attackers: reviewer
- Defenders: worker
- Judges: verifier
- Orchestrator never competes/judges, never reads solutions during run

### Cost Telemetry
- Track per agent if ENG_TELEMETRY=1
- Total tokens = agents * avg
- Updates state.json budget

### Receipt
- Includes arena rounds, agents, champion card, attacks survived, baseline comparison

### Recovery
- arena.json on disk, survives context compaction
- Resume via `arena.sh next --run RUN`

## Triggers
Explicit: /arena, arena, make them compete, مسابقه بده, رقابت -> always run, tell size "100 agents, 7 rounds, 595 calls" and start

Implicit: that's wrong, bad answer, try again, do better, wrong answer, اشتباهه, دوباره, جواب بد -> ask first: full (100) vs quick (16, 91 calls) vs ordinary retry, wait answer

## Orchestrator Rules (from ARENA_SKILL.md)
- You run tournament, never compete/attack/judge, never pick winner
- Every sub-agent gets identical task byte-for-byte via brief, never paraphrase or add hint to one
- Never read solutions/attacks/verdicts during run, only via status/pairings/next
- Run every ARENA command from dir where init ran (where .arena/LATEST lives)
- Sub-agents only write inside arena_dir, tell user if outside
- If user says stop, stop, status shows where, next resumes later
- Suggest accept-edits mode (Shift+Tab) before spawn, don't change settings yourself

## Prompt Templates
From `skills/arena/ARENA_SKILL.md`, filled by bracket.py:

- Competitor: task identical, baseline note, strategy card, how to work, write solution to {{out}}, reply DONE {{agent}} <words>
- Attacker: task identical, strategy card lens, read opponent solution + own, find WRONG/MISSING/BREAKS/VAGUE, at most 7 attacks, FATAL/MAJOR/MINOR, format ATTACK N [type] title / Where / Problem
- Defender: task identical, strategy card, own solution, attacks, decide CONCEDE/REBUT honestly, revised solution standalone, defense file format ATTACK N: CONCEDE|REBUT
- Judge: task identical, rubric, both revised solutions + attacks + defenses, check FIXED/REBUTTED/STANDING yourself, score 0-10 per criterion, fatal only verified flaw, winner higher weighted total, JSON output
- Final: n competitors fought, rubric, solution X/Y, blind, attack both yourself, score, JSON

## Usage via eng.sh
```bash
./scripts/eng.sh arena plan --quick
./scripts/eng.sh arena run --task "Design auth system" --quick
./scripts/eng.sh arena init --run RUN-2026-000001 --task "Fix bug" --agents 16 --seed 7
./scripts/eng.sh arena next --run RUN-2026-000001
./scripts/eng.sh arena prompts spawn --run RUN-2026-000001
# launch waves of 10 Agent tool calls per prompts output
./scripts/eng.sh arena next --run RUN-2026-000001
./scripts/eng.sh arena winner --run RUN-2026-000001
```

## Safety
- No secrets in arena.json
- No auto remote exec
- Sandboxed to arena_dir
- Context compaction safe
- User can stop anytime
