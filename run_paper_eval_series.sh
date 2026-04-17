#!/bin/bash
# This script runs the evaluation for the paper, using the scripts for
# carnet/series_carnet.bash and the scalability/series_multipubsub.bash.

RUNS=25
OPTIONS=("A" "F" "H")
MAX_RETRIES=100
# scalability
MIN_PUBS=1
MAX_PUBS=100
PUB_STEPS=1
MIN_SUBS=1
MAX_SUBS=10
SUB_STEPS=1

echo "Running paper evaluation series with the following settings:"
echo "  Runs per configuration: $RUNS"
echo "  Max retries for failed runs: $MAX_RETRIES"
echo "  Options: ${OPTIONS[*]}"

echo "Starting evaluation for Carnet..."
cd carnet
bash ./series_carnet.bash --runs $RUNS --max-retries $MAX_RETRIES --options $(IFS=,; echo "${OPTIONS[*]}")
cd ..
echo "Carnet evaluation completed."

echo "Starting evaluation for scalability/Multipubsub..."
cd scalability
bash ./series_multipubsub.bash --runs $RUNS --max-retries $MAX_RETRIES --options $(IFS=,; echo "${OPTIONS[*]}") --min-pubs $MIN_PUBS --max-pubs $MAX_PUBS --pub-steps $PUB_STEPS --min-subs $MIN_SUBS --max-subs $MAX_SUBS --sub-steps $SUB_STEPS --pubs-per-host $MAX_PUBS
cd ..  
echo "Scalability evaluation completed."
