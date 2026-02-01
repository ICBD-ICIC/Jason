#!/bin/bash

MAS_FILE="$1"
RUNS=50

if [ -z "$MAS_FILE" ]; then
    echo "Usage: $0 <mas_file>"
    exit 1
fi

MAS_NAME=$(basename "$MAS_FILE" .mas2j)
RESULTS_DIR="results/${MAS_NAME}"
LOG_FILE="mas.log"

mkdir -p "$RESULTS_DIR"

for i in $(seq 1 $RUNS); do
    echo "Starting run $i of $RUNS..."

    gradle clean run -PmasFile="$MAS_FILE"

    if [ -f "$LOG_FILE" ]; then
        TIMESTAMP=$(date +"%Y%m%d_%H%M%S_%N")
        mv "$LOG_FILE" "$RESULTS_DIR/mas_run${i}_${TIMESTAMP}.log"
        echo "Saved log as mas_run${i}_${TIMESTAMP}.log"
    else
        echo "Warning: $LOG_FILE not found after run $i"
    fi

    echo "Run $i completed."
    echo "------------------------"
done

echo "All runs completed."
