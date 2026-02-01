#!/bin/bash

MAS_FILE="$1"
RUNS=50
LOG_FILE="mas.log"

if [ -z "$MAS_FILE" ]; then
    echo "Usage: $0 <mas_file>"
    exit 1
fi

MAS_NAME=$(basename "$MAS_FILE" .mas2j)

GOOD_DIR="results/${MAS_NAME}_good"
DISCARD_DIR="results/${MAS_NAME}_discard"

mkdir -p "$GOOD_DIR" "$DISCARD_DIR"

echo "Target successful runs: $RUNS"
echo "--------------------------------"

while true; do
    GOOD_COUNT=$(find "$GOOD_DIR" -type f 2>/dev/null | wc -l)
    REMAINING=$((RUNS - GOOD_COUNT))

    if [ "$REMAINING" -le 0 ]; then
        echo "Reached $RUNS good runs. Stopping."
        break
    fi

    echo "Remaining runs needed: $REMAINING"
    echo "Starting new run..."

    gradle clean run -PmasFile="$MAS_FILE"

    if [ ! -f "$LOG_FILE" ]; then
        echo "Warning: $LOG_FILE not found. Skipping."
        continue
    fi

    TIMESTAMP=$(date +"%Y%m%d_%H%M%S_%N")
    AGENT10_COUNT=$(grep -c '^\[agent10\]' "$LOG_FILE")

    if [ "$AGENT10_COUNT" -eq 1 ]; then
        DEST_DIR="$DISCARD_DIR"
        echo "Log discarded (exactly one [agent10] occurrence)."
    else
        DEST_DIR="$GOOD_DIR"
        echo "Log accepted as good run."
    fi

    mv "$LOG_FILE" "$DEST_DIR/mas_${TIMESTAMP}.log"
    echo "Saved to $DEST_DIR/mas_${TIMESTAMP}.log"
    echo "--------------------------------"
done

echo "All experiments completed."
