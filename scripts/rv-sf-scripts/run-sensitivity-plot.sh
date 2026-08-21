#!/bin/bash
for code_type in cr uc; do
  for core_type in minor o3; do
    for param in rob l1mshr sq; do
      for axis in cbe tbe; do

        echo python scripts/rv-sf-scripts/sensitivity-plot-simticks.py \
          --num-cpus 4 \
          --code-type $code_type \
          --core-type $core_type \
          --cache-levels two-level \
          --param $param \
          --axis $axis \
          --output $1/sensitivity-plot-$code_type-$core_type-$param-$axis.csv \
          --plot-output $1/sensitivity-plot-$code_type-$core_type-$param-$axis.png \
          $2
        python scripts/rv-sf-scripts/sensitivity-plot-simticks.py \
          --num-cpus 4 \
          --code-type $code_type \
          --core-type $core_type \
          --cache-levels two-level \
          --param $param \
          --axis $axis \
          --output $1/sensitivity-plot-$code_type-$core_type-$param-$axis.csv \
          --plot-output $1/sensitivity-plot-$code_type-$core_type-$param-$axis.png \
          $2
      done
    done
  done
done
