#!/usr/bin/env bash
set -euo pipefail

# arena.sh - eng-orchestrator wrapper around skills/arena/bracket.py
# Integrates arena tournament with run_manager, state_machine, event_log, permissions
# Original bracket.py from Jakeschincariol/arena-skill, wrapper adds control plane integration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BRACKET="$ROOT/skills/arena/bracket.py"
STRATEGIES="$ROOT/skills/arena/strategies.json"
RUBRIC="$ROOT/skills/arena/rubric.md"

# Ensure bracket.py exists
if [[ ! -f "$BRACKET" ]]; then
  echo "ERROR: bracket.py not found at $BRACKET. Install arena skill first." >&2
  exit 1
fi

# Default values from config/arena.yaml
DEFAULT_AGENTS=100
QUICK_AGENTS=16
DEFAULT_WAVE=10

usage() {
  cat <<EOF
eng-orchestrator Arena Tournament v2.0

Usage: $0 <command> [options]

Commands:
  plan [--agents N|--quick] [--seed S] [--wave W]  - Show rounds/calls/waves
  init --run RUN --task "desc" [--agents N|--quick] [--seed S] [--baseline-file FILE] [--task-file FILE]
  next --run RUN                                    - What to do next (drives loop)
  prompts <phase> --run RUN                         - Write sub-agent briefs for phase
  check <phase> --run RUN                           - Which outputs missing
  pairings --run RUN                                - This round's matches
  collect --run RUN                                 - Record winners from verdicts
  record <match_id> <winner_id> --run RUN [--reason ...] - Manual bookkeeping fix
  advance --run RUN                                 - Close round, eliminate losers
  status --run RUN                                  - Alive/eliminated per round
  winner --run RUN                                  - Champion + attacks survived
  card <agent_id> --run RUN                         - One competitor's strategy card
  create-task --run RUN --task "desc" [--baseline FILE] - Write task.md standalone
  run --task "desc" [--agents N|--quick] [--seed S] [--type TYPE] [--domain DOMAIN] [--tier TIER]
                                                    - Full flow: create run + init + loop guidance

Integration:
  - Uses .eng/runs/RUN/arena/ instead of .arena/
  - Logs events to .eng/runs/RUN/events.jsonl (ARENA_CREATED, etc.)
  - Checks permissions via permission_check.sh
  - Tracks cost via cost_telemetry.sh if ENG_TELEMETRY=1

Examples:
  $0 plan --quick
  $0 run --task "Build a CLI calculator" --quick
  $0 init --run RUN-2026-000001 --task "Fix auth bug" --agents 16 --seed 7
  $0 next --run RUN-2026-000001
  $0 prompts spawn --run RUN-2026-000001
  $0 winner --run RUN-2026-000001
EOF
}

# Helper: get arena dir for a run
arena_dir_for_run() {
  local run="$1"
  echo "$ROOT/.eng/runs/$run/arena"
}

# Helper: log event to run's event log
log_event() {
  local run="$1"
  local type="$2"
  local extra="${3:-}"
  if [[ -f "$SCRIPT_DIR/event_log.sh" ]]; then
    "$SCRIPT_DIR/event_log.sh" append --run "$run" --type "$type" --actor arena-orchestrator ${extra:+--data "$extra"} 2>/dev/null || true
  fi
}

# Helper: ensure run exists
require_run() {
  local run="$1"
  if [[ -z "$run" ]]; then
    echo "ERROR: --run RUN required" >&2
    exit 2
  fi
  if [[ ! -d "$ROOT/.eng/runs/$run" ]]; then
    echo "ERROR: run $run not found at $ROOT/.eng/runs/$run" >&2
    echo "Create with: ./scripts/run_manager.sh create --type arena --task \"desc\"" >&2
    exit 2
  fi
}

cmd="${1:-}"
if [[ -z "$cmd" ]]; then
  usage
  exit 0
fi
shift || true

case "$cmd" in
  plan)
    # Pass through to bracket.py plan, but from current dir
    python3 "$BRACKET" plan "$@"
    ;;

  create-task)
    RUN=""
    TASK=""
    BASELINE=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --run) RUN="$2"; shift 2 ;;
        --task) TASK="$2"; shift 2 ;;
        --baseline) BASELINE="$2"; shift 2 ;;
        --baseline-file) BASELINE="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    require_run "$RUN"
    ADIR=$(arena_dir_for_run "$RUN")
    mkdir -p "$ADIR"
    # Write task.md standalone - must include requirements, constraints, context
    TASK_FILE="$ADIR/task.md"
    if [[ -n "$TASK" ]]; then
      cat > "$TASK_FILE" <<TASK_EOF
# Arena Task - RUN $RUN
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

$TASK

## Context
- Run: $RUN
- Repo: $ROOT
- Created by: arena.sh create-task

## Requirements
- Task as stated above, in user's own words
- Must meet all constraints mentioned in conversation
- Standalone: sub-agents cannot see conversation, only this file

## Done Criteria
- Solution meets task requirements
- No invented requirements
- Evidence-based where applicable
TASK_EOF
      echo "Task written to $TASK_FILE"
    fi
    if [[ -n "$BASELINE" && -f "$BASELINE" ]]; then
      cp "$BASELINE" "$ADIR/baseline.md"
      echo "Baseline copied to $ADIR/baseline.md"
    fi
    # Update LATEST symlink inside arena dir
    echo "$ADIR" > "$ROOT/.eng/runs/$RUN/arena/LATEST" 2>/dev/null || echo "$ADIR" > "$ADIR/LATEST"
    log_event "$RUN" "ARENA_TASK_CREATED"
    ;;

  init)
    RUN=""
    TASK=""
    TASK_FILE=""
    BASELINE_FILE=""
    AGENTS=""
    SEED=""
    QUICK=false
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --run) RUN="$2"; shift 2 ;;
        --task) TASK="$2"; shift 2 ;;
        --task-file) TASK_FILE="$2"; shift 2 ;;
        --baseline-file) BASELINE_FILE="$2"; shift 2 ;;
        --agents) AGENTS="$2"; shift 2 ;;
        --quick) QUICK=true; shift ;;
        --seed) SEED="$2"; shift 2 ;;
        --wave) shift 2 ;; # wave handled in prompts phase, not init
        *) shift ;;
      esac
    done
    require_run "$RUN"
    ADIR=$(arena_dir_for_run "$RUN")
    mkdir -p "$ADIR"

    # If task string provided, create task.md first
    if [[ -n "$TASK" && -z "$TASK_FILE" ]]; then
      "$SCRIPT_DIR/arena.sh" create-task --run "$RUN" --task "$TASK" ${BASELINE_FILE:+--baseline "$BASELINE_FILE"}
      TASK_FILE="$ADIR/task.md"
    fi
    if [[ -z "$TASK_FILE" ]]; then
      TASK_FILE="$ADIR/task.md"
      if [[ ! -f "$TASK_FILE" ]]; then
        echo "ERROR: task file not found. Provide --task \"desc\" or --task-file path" >&2
        exit 2
      fi
    fi

    # Build bracket.py init args
    INIT_ARGS=()
    if [[ "$QUICK" == true ]]; then
      INIT_ARGS+=(--quick)
    elif [[ -n "$AGENTS" ]]; then
      INIT_ARGS+=(--agents "$AGENTS")
    else
      INIT_ARGS+=(--agents "$DEFAULT_AGENTS")
    fi
    if [[ -n "$SEED" ]]; then
      INIT_ARGS+=(--seed "$SEED")
    fi
    INIT_ARGS+=(--task-file "$TASK_FILE")
    if [[ -n "$BASELINE_FILE" ]]; then
      INIT_ARGS+=(--baseline-file "$BASELINE_FILE")
    fi
    INIT_ARGS+=(--dir "$ADIR")

    echo "Initializing arena in $ADIR with ${AGENTS:-$DEFAULT_AGENTS} agents..."
    python3 "$BRACKET" init "${INIT_ARGS[@]}"

    # Also create .arena/LATEST in repo root for bracket.py compatibility
    mkdir -p "$ROOT/.arena"
    echo "$ADIR" > "$ROOT/.arena/LATEST"
    echo "$ADIR" > "$ADIR/LATEST" 2>/dev/null || true

    log_event "$RUN" "ARENA_CREATED" "{\"agents\": \"${AGENTS:-$DEFAULT_AGENTS}\", \"seed\": \"${SEED:-random}\"}"

    # Show plan
    echo ""
    python3 "$BRACKET" plan "${INIT_ARGS[@]}" 2>/dev/null || true
    ;;

  next|prompts|check|pairings|collect|status|winner|card|record|advance)
    RUN=""
    PHASE=""
    MATCH=""
    WINNER_ID=""
    REASON=""
    AGENT_ID=""
    ARGS=()
    # Parse --run and other args
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --run) RUN="$2"; shift 2 ;;
        --reason) REASON="$2"; shift 2 ;;
        --dir) shift 2 ;; # we override dir with run's arena dir
        *) ARGS+=("$1"); shift ;;
      esac
    done

    # For prompts/check, first arg is phase
    if [[ "$cmd" == "prompts" || "$cmd" == "check" ]]; then
      PHASE="${ARGS[0]:-}"
      ARGS=("${ARGS[@]:1}")
    elif [[ "$cmd" == "record" ]]; then
      MATCH="${ARGS[0]:-}"
      WINNER_ID="${ARGS[1]:-}"
      ARGS=("${ARGS[@]:2}")
    elif [[ "$cmd" == "card" ]]; then
      AGENT_ID="${ARGS[0]:-}"
      ARGS=("${ARGS[@]:1}")
    fi

    if [[ -z "$RUN" ]]; then
      # Try to find run from .arena/LATEST or last run
      if [[ -f "$ROOT/.arena/LATEST" ]]; then
        ADIR=$(cat "$ROOT/.arena/LATEST")
        RUN=$(basename "$(dirname "$ADIR")")
        echo "Using run $RUN from .arena/LATEST" >&2
      else
        echo "ERROR: --run RUN required" >&2
        exit 2
      fi
    fi
    require_run "$RUN"
    ADIR=$(arena_dir_for_run "$RUN")

    # Build command
    case "$cmd" in
      prompts)
        if [[ -z "$PHASE" ]]; then echo "ERROR: prompts <phase> required" >&2; exit 2; fi
        python3 "$BRACKET" prompts "$PHASE" --dir "$ADIR" "${ARGS[@]}"
        ;;
      check)
        if [[ -z "$PHASE" ]]; then echo "ERROR: check <phase> required" >&2; exit 2; fi
        python3 "$BRACKET" check "$PHASE" --dir "$ADIR" "${ARGS[@]}"
        ;;
      record)
        if [[ -z "$MATCH" || -z "$WINNER_ID" ]]; then echo "ERROR: record <match_id> <winner_id> required" >&2; exit 2; fi
        if [[ -n "$REASON" ]]; then
          python3 "$BRACKET" record "$MATCH" "$WINNER_ID" --reason "$REASON" --dir "$ADIR" "${ARGS[@]}"
        else
          python3 "$BRACKET" record "$MATCH" "$WINNER_ID" --dir "$ADIR" "${ARGS[@]}"
        fi
        ;;
      card)
        if [[ -z "$AGENT_ID" ]]; then echo "ERROR: card <agent_id> required" >&2; exit 2; fi
        python3 "$BRACKET" card "$AGENT_ID" --dir "$ADIR" "${ARGS[@]}"
        ;;
      *)
        python3 "$BRACKET" "$cmd" --dir "$ADIR" "${ARGS[@]}"
        ;;
    esac

    # Log events based on command
    case "$cmd" in
      next) log_event "$RUN" "ARENA_NEXT_CHECK" ;;
      winner) log_event "$RUN" "ARENA_CHAMPION_SELECTED" ;;
      advance) log_event "$RUN" "ARENA_ROUND_COMPLETED" ;;
    esac
    ;;

  run)
    # Full flow: create run + init + show guidance
    TASK=""
    AGENTS=""
    SEED=""
    QUICK=false
    TYPE="arena"
    DOMAIN="general"
    TIER="T2"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --task) TASK="$2"; shift 2 ;;
        --agents) AGENTS="$2"; shift 2 ;;
        --quick) QUICK=true; shift 2 ;;
        --seed) SEED="$2"; shift 2 ;;
        --type) TYPE="$2"; shift 2 ;;
        --domain) DOMAIN="$2"; shift 2 ;;
        --tier) TIER="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    if [[ -z "$TASK" ]]; then
      echo "ERROR: --task \"desc\" required" >&2
      exit 2
    fi

    # Create run via run_manager.sh
    echo "Creating arena run..."
    RUN_OUTPUT=$("$SCRIPT_DIR/run_manager.sh" create --type "$TYPE" --domain "$DOMAIN" --tier "$TIER" --task "$TASK" 2>&1)
    echo "$RUN_OUTPUT"
    RUN=$(echo "$RUN_OUTPUT" | grep -oE "RUN-[0-9]+-[0-9]+" | head -n1)
    if [[ -z "$RUN" ]]; then
      # Try alternative parsing
      RUN=$(ls -t "$ROOT/.eng/runs/" | head -n1)
    fi
    echo "Run: $RUN"

    # Init arena
    INIT_CMD=("$SCRIPT_DIR/arena.sh" init --run "$RUN" --task "$TASK")
    if [[ "$QUICK" == true ]]; then INIT_CMD+=(--quick); elif [[ -n "$AGENTS" ]]; then INIT_CMD+=(--agents "$AGENTS"); fi
    if [[ -n "$SEED" ]]; then INIT_CMD+=(--seed "$SEED"); fi
    "${INIT_CMD[@]}"

    echo ""
    echo "=== Arena $RUN ready ==="
    echo "Next: $SCRIPT_DIR/arena.sh next --run $RUN"
    echo "Then: $SCRIPT_DIR/arena.sh prompts spawn --run $RUN"
    echo "Spawn waves of 10 sub-agents with Agent tool, then: $SCRIPT_DIR/arena.sh next --run $RUN"
    echo "Loop until DONE, then: $SCRIPT_DIR/arena.sh winner --run $RUN"
    ;;

  *)
    echo "ERROR: unknown command $cmd" >&2
    usage
    exit 2
    ;;
esac
