#!/usr/bin/env bash
# eng.sh - Engineering Control Plane CLI v2.1 - with Project Profiles + Arena
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-}" in
  preview)
    shift
    "$SCRIPT_DIR/preview.sh" "$@"
    ;;
  run)
    shift
    "$SCRIPT_DIR/run_manager.sh" create "$@"
    ;;
  list)
    "$SCRIPT_DIR/run_manager.sh" list
    ;;
  show)
    shift
    "$SCRIPT_DIR/run_manager.sh" show "$@"
    ;;
  state)
    shift
    "$SCRIPT_DIR/state_machine.sh" "$@"
    ;;
  event)
    shift
    "$SCRIPT_DIR/event_log.sh" "$@"
    ;;
  recover)
    shift
    "$SCRIPT_DIR/recovery.sh" "$@"
    ;;
  worktree)
    shift
    "$SCRIPT_DIR/worktree.sh" "$@"
    ;;
  receipt)
    shift
    "$SCRIPT_DIR/receipt.sh" "$@"
    ;;
  registry)
    shift
    "$SCRIPT_DIR/skill_registry.sh" "$@"
    ;;
  playbook)
    shift
    "$SCRIPT_DIR/playbook_engine.sh" "$@"
    ;;
  gate)
    shift
    "$SCRIPT_DIR/gate_check.sh" "$@"
    ;;
  arena)
    shift
    "$SCRIPT_DIR/arena.sh" "$@"
    ;;
  knowledge)
    shift
    "$SCRIPT_DIR/knowledge.sh" "$@"
    ;;
  cost)
    shift
    "$SCRIPT_DIR/cost_telemetry.sh" "$@"
    ;;
  project-profile|project)
    shift
    "$SCRIPT_DIR/project_profile.sh" "$@"
    ;;
  -h|--help|help|*)
    echo "eng-orchestrator Control Plane v2.1 - Project Profiles + Arena"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Core Control Plane:"
    echo "  preview [--type TYPE] [--domain DOMAIN] [--task DESC]  - Preview without mutation"
    echo "  run create [--type TYPE] [--domain DOMAIN] [--tier TIER] [--task DESC] - Create run"
    echo "  list - List all runs"
    echo "  show --run RUN-xxx - Show run details"
    echo "  state {list-states|validate|transition|current|history} - State machine (17 states)"
    echo "  event {append|list|tail} - Event log (23+ types)"
    echo "  recover {detect|inspect|reconcile|recover|resume} --run RUN - Recovery"
    echo "  worktree {create|remove|list|detect|cleanup} --run RUN - Worktree isolation"
    echo "  receipt generate --run RUN - Generate receipt.json"
    echo "  registry {discover|inspect|validate|load|disable} - Skill registry"
    echo "  playbook {compose|list} - Playbook engine (12 workflows incl arena + 15 domains)"
    echo "  gate <gate> [--no-run] - Gate engine (G0_Build, G1_Tests, G2_Lens, G3_Security, G4_Release, G5_Project)"
    echo "  knowledge {add|validate|promote-check|list|check} - Structured knowledge"
    echo "  cost {record|show} --run RUN --metric NAME --value VAL - Cost telemetry"
    echo "  project-profile {--check|--help} - Project profile validation (v1.2)"
    echo ""
    echo "Arena Tournament (NEW v2.0):"
    echo "  arena plan [--agents N|--quick] [--seed S] - Show rounds/calls/waves"
    echo "  arena run --task \"desc\" [--agents N|--quick] [--seed S] - Full tournament"
    echo "  arena init --run RUN --task \"desc\" [--agents N|--quick] --seed S"
    echo "  arena next --run RUN - Drive tournament loop (spawn->attack->defend->judge)"
    echo "  arena prompts <phase> --run RUN - Write sub-agent briefs (spawn|attack|defend|judge|final)"
    echo "  arena winner --run RUN - Champion solution + why it won"
    echo "  arena status --run RUN - Alive/eliminated per round"
    echo "  arena pairings --run RUN - Current round matches"
    echo ""
    echo "Examples:"
    echo "  $0 preview --type feature --task 'Add auth'"
    echo "  $0 run create --type feature --domain wordpress --tier T3 --task 'WooCommerce bulk discount'"
    echo "  $0 project-profile --check"
    echo "  $0 arena run --task 'Design auth system' --quick   # 16 agents, 4 rounds, 91 calls"
    echo "  $0 arena run --task 'Fix critical bug' --agents 100  # 100 agents, 7 rounds, 595 calls"
    echo "  $0 arena next --run RUN-2026-000001"
    echo "  $0 receipt generate --run RUN-2026-000001"
    ;;
esac
