#!/bin/bash

RESULTS_DIR="results/experiment1"
LOG_FILE="mas.log"
RUNS=50

# Create results directory if it doesn't exist
mkdir -p "$RESULTS_DIR"

for i in $(seq 1 $RUNS); do
    echo "Starting run $i of $RUNS..."

    # Run gradle command
    gradle clean run

    # Check if log file exists
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
