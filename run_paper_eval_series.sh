#!/bin/bash
# This script runs the evaluation for the paper, using the scripts for
# carnet/series_carnet.bash and the scalability/series_multipubsub.bash.

# validate that the script runs as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit
fi

RUNS=25
OPTIONS=("A" "F" "H")
MAX_RETRIES=100

SKIP_CARNET="false"
SKIP_SCALABILITY_1_50="false"
SKIP_SCALABILITY_5_200="false"

RAW="evaluation/data/raw/$(date +%Y%m%d-%H%M%S)"

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --runs NUM                  Number of runs per configuration (default: 25)
    --max-retries NUM           Maximum retries for failed runs (default: 100)
    --options LIST              Comma-separated options to evaluate (default: A,F,H)
    --skip-carnet               Skip Carnet evaluation (default: false)
    --skip-scalability-1-50     Skip scalability evaluation for 1 pub X 1-50 subs (default: false)
    --skip-scalability-5-200    Skip scalability evaluation for 1-200 pubs X 1-5 subs (default: false)
    --raw_dir DIR               Directory to store raw results (default: evaluation/data/raw/TIMESTAMP)
    --help                      Display this help message

EOF
    exit 1
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
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
        --skip-carnet)
            SKIP_CARNET="true"
            shift 1
            ;;
        --skip-scalability-1-50)
            SKIP_SCALABILITY_1_50="true"
            shift 1
            ;;
        --skip-scalability-5-200)
            SKIP_SCALABILITY_5_200="true"
            shift 1
            ;;
        --raw_dir)
            RAW="$2"
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

exec > >(tee -a "$(date +%Y%m%d-%H%M%S).log") 2>&1

echo "Running paper evaluation series with the following settings:"
echo "  Runs per configuration: $RUNS"
echo "  Max retries for failed runs: $MAX_RETRIES"
echo "  Options: ${OPTIONS[*]}"
echo "  Note: this will take a while to complete (expect several hours, i.e., X hours on Intel 13900K), pre compiled results are in the data/raw folder."

mkdir -p "$RAW"

move_to_raw() {
    local src_dir="$1"
    local dest_dir="$RAW/$2"
    mkdir -p "$dest_dir"
    for opt in "${OPTIONS[@]}"; do
        if [ -d "$src_dir/$opt-series" ]; then
            mv "$src_dir/$opt-series" "$dest_dir/"
        else
            echo "Warning: Cannot move results for directory $src_dir/$opt-series, does not exist and will be skipped."
        fi
    done
}

copy_closest_logs() {
    local base_dir="$1"
    local dest_dir="$RAW/$2"
    mkdir -p "$dest_dir"
    # list files in base_dir, find the file with the timestamp (%Y%m%d-%H%M%S) closest to now, and copy it to dest_dir
    files=("$base_dir"/*.log)
    if [ ${#files[@]} -eq 0 ]; then
        echo "Warning: No log files found in $base_dir to copy."
        return
    fi
    closest_file=""
    closest_time=0
    now=$(date +%s)
    for file in "${files[@]}"; do
        if [[ -f "$file" ]]; then
            filename=$(basename "$file")
            timestamp=$(echo "$filename" | grep -oP '\d{8}-\d{6}' | head -n 1)
            if [[ -n "$timestamp" ]]; then
                # Convert YYYYMMDD-HHMMSS to YYYY-MM-DD HH:MM:SS format for date parsing
                formatted_timestamp=$(echo "$timestamp" | sed 's/\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)-\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1-\2-\3 \4:\5:\6/')
                file_time=$(date -d "$formatted_timestamp" +%s)
                time_diff=$((now - file_time))
                if [[ $closest_time -eq 0 || $time_diff -lt $closest_time ]]; then
                    closest_time=$time_diff
                    closest_file="$file"
                fi            
            fi
        fi
    done
    if [[ -n "$closest_file" ]]; then
        mv "$closest_file" "$dest_dir/"
    else
        echo "Warning: No valid log files with timestamps found in $base_dir to copy."
    fi
}

if [ "$SKIP_CARNET" != "true" ]; then
    echo "Starting evaluation for Carnet..."
    cd carnet
    bash ./series_carnet.bash --runs $RUNS --max-retries $MAX_RETRIES --options $(IFS=,; echo "${OPTIONS[*]}")
    cd ..
    echo "Moving Carnet results to raw data folder..."
    move_to_raw "carnet/statistic-results" "carnet"
    copy_closest_logs "carnet" "carnet"
    echo "Carnet evaluation completed."
else
    echo "Skipping Carnet evaluation as per user request."
fi

if [ "$SKIP_SCALABILITY_1_50" != "true" ]; then
    cd scalability
    echo "Starting evaluation for scalability/Multipubsub 1 pub X 1-50 subs..."
    bash ./series_multipubsub.bash --runs $RUNS --max-retries $MAX_RETRIES --options $(IFS=,; echo "${OPTIONS[*]}") --min-pubs 1 --max-pubs 1 --pub-steps 1 --min-subs 1 --max-subs 50 --sub-steps 1 --pubs-per-host 1
    echo "Moving scalability/Multipubsub 1 pub X 1-50 subs results to raw data folder..."
    cd ..
    move_to_raw "scalability/statistic-results" "scalability/1-50subs_x_1pub"
    copy_closest_logs "scalability" "scalability/1-50subs_x_1pub"
    echo "Scalability/Multipubsub 1 pub X 1-50 subs evaluation completed."
else 
    echo "Skipping scalability/Multipubsub 1 pub X 1-50 subs evaluation as per user request."
fi

if [ "$SKIP_SCALABILITY_5_200" != "true" ]; then
    cd scalability
    echo "Starting evaluation for scalability/Multipubsub 1-200 pubs (step 10) X 1-5 subs..."
    bash ./series_multipubsub.bash --runs $RUNS --max-retries $MAX_RETRIES --options $(IFS=,; echo "${OPTIONS[*]}") --min-pubs 1 --max-pubs 200 --pub-steps 10 --min-subs 1 --max-subs 5 --sub-steps 1 --pubs-per-host 50
    echo "Moving scalability/Multipubsub 1-200 pubs (step 10) X 1-5 subs results to raw data folder..."
    cd ..
    move_to_raw "scalability/statistic-results" "scalability/1-5subs_x_1-200pubs"
    copy_closest_logs "scalability" "scalability/1-5subs_x_1-200pubs"
    echo "Scalability/Multipubsub 1-200 pubs (step 10) X 1-5 subs evaluation completed."
    echo "Scalability evaluation completed."
else 
    echo "Skipping scalability/Multipubsub 1-200 pubs (step 10) X 1-5 subs evaluation as per user request."
fi

copy_closest_logs "." ""
