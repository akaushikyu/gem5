#!/bin/bash

while getopts "drc" opt
do
  case "$opt" in
    d)
     echo "Dry run (no compile and no actual run)"       
     ;; 
    r)
      echo "Compile and run"
      mkdir rv-sf-workloads
      for cpu in 2 4 8; do
#        for insnBetween in 1 2 3 4; do
#          python scripts/rv-sf-scripts/gen_riscv_lrsc.py --threads $cpu --iterations 5000 \
#            --unconditional --between $insnBetween --output \
#            rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween.cpp
#
#          ./scripts/rv-sf-scripts/compile.sh \
#            rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween
#
#          simcpu=$((cpu + 1))
#          for cbe in 1 4 8 12 16 20 50 80 100 150; do
#            ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#              riscv-lrsc-exp/SF-uc-bb-$insnBetween-minor-one-level-cbe-$cbe-num-cpus-$cpu \
#              configs/riscv-sf-experiments/riscv_minor_one_level_cache.py \
#              --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
#              --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#
#            ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#              riscv-lrsc-exp/SF-uc-bb-$insnBetween-minor-two-level-cbe-$cbe-num-cpus-$cpu \
#              configs/riscv-sf-experiments/riscv_minor_two_level_cache.py \
#              --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
#              --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#
#            ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#              riscv-lrsc-exp/SF-uc-bb-$insnBetween-o3-one-level-cbe-$cbe-num-cpus-$cpu \
#              configs/riscv-sf-experiments/riscv_single_issue_o3_one_level_cache.py \
#              --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
#              --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#
#            ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#              riscv-lrsc-exp/SF-uc-bb-$insnBetween-o3-two-level-cbe-$cbe-num-cpus-$cpu \
#              configs/riscv-sf-experiments/riscv_single_issue_o3_two_level_cache.py \
#              --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
#              --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#          done
#          for tbe in 1 2 4 8 10 20 50 80 100 150 200 300; do
#            ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#              riscv-lrsc-exp/SF-uc-bb-$insnBetween-minor-one-level-tbe-$tbe-num-cpus-$cpu \
#              configs/riscv-sf-experiments/riscv_minor_one_level_cache.py \
#              --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
#              --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#
#            ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#              riscv-lrsc-exp/SF-uc-bb-$insnBetween-minor-two-level-tbe-$tbe-num-cpus-$cpu \
#              configs/riscv-sf-experiments/riscv_minor_two_level_cache.py \
#              --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
#              --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#
#            ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#              riscv-lrsc-exp/SF-uc-bb-$insnBetween-o3-one-level-tbe-$tbe-num-cpus-$cpu \
#              configs/riscv-sf-experiments/riscv_single_issue_o3_one_level_cache.py \
#              --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
#              --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#
#            ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#              riscv-lrsc-exp/SF-uc-bb-$insnBetween-o3-two-level-tbe-$tbe-num-cpus-$cpu \
#              configs/riscv-sf-experiments/riscv_single_issue_o3_two_level_cache.py \
#              --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
#              --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#          done
#          ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
#          riscv-lrsc-exp/NOSF-uc-bb-$insnBetween-minor-one-level-num-cpus-$cpu \
#          configs/riscv-sf-experiments/riscv_minor_one_level_cache.py \
#          --num-cpus $simcpu --mem-size=8GB \
#          --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#
#          ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
#          riscv-lrsc-exp/NOSF-uc-bb-$insnBetween-minor-two-level-num-cpus-$cpu \
#          configs/riscv-sf-experiments/riscv_minor_two_level_cache.py \
#          --num-cpus $simcpu --mem-size=8GB \
#          --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#
#          ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
#          riscv-lrsc-exp/NOSF-uc-bb-$insnBetween-o3-one-level-num-cpus-$cpu \
#          configs/riscv-sf-experiments/riscv_single_issue_o3_one_level_cache.py \
#          --num-cpus $simcpu --mem-size=8GB \
#          --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween &
#
#          ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
#          riscv-lrsc-exp/NOSF-uc-bb-$insnBetween-o3-two-level-num-cpus-$cpu \
#          configs/riscv-sf-experiments/riscv_single_issue_o3_two_level_cache.py \
#          --num-cpus $simcpu --mem-size=8GB \
#          --cmd rv-sf-workloads/unconditional-threads-$cpu-bb-$insnBetween
#        done
#
#        # sleep 5 minutes. This should be sufficient
#        echo "SLEEPING FOR 5m 1"
#        sleep 5m
#        echo "WAKING UP 1"
#
#        # Conditional LR/SC with no retry
#        for insnBetween in 1 2 3 4; do
#          for insnExitPath in 1 2 4 8 12 16 20 50; do
#            python scripts/rv-sf-scripts/gen_riscv_lrsc.py --threads $cpu --iterations 5000 \
#              --conditional --between $insnBetween --retry-fail $insnExitPath --lr-fail-action exit \
#              --output rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath.cpp
#
#            ./scripts/rv-sf-scripts/compile.sh \
#              rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath
#
#            simcpu=$((cpu + 1))
#            for cbe in 1 4 8 12 16 20 50; do
#              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#                riscv-lrsc-exp/SF-cnr-bb-$insnBetween-eb-$insnExitPath-minor-one-level-cbe-$cbe-num-cpus-$cpu \
#                configs/riscv-sf-experiments/riscv_minor_one_level_cache.py \
#                --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
#                --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#
#              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#                riscv-lrsc-exp/SF-cnr-bb-$insnBetween-eb-$insnExitPath-minor-two-level-cbe-$cbe-num-cpus-$cpu \
#                configs/riscv-sf-experiments/riscv_minor_two_level_cache.py \
#                --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
#                --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#
#              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#                riscv-lrsc-exp/SF-cnr-bb-$insnBetween-eb-$insnExitPath-o3-one-level-cbe-$cbe-num-cpus-$cpu \
#                configs/riscv-sf-experiments/riscv_single_issue_o3_one_level_cache.py \
#                --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
#                --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#
#              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#                riscv-lrsc-exp/SF-cnr-bb-$insnBetween-eb-$insnExitPath-o3-two-level-cbe-$cbe-num-cpus-$cpu \
#                configs/riscv-sf-experiments/riscv_single_issue_o3_two_level_cache.py \
#                --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
#                --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#            done
#            for tbe in 1 2 4 8 10 10 20 50 80 100 150 200 300; do
#              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#                riscv-lrsc-exp/SF-cnr-bb-$insnBetween-eb-$insnExitPath-minor-one-level-tbe-$tbe-num-cpus-$cpu \
#                configs/riscv-sf-experiments/riscv_minor_one_level_cache.py \
#                --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
#                --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#
#              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#                riscv-lrsc-exp/SF-cnr-bb-$insnBetween-eb-$insnExitPath-minor-two-level-tbe-$tbe-num-cpus-$cpu \
#                configs/riscv-sf-experiments/riscv_minor_two_level_cache.py \
#                --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
#                --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#
#              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#                riscv-lrsc-exp/SF-cnr-bb-$insnBetween-eb-$insnExitPath-o3-one-level-tbe-$tbe-num-cpus-$cpu \
#                configs/riscv-sf-experiments/riscv_single_issue_o3_one_level_cache.py \
#                --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
#                --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#
#              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
#                riscv-lrsc-exp/SF-cnr-bb-$insnBetween-eb-$insnExitPath-o3-two-level-tbe-$tbe-num-cpus-$cpu \
#                configs/riscv-sf-experiments/riscv_single_issue_o3_two_level_cache.py \
#                --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
#                --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#            done
#            ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
#            riscv-lrsc-exp/NOSF-cnr-bb-$insnBetween-eb-$insnExitPath-minor-one-level-num-cpus-$cpu \
#            configs/riscv-sf-experiments/riscv_minor_one_level_cache.py \
#            --num-cpus $simcpu --mem-size=8GB \
#            --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#
#            ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
#            riscv-lrsc-exp/NOSF-cnr-bb-$insnBetween-eb-$insnExitPath-minor-two-level-num-cpus-$cpu \
#            configs/riscv-sf-experiments/riscv_minor_two_level_cache.py \
#            --num-cpus $simcpu --mem-size=8GB \
#            --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#
#            ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
#            riscv-lrsc-exp/NOSF-cnr-bb-$insnBetween-eb-$insnExitPath-o3-one-level-num-cpus-$cpu \
#            configs/riscv-sf-experiments/riscv_single_issue_o3_one_level_cache.py \
#            --num-cpus $simcpu --mem-size=8GB \
#            --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath &
#
#            ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
#            riscv-lrsc-exp/NOSF-cnr-bb-$insnBetween-eb-$insnExitPath-o3-two-level-num-cpus-$cpu \
#            configs/riscv-sf-experiments/riscv_single_issue_o3_two_level_cache.py \
#            --num-cpus $simcpu --mem-size=8GB \
#            --cmd rv-sf-workloads/conditional-no-retry-threads-$cpu-bb-$insnBetween-eb-$insnExitPath
#          done
#        done
#
#        echo "SLEEPING FOR 5m 2"
#        sleep 5m
#        echo "WAKING UP 2"
#
        # Conditional LR/SC with retry
        for insnBetween in 1 2 3 4; do
          for insnRetryPath in 1 2 4 8 12 16 20 50; do
            python scripts/rv-sf-scripts/gen_riscv_lrsc.py --threads $cpu --iterations 5000 \
              --conditional --between $insnBetween --retry-fail $insnRetryPath --lr-fail-action retry \
            --output rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath.cpp

            ./scripts/rv-sf-scripts/compile.sh \
              rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath

            simcpu=$((cpu + 1))
            for cbe in 1 4 8 12 16 20 50; do
              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
                riscv-lrsc-exp/SF-cr-bb-$insnBetween-rb-$insnRetryPath-minor-one-level-cbe-$cbe-num-cpus-$cpu \
                configs/riscv-sf-experiments/riscv_minor_one_level_cache.py \
                --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
                --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &

              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
                riscv-lrsc-exp/SF-cr-bb-$insnBetween-rb-$insnRetryPath-minor-two-level-cbe-$cbe-num-cpus-$cpu \
                configs/riscv-sf-experiments/riscv_minor_two_level_cache.py \
                --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
                --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &

              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
                riscv-lrsc-exp/SF-cr-bb-$insnBetween-rb-$insnRetryPath-o3-one-level-cbe-$cbe-num-cpus-$cpu \
                configs/riscv-sf-experiments/riscv_single_issue_o3_one_level_cache.py \
                --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
                --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &

              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
                riscv-lrsc-exp/SF-cr-bb-$insnBetween-rb-$insnRetryPath-o3-two-level-cbe-$cbe-num-cpus-$cpu \
                configs/riscv-sf-experiments/riscv_single_issue_o3_two_level_cache.py \
                --cbe-insn-count-limit $cbe --num-cpus $simcpu --mem-size=8GB \
                --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &
            done
            for tbe in 1 2 4 8 10 10 20 50 80 100 150 200 300; do
              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
                riscv-lrsc-exp/SF-cr-bb-$insnBetween-rb-$insnRetryPath-minor-one-level-tbe-$tbe-num-cpus-$cpu \
                configs/riscv-sf-experiments/riscv_minor_one_level_cache.py \
                --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
                --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &

              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
                riscv-lrsc-exp/SF-cr-bb-$insnBetween-rb-$insnRetryPath-minor-two-level-tbe-$tbe-num-cpus-$cpu \
                configs/riscv-sf-experiments/riscv_minor_two_level_cache.py \
                --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
                --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &

              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
                riscv-lrsc-exp/SF-cr-bb-$insnBetween-rb-$insnRetryPath-o3-one-level-tbe-$tbe-num-cpus-$cpu \
                configs/riscv-sf-experiments/riscv_single_issue_o3_one_level_cache.py \
                --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
                --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &

              ./build/RISCV_NoRuby_SF/gem5.opt -r -d \
                riscv-lrsc-exp/SF-cr-bb-$insnBetween-rb-$insnRetryPath-o3-two-level-tbe-$tbe-num-cpus-$cpu \
                configs/riscv-sf-experiments/riscv_single_issue_o3_two_level_cache.py \
                --tbe-cycle-limit $tbe --num-cpus $simcpu --mem-size=8GB \
                --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &
            done
            ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
            riscv-lrsc-exp/NOSF-cr-bb-$insnBetween-rb-$insnRetryPath-minor-one-level-num-cpus-$cpu \
            configs/riscv-sf-experiments/riscv_minor_one_level_cache.py \
            --num-cpus $simcpu --mem-size=8GB \
            --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &

            ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
            riscv-lrsc-exp/NOSF-cr-bb-$insnBetween-rb-$insnRetryPath-minor-two-level-num-cpus-$cpu \
            configs/riscv-sf-experiments/riscv_minor_two_level_cache.py \
            --num-cpus $simcpu --mem-size=8GB \
            --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &

            ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
            riscv-lrsc-exp/NOSF-cr-bb-$insnBetween-rb-$insnRetryPath-o3-one-level-num-cpus-$cpu \
            configs/riscv-sf-experiments/riscv_single_issue_o3_one_level_cache.py \
            --num-cpus $simcpu --mem-size=8GB \
            --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath &

            ./build/RISCV_NoRuby_NoSF/gem5.opt -r -d \
            riscv-lrsc-exp/NOSF-cr-bb-$insnBetween-rb-$insnRetryPath-o3-two-level-num-cpus-$cpu \
            configs/riscv-sf-experiments/riscv_single_issue_o3_two_level_cache.py \
            --num-cpus $simcpu --mem-size=8GB \
            --cmd rv-sf-workloads/conditional-retry-threads-$cpu-bb-$insnBetween-rb-$insnRetryPath
          done
        done
        echo "SLEEPING FOR 5m 3"
        sleep 5m
        echo "WAKING UP 3"
      done
      ;;
    c)
      rm -rf rv-sf-workloads/
 esac
done
