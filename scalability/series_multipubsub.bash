#!/usr/bin/bash

# validate that the script runs as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit
fi

# Default parameters
RUNTIMESLOG="./bash_series.log"
MIN_PUBS=2
MAX_PUBS=50
PUB_STEPS=2
MIN_SUBS=1
MAX_SUBS=5
SUB_STEPS=1
PUBS_PER_HOST=50
RUNS=10
OPTIONS=("A" "F" "H")
MAX_RETRIES=2

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --runtimeslog FILE          Log file for runtimes (default: ./bash_series.log)
    --min-pubs NUM              Minimum publishers (default: 2)
    --max-pubs NUM              Maximum publishers (default: 50)
    --pub-steps NUM             Publisher step size (default: 2)
    --min-subs NUM              Minimum subscribers (default: 1)
    --max-subs NUM              Maximum subscribers (default: 5)
    --sub-steps NUM             Subscriber step size (default: 1)
    --pubs-per-host NUM         Publishers per host (default: 50)
    --runs NUM                  Number of runs per configuration (default: 10)
    --max-retries NUM             Maximum retries for failed runs (default: 2)
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

OPTS="--pubsperhost $PUBS_PER_HOST --onesubhost --max-retries $MAX_RETRIES --copy-logs-on-failure"
touch $RUNTIMESLOG
options=("${OPTIONS[@]}")
bash clear_results.bash

# print_settings

for option in "${options[@]}"; do
    # pub_count=1
    for ((pub_count = $MIN_PUBS; pub_count <= $MAX_PUBS; pub_count += $PUB_STEPS)); do
        for ((sub_count = $MIN_SUBS; sub_count <= $MAX_SUBS; sub_count += $SUB_STEPS)); do
            echo "Running with $pub_count publishers, $sub_count subscribers"
            $(which time) -a -o $RUNTIMESLOG -f "${option}-${pub_count}-${sub_count}-${RUNS}:\t%E real,\t%U user,\t%S sys" python topo-1sw-scalability.py --pubs $pub_count  --subsperpub $sub_count $OPTS --evaluate $option --runs $RUNS --clean-start
            # cp -r /var/log/multihost ./logs/multihost-${option}-${pub_count}-${sub_count}
            echo "Done."
        done
    done
done
