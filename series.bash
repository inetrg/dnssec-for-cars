#!/usr/bin/bash
RUNTIMESLOG="runtimes.log"
UPPER_BOUND_HOSTS=26
touch $RUNTIMESLOG
options=("A" "F" "H")
RUNS=20
for option in "${options[@]}"; do
    for ((host_count = UPPER_BOUND_HOSTS; host_count >= 2; host_count--)); do

        $(which time) -a -o $RUNTIMESLOG -f "${option}-${host_count}-${RUNS}:\t%E real,\t%U user,\t%S sys" python topo-1sw-Nhosts.py --hosts $host_count --evaluate $option --runs $RUNS --clean-start
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
