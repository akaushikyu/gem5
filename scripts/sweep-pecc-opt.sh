#!/bin/bash

for num_cores in 4 8 12 16 
do
  num_sim_cores=$((num_cores-1))
  for num_ops in 5000 10000 50000 100000 500000 
  do
    for num_locks in 1 4 8 16 
    do
      for acq_lock in 0 20 50 100 
      do
        for cl_access in 8 32 128 
        do
          for lock_delay in 0 20 50 100 
          do
            output_dir_excl="results-ql-new/excl-${num_cores}-${num_ops}-${num_locks}-${acq_lock}-${cl_access}-${lock_delay}"
            output_dir_excl_log="results-ql-new/excl-${num_cores}-${num_ops}-${num_locks}-${acq_lock}-${cl_access}-${lock_delay}.log"
            output_dir_excl_ql="results-ql-new/exclql-${num_cores}-${num_ops}-${num_locks}-${acq_lock}-${cl_access}-${lock_delay}"
            output_dir_excl_ql_log="results-ql-new/exclql-${num_cores}-${num_ops}-${num_locks}-${acq_lock}-${cl_access}-${lock_delay}.log"
            options="'-n${num_sim_cores} -d ${num_ops} -l ${num_locks} -a ${acq_lock} -c ${cl_access} -p ${lock_delay} -w 1'"
            optionsStr=`echo ${options}`
            echo ${optionsStr}
            qlcmd=`echo "./build/RISCV_EXCL_ql/gem5.fast  -d ${output_dir_excl_ql} configs/deprecated/example/se.py --ruby --num-cpus ${num_cores} --cpu-type TimingSimpleCPU --l1d_size 8kB --l1i_size 8kB --l2_size 256kB --mem-type SimpleMemory --mem-size 2GB -c /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --options=${optionsStr} &> ${output_dir_excl_ql_log} &"`
            eval " $qlcmd"
            echo "Done EXCL QL"
            cmd=`echo "./build/RISCV_EXCL/gem5.fast  -d ${output_dir_excl} configs/deprecated/example/se.py --ruby --num-cpus ${num_cores} --cpu-type TimingSimpleCPU --l1d_size 8kB --l1i_size 8kB --l2_size 256kB --mem-type SimpleMemory --mem-size 2GB -c /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs --options=${optionsStr} &> ${output_dir_excl_log}"`
            eval " $cmd"
            echo "Done EXCL"
          done
        done
      done
    done
  done
done
