#!/data/data/com.termux/files/usr/bin/bash
# NOTE: #!/bin/bash also works if this script is sourced rather than executed directly.

set -euo pipefail

# ---------------------------------------------------------------------------
# setup-all.sh - Orchestrator: run all Termux setup scripts for Quest 3
# ---------------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${GREEN}===${NC} $* ${GREEN}===${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Steps to run, in order
STEPS=(
    "setup-base.sh:Base packages"
    "setup-storage.sh:Storage & symlinks"
    "setup-nodejs.sh:Node.js & Claude Code"
    "setup-python.sh:Python & venv"
)

declare -A RESULTS

TOTAL=0
PASSED=0
FAILED=0

# ---- Banner ----------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}============================================${NC}"
echo -e "${BOLD}  Quest 3 Termux - Full Environment Setup${NC}"
echo -e "${BOLD}${GREEN}============================================${NC}"
echo ""
echo -e "  Scripts directory: ${YELLOW}${SCRIPT_DIR}${NC}"
echo -e "  Steps: ${#STEPS[@]}"
echo ""

# ---- Run each step ---------------------------------------------------------
for entry in "${STEPS[@]}"; do
    script="${entry%%:*}"
    label="${entry#*:}"
    TOTAL=$((TOTAL + 1))

    header "Step ${TOTAL}/${#STEPS[@]}: ${label}"

    SCRIPT_PATH="${SCRIPT_DIR}/${script}"

    if [ ! -f "$SCRIPT_PATH" ]; then
        error "Script not found: ${SCRIPT_PATH}"
        RESULTS["$label"]="MISSING"
        FAILED=$((FAILED + 1))
        continue
    fi

    if [ ! -x "$SCRIPT_PATH" ]; then
        warn "Script not executable — running with bash: ${script}"
    fi

    # Run the step script in a subshell so set -e in the child does not
    # kill this orchestrator.  We intentionally allow failures here.
    set +e
    bash "$SCRIPT_PATH"
    EXIT_CODE=$?
    set -e

    if [ "$EXIT_CODE" -eq 0 ]; then
        RESULTS["$label"]="OK"
        PASSED=$((PASSED + 1))
    else
        RESULTS["$label"]="FAILED (exit $EXIT_CODE)"
        FAILED=$((FAILED + 1))
    fi
done

# ---- Summary ---------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}============================================${NC}"
echo -e "${BOLD}  Setup Summary${NC}"
echo -e "${BOLD}${GREEN}============================================${NC}"
echo ""

for entry in "${STEPS[@]}"; do
    label="${entry#*:}"
    result="${RESULTS[$label]}"

    if [ "$result" = "OK" ]; then
        echo -e "  ${GREEN}[PASS]${NC} ${label}"
    else
        echo -e "  ${RED}[FAIL]${NC} ${label}  —  ${result}"
    fi
done

echo ""
echo -e "  Total: ${TOTAL}   Passed: ${GREEN}${PASSED}${NC}   Failed: ${RED}${FAILED}${NC}"
echo ""

if [ "$FAILED" -gt 0 ]; then
    warn "Some steps failed. You can re-run individual scripts to retry."
    warn "Scripts are idempotent — it is safe to run them again."
    exit 1
else
    info "All steps completed successfully. Your Termux environment is ready!"
    echo ""
    echo -e "  ${BOLD}Quick start:${NC}"
    echo -e "    source ~/.bashrc          # reload PATH"
    echo -e "    cd ~/projects             # shared storage"
    echo -e "    source ~/venvs/default/bin/activate   # Python venv"
    echo -e "    claude                    # Claude Code (if installed)"
    echo ""
fi
