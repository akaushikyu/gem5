#!/bin/bash

for num_cpus in 2 4 8; do
  for ee_type in tbe cbe; do
    for code_type in uc cnr cr; do
      for core_type in minor o3; do
        for cache_levels in one-level two-level; do
          echo python scripts/rv-sf-scripts/visualize-riscv-lrsc.py --num-cpus $num_cpus --ee-type $ee_type \
            --code-type $code_type --core-type $core_type --cache-levels $cache_levels \
            -o heatmap_${num_cpus}_${ee_type}_${code_type}_${core_type}_${cache_levels}.png tmp-uc.csv

          python scripts/rv-sf-scripts/visualize-riscv-lrsc.py --num-cpus $num_cpus --ee-type $ee_type \
            --code-type $code_type --core-type $core_type --cache-levels $cache_levels \
            -o $1/heatmap_${num_cpus}_${ee_type}_${code_type}_${core_type}_${cache_levels}.png $2
        done
      done
    done
  done
done
