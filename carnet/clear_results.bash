#!/usr/bin/bash

PROJECT_FOLDER_PATH="/home/vm-user/workspace/mininet-vsomeip-evaluation"
SCENARIO_FOLDER_PATH="${PROJECT_FOLDER_PATH}/carnet"
SCENARIOS=('A-series' 'B-series' 'C-series' 'D-series' 'E-series' 'F-series' 'G-series' 'H-series')
read -p "Are you sure you want to clear all statistic files? (y/n): " confirm
if [[ $confirm != [yY] ]]; then
    echo "Operation cancelled."
    exit 1
fi
for scenario in ${SCENARIOS[@]}; do
    rm ${SCENARIO_FOLDER_PATH}/statistic-results/${scenario}/*.csv
done
