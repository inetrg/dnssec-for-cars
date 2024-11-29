#!/usr/bin/bash
RUNTIMESLOG="runtimes.log"
UPPER_BOUND_HOSTS=2
touch $RUNTIMESLOG
RUNS=1
for option in {A..H}; do
    for ((host_count = 2; host_count <= UPPER_BOUND_HOSTS; host_count++)); do
        $(which time) -a -o $RUNTIMESLOG -f "${option}-${host_count}-${RUNS}:\t%E real,\t%U user,\t%S sys" python topo-1sw-Nhosts.py --hosts $host_count --evaluate $option --runs $RUNS
        echo "Cleaning up mininet"
        mn -c
        echo "Done."
        # exit_code=$?
        # if [ $exit_code ]; then
        #     echo "Error: Non-zero exit code detected. Exiting."
        #     break 2  # Break out of both loops
        # fi
    done
done
