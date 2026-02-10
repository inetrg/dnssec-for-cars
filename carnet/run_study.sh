#!/bin/bash
logfile="carnet_study_$(date +%Y%m%d%H%M%S).log"
numruns=25
start_time=$(date +%s)

bash statistic-results/clear_results.bash

pkill nsd
echo "Starting H evaluation" >> "$logfile"
python topo-carnet-hostperservice.py --evaluate H --runs $numruns --clean-start >> "$logfile" 2>&1
h_time=$(date +%s)
echo "H evaluation done after $((h_time - start_time)) seconds" >> "$logfile"
sleep 1
echo "Starting F evaluation" >> "$logfile"
python topo-carnet-hostperservice.py --evaluate F --runs $numruns >> "$logfile" 2>&1
f_time=$(date +%s)
echo "F evaluation done after $((f_time - h_time)) seconds" >> "$logfile"
sleep 1
# echo "Starting E evaluation" >> "$logfile"
# python topo-carnet-hostperservice.py --evaluate E --runs $numruns >> "$logfile" 2>&1
# e_time=$(date +%s)
# echo "E evaluation done after $((e_time - f_time)) seconds" >> "$logfile"
# sleep 1
echo "Starting A evaluation" >> "$logfile"
python topo-carnet-hostperservice.py --evaluate A --runs $numruns >> "$logfile" 2>&1
a_time=$(date +%s)
echo "A evaluation done after $((a_time - f_time)) seconds" >> "$logfile"
sleep 1
# echo "Starting G evaluation" >> "$logfile"
# python topo-carnet-hostperservice.py --evaluate G --runs $numruns >> "$logfile" 2>&1
# g_time=$(date +%s)
# echo "G evaluation done after $((g_time - a_time)) seconds" >> "$logfile"
# sleep 1

end_time=$(date +%s)
total_time=$((end_time - start_time))
echo "Total time for all measurements: $total_time seconds" >> "$logfile"
