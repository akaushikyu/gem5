#!/bin/bash

#/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 1024kB --ncore 8 --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_tl --args='-n 7 -d 5000 -l 1 -c 20 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_ticket.csv

#/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-seq-normal.csv

## BEGIN DEADLOCK SCENARIOS ##
#/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --wc --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-seq-wc.csv

#/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --wc --subslot-opt --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-seq-wc-subslot.csv

#/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --wc --subslot-opt --split-bus --wb-buffer-size 128 --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-seq-splitbus.csv

## END DEADLOCK SCENARIOS ##

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --use-ziv --use-vi --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-xyz-normal.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --use-ziv --use-vi --wc --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-xyz-wc.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --use-ziv --use-vi --wc --subslot-opt --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-xyz-subslot.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --use-ziv --use-vi --wc --subslot-opt --split-bus --wb-buffer-size 128 --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-xyz-splitbus.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --use-ziv --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-ziv-normal.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --use-ziv --wc --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-ziv-wc.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --use-ziv --wc --subslot-opt --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-ziv-subslot.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --use-ziv --wc --subslot-opt --split-bus --wb-buffer-size 128 --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-ziv-splitbus.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --disable-roc --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-gp-normal.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --disable-roc --wc --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-gp-wc.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --disable-roc --wc --subslot-opt --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-gp-subslot.csv

/home/kaushika/REPOS/yu-gem5/gem5//build/RISCV_LC_MSI/gem5.opt /home/kaushika/REPOS/yu-gem5/gem5//configs/xyz/simple_ruby.py --l1-size 16kB --l1-assoc 2 --l2-size 32kB --l2-assoc 4 --l3-assoc 8 --l3-size 512kB --ncore 16 --disable-roc --wc --subslot-opt --split-bus --wb-buffer-size 128 --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --args='-n 15 -d 5000 -l 1 -c 200 -p 0 -w 1'
#mv log.csv zcllc_linear_pmsi_mcs-gp-splitbus.csv

