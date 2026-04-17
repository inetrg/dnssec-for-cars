#!/bin/bash

# validate that the script runs as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit
fi

RUNTIMESLOG="carnet_study_$(date +%Y%m%d%H%M%S).log"
RUNS=25
OPTIONS=("A" "F" "H")
MAX_RETRIES=5
SCENARIO="topo-carnet.py"

usage() {
    cat << EOF
Usage: $0 [OPTIONS]
Options:
    --runtimeslog FILE          Log file for runtimes (default: logs/carnet_study_TIMESTAMP.log)
    --runs NUM                  Number of runs per configuration (default: 25)
    --max-retries NUM             Maximum retries for failed runs (default: 5)
    --options LIST              Comma-separated options to evaluate (default: A,F,H)
    --help                      Display this help message

Example:
    $0 --runs 10 --options A,B,C
EOF
    exit 1
}

print_settings() {
    echo "Current settings:"
    echo "  Runtimes log: $RUNTIMESLOG"
    echo "  Runs per configuration: $RUNS"
    echo "  Max retries for failed runs: $MAX_RETRIES"
    echo "  Options: ${OPTIONS[*]}"
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --runtimeslog)
            RUNTIMESLOG="$2"
            shift 2
            ;;
        --runs)
            RUNS="$2"
            shift 2
            ;;
        --max-retries)
            MAX_RETRIES="$2"
            shift 2
            ;;
        --options)
            IFS=',' read -r -a OPTIONS <<< "$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

OPTS="--max-retries $MAX_RETRIES --copy-logs-on-failure --vsomeip-no-logging"
touch $RUNTIMESLOG
IF_FIRST="--clean-start"
options=("${OPTIONS[@]}")

echo "Cleaning up everything to ensure a fresh start..."
for opt in "${OPTIONS[@]}"; do
    rm -rf logs/${opt}-series/*
    rm -rf statistic-results/${opt}-series/*
done
pkill nsd

start_time=$(date +%s)
for option in "${options[@]}"; do
    echo "Starting evaluation for option $option"
    option_start_time=$(date +%s)
    python $SCENARIO --evaluate "$option" --runs $RUNS $OPTS $IF_FIRST >> "$RUNTIMESLOG" 2>&1
    option_time=$(date +%s)
    echo "Evaluation for option $option done after $((option_time - option_start_time)) seconds"
    sleep 0.1
    IF_FIRST=""
done
end_time=$(date +%s)
total_time=$((end_time - start_time))
echo "Total time for all measurements: $total_time seconds"

echo "Verifying all results are available..."
for option in "${options[@]}"; do
    if [ ! -d "statistic-results/${option}-series" ] || [ -z "$(ls -A "statistic-results/${option}-series")" ]; then
        echo "Error: Result directory statistic-results/${option}-series does not exist or is empty!"
    else
        for i in $(seq 1 $((RUNS))); do
            result_file="statistic-results/${option}-series/run-${i}/${option}-300-#0.csv"
            if [ ! -f "$result_file" ]; then
                echo "Error: Result file $result_file is missing!"
            fi
        done
    fi
done
echo "Results verification completed."
