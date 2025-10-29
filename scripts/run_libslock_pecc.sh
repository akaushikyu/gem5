#!/bin/bash

#/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_INCL/gem5.opt --debug-flags=Ruby /home/kaushika/REPOS/yu-gem5/gem5//configs/deprecated/example/se.py --ruby --num-cpus 16 --cpu-type TimingSimpleCPU --l1d_size 16kB --l1i_size 16kB --l2_size 256kB --mem-type SimpleMemory --mem-size 2GB -c /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --options='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv pecc-INCL.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_EXCL/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/deprecated/example/se.py --ruby --num-cpus 16 --cpu-type TimingSimpleCPU --l1d_size 16kB --l1i_size 16kB --l2_size 256kB --mem-type SimpleMemory --mem-size 2GB -c /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --options='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
mv log.csv pecc-EXCL.csv
