#!/usr/bin/bash
RUNTIMESLOG="runtimes.log"
MIN_PUBS=1
MAX_PUBS=1
PUB_STEPS=1
MIN_SUBS=1
MAX_SUBS=50
SUB_STEPS=1
PUBS_PER_HOST=1
OPTS="--pubsperhost $PUBS_PER_HOST" # --onesubhost"
touch $RUNTIMESLOG
options=("A" "F" "H")
RUNS=20
bash ./statistic-results/clear_results.bash
for option in "${options[@]}"; do
    # pub_count=1
    for ((pub_count = $MIN_PUBS; pub_count <= $MAX_PUBS; pub_count += $PUB_STEPS)); do
        for ((sub_count = $MIN_SUBS; sub_count <= $MAX_SUBS; sub_count += $SUB_STEPS)); do
            echo "Running with $pub_count publishers, $sub_count subscribers"
            $(which time) -a -o $RUNTIMESLOG -f "${option}-${pub_count}-${sub_count}-${RUNS}:\t%E real,\t%U user,\t%S sys" python topo-1sw-multipubsub.py --pubs $pub_count  --subsperpub $sub_count $OPTS --evaluate $option --runs $RUNS --clean-start
            cp -r /var/log/multihost ./logs/multihost-${option}-${pub_count}-${sub_count}
            echo "Cleaning up mininet"
            mn -c
            echo "Done."
        done
    done
done
