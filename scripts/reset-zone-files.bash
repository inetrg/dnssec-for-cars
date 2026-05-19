#!/usr/bin/bash

# defaults
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="${PROJECT_PATH:-$(cd "$SCRIPT_DIR/.." && pwd)}"
SCENARIO_DIR="$PROJECT_PATH/scalability"
ZONES_FOLDER="zones"

DEFAULT_ZONE_FILES=("client.zone" "service.zone")
ZONE_FILES_INPUT=()
ZONE_FILES=()

SCENARIO_DIR_INPUT="$SCENARIO_DIR"
ZONES_FOLDER_INPUT="$ZONES_FOLDER"

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --base-dir DIR              Base directory for the project as an absolute or relative path (default: $PROJECT_PATH)
    --scenario DIR              Scenario folder as an absolute path or relative to base directory (default: $SCENARIO_DIR)
    --zones-folder DIR          Zones folder as an absolute or relative path in scenario folder containing zone files (default: $ZONES_FOLDER)
    --zone-file FILE            Zone file as an absolute path or relative to zones folder (repeatable)
    --help                      Display this help message

Example:
    $0 --base-dir /path/to/project --scenario scenario_folder --zones-folder zones --zone-file client.zone --zone-file service.zone
OR:
    $0 --zones-folder /path/to/zones --zone-file custom1.zone --zone-file custom2.zone --zone-file custom3.zone
OR:
    $0 --zone-file /path/to/custom1.zone --zone-file /path/to/custom2.zone --zone-file custom3.zone
EOF
    exit 1
}

resolve_path() {
    local input_path="$1"
    local parent_dir="$2"

    if [[ "$input_path" = /* ]]; then
        echo "$input_path"
    else
        echo "$parent_dir/$input_path"
    fi
}

parse_zones_from_args() {
    # Build paths in dependency order so relative inputs are resolved correctly.
    SCENARIO_DIR="$(resolve_path "$SCENARIO_DIR_INPUT" "$PROJECT_PATH")"
    ZONES_FOLDER="$(resolve_path "$ZONES_FOLDER_INPUT" "$SCENARIO_DIR")"

    if [[ ${#ZONE_FILES_INPUT[@]} -eq 0 ]]; then
        ZONE_FILES_INPUT=("${DEFAULT_ZONE_FILES[@]}")
    fi

    local zone_file
    for zone_file in "${ZONE_FILES_INPUT[@]}"; do
        ZONE_FILES+=("$(resolve_path "$zone_file" "$ZONES_FOLDER")")
    done
}


# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --base|--base-dir)
            PROJECT_PATH="$2"
            shift 2
            ;;
        --scenario|--scenario-folder)
            SCENARIO_DIR_INPUT="$2"
            shift 2
            ;;
        --zones-folder)
            ZONES_FOLDER_INPUT="$2"
            shift 2
            ;;
        --zone-file|--client-zone|--service-zone)
            ZONE_FILES_INPUT+=("$2")
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

parse_zones_from_args

for zone_file in "${ZONE_FILES[@]}"; do
    sed -i '/; =======================================================================/q' "$zone_file"
done
