#!/usr/bin/bash

# validate that the script runs as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit
fi

# Default parameters
RUNTIMESLOG="scalability_series_$(date +%Y%m%d%H%M%S).log"
MIN_PUBS=1
MAX_PUBS=50
PUB_STEPS=1
MIN_SUBS=1
MAX_SUBS=5
SUB_STEPS=1
PUBS_PER_HOST=50
RUNS=10
OPTIONS=("A" "F" "H")
MAX_RETRIES=5
SCENARIO="topo-1sw-scalability.py"

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --runtimeslog FILE          Log file for runtimes (default: scalability_series_TIMESTAMP.log)
    --min-pubs NUM              Minimum publishers (default: 1)
    --max-pubs NUM              Maximum publishers (default: 50)
    --pub-steps NUM             Publisher step size (default: 1)
    --min-subs NUM              Minimum subscribers (default: 1)
    --max-subs NUM              Maximum subscribers (default: 5)
    --sub-steps NUM             Subscriber step size (default: 1)
    --pubs-per-host NUM         Publishers per host (default: 50)
    --runs NUM                  Number of runs per configuration (default: 10)
    --max-retries NUM             Maximum retries for failed runs (default: 5)
    --options LIST              Comma-separated options to evaluate (default: A,F,H)
    --help                      Display this help message

Example:
    $0 --min-pubs 1 --max-pubs 20 --runs 5 --options A,B,C
EOF
    exit 1
}

print_settings() {
    echo "Current settings:"
    echo "  Runtimes log: $RUNTIMESLOG"
    echo "  Publisher count: $MIN_PUBS to $MAX_PUBS (step $PUB_STEPS)"
    echo "  Subscriber count: $MIN_SUBS to $MAX_SUBS (step $SUB_STEPS)"
    echo "  Publishers per host: $PUBS_PER_HOST"
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
        --min-pubs)
            MIN_PUBS="$2"
            shift 2
            ;;
        --max-pubs)
            MAX_PUBS="$2"
            shift 2
            ;;
        --pub-steps)
            PUB_STEPS="$2"
            shift 2
            ;;
        --min-subs)
            MIN_SUBS="$2"
            shift 2
            ;;
        --max-subs)
            MAX_SUBS="$2"
            shift 2
            ;;
        --sub-steps)
            SUB_STEPS="$2"
            shift 2
            ;;
        --pubs-per-host)
            PUBS_PER_HOST="$2"
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
            IFS=',' read -ra OPTIONS <<< "$2"
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

OPTS="--pubsperhost $PUBS_PER_HOST --onesubhost --max-retries $MAX_RETRIES --copy-logs-on-failure --vsomeip-no-logging"
touch $RUNTIMESLOG
options=("${OPTIONS[@]}")


echo "Cleaning up everything to ensure a fresh start..."
for opt in "${OPTIONS[@]}"; do
    rm -rf logs/${opt}-series/*
    rm -rf statistic-results/${opt}-series/*
done
pkill nsd

start_time=$(date +%s)
for option in "${options[@]}"; do
    for ((pub_count = $MIN_PUBS; pub_count <= $MAX_PUBS; pub_count += $PUB_STEPS)); do
        for ((sub_count = $MIN_SUBS; sub_count <= $MAX_SUBS; sub_count += $SUB_STEPS)); do
            echo "Starting evaluation for option ${option} with $pub_count publishers, $sub_count subscribers"
            option_start_time=$(date +%s)
            python $SCENARIO --evaluate $option --runs $RUNS --pubs $pub_count  --subsperpub $sub_count $OPTS  --clean-start >> "$RUNTIMESLOG" 2>&1
            option_time=$(date +%s)
            echo "Evaluation for option ${option} with $pub_count publishers, $sub_count subscribers completed after $((option_time - option_start_time)) seconds""
            sleep 1
        done
    done
done
end_time=$(date +%s)
total_time=$((end_time - start_time))
echo "Total time for all measurements: $total_time seconds"

echo "Verifying all results are available..."
for option in "${options[@]}"; do
    if [ ! -d "statistic-results/${option}-series" ] || [ -z "$(ls -A "statistic-results/${option}-series")" ]; then
        echo "Error: Result directory statistic-results/${option}-series does not exist or is empty!"
    else
        for pub_count in $(seq $MIN_PUBS $PUB_STEPS $MAX_PUBS); do
            for sub_count in $(seq $MIN_SUBS $SUB_STEPS $MAX_SUBS); do
                for i in $(seq 1 $((RUNS))); do
                    result_file="statistic-results/${option}-series/p${pub_count}_s${sub_count}/run-${i}/${option}-1-#0.csv"
                    if [ ! -f "$result_file" ]; then
                        echo "Error: Result file $result_file is missing!"
                    fi
                done
            done
        done
    fi
done
echo "Results verification completed."
