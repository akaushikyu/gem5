#!/bin/bash

for num_cpus in 2 4 8; do
   for code_type in uc cnr cr; do
     for core_type in minor o3; do
       for cache_levels in one-level two-level; do
         #python scripts/rv-sf-scripts/get-simticks.py --num-cpus $num_cpus \
         #  --code-type $code_type --core-type $core_type --cache-levels $cache_levels \
         #  -o simticks-results/results_${num_cpus}_${code_type}_${core_type}_${cache_levels}.csv \
         #  --plot --plot-output simticks-results/simticks_plot_${num_cpus}_${code_type}_${core_type}_${cache_levels}.png \
         #  --plot-minmax --minmax-output simticks-results/simticks_minmaxplot_${num_cpus}_${code_type}_${core_type}_${cache_levels}.png $1 

         python scripts/rv-sf-scripts/heatmap-visualize.py simticks-results/results_${num_cpus}_${code_type}_${core_type}_${cache_levels}.csv
      done
    done
  done
done
