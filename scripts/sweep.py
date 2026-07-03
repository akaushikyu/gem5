#!/usr/bin/python3
from multiprocessing import Pool
import tqdm
import subprocess
import sys

def generateCmdEXCL(config, gem5exe, outputDirRoot):
    output_dir = str(outputDirRoot) + "/" + str(gem5exe) + "-" + \
                 str(config['numCores']) + "-" + str(config['numCCores']) + "-" + \
                 str(config['numXCores']) + "-" + str(config['numOps']) + "-" + \
                 str(config['numLocks']) + "-" + str(config['acqLock']) + "-" + \
                 str(config['clAccess']) + "-" + str(config['lockDelay'])
    output_log = output_dir + ".log"

    binOpts = "-n "+str(config['numCCores'])+ " -x " + str(config['numXCores']) + \
              " -d "+str(config['numOps']) + " -l "+\
                str(config['numLocks']) + " -a " + str(config['acqLock']) + " -c " + \
                str(config['clAccess']) + " -p " + str(config['lockDelay']) + " -w1"

    cmd = "build/" + str(gem5exe) + "/gem5.fast -d " + str(output_dir) +\
            " configs/deprecated/example/se.py --ruby --num-cpus " + \
            str(config['numCores']) + " --cpu-type TimingSimpleCPU " + \
                    "--l1d_size 512B --l1i_size 512B --l2_size 8kB " + \
                    "--mem-type SimpleMemory --mem-size 8GB " + \
                    "-c /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs" + \
                    " --options=\"" + str(binOpts) + "\" &> " + str(output_log) + "\n" + \
                    " mv log.csv " + str(output_log) + ".csv"
    return (cmd, config)

def generateCmdZIV(config, gem5exe, outputDirRoot):
    output_dir = str(outputDirRoot) + "/" + str(gem5exe) + "-" + \
                 str(config['numCores']) + "-" + str(config['numCCores']) + "-" + \
                 str(config['numXCores']) + "-" + str(config['numOps']) + "-" + \
                 str(config['numLocks']) + "-" + str(config['acqLock']) + "-" + \
                 str(config['clAccess']) + "-" + str(config['lockDelay'])
    output_log = output_dir + ".log"

    binOpts = "-n "+str(config['numCCores'])+ " -x "+str(config['numXCores']) + \
            " -d "+str(config['numOps']) + " -l "+\
                str(config['numLocks']) + " -a " + str(config['acqLock']) + " -c " + \
                str(config['clAccess']) + " -p " + str(config['lockDelay']) + " -w1"

    if (gem5exe == "RISCV_LC_MSI_ql"):
        configFile = "simple_ruby_ql.py"
    else:
        configFile = "simple_ruby.py"

    cmd = "build/" + str(gem5exe) + "/gem5.fast -d " + str(output_dir) +\
            " configs/xyz/" + configFile + " --l1-size 512B --l1-assoc 2 " +\
            "--l2-size 1024B --l2-assoc 4 --l3-assoc 8 l3-size 16kB --ncore " + \
            str(config['numCores']) + " --use-ziv --use-vi --wc" + \
            " --program /home/kaushika/REPOS/workloads/libslock-modif/measure_blocking_mcs" + \
            " --args=\"" + str(binOpts) + "\" &> " + str(output_log) + "\n" + \
                    " mv log.csv " + str(output_log) + ".csv"
    return (cmd, config)

def call_proc(args):
    cmd, config = args
    with open('run_log.txt', 'w') as fp:
        p = subprocess.Popen(cmd, shell=True, executable='/bin/bash', stdout=fp, stderr=subprocess.STDOUT, cwd=".")
        p.communicate(timeout=3600*12*10)
        return (config, p.returncode)

def run(output_dir):
    num_cores = [4, 8, 12, 16]
    num_ops = [10000]#, 50000, 100000, 500000, 1000000]
    num_locks = [1, 4, 8, 16]
    acq_lock = [0]#, 20, 50, 100]
    cl_access = [1000]#8, 32]#, 128]
    lock_delay = [0]#, 20]#, 50, 100]

    config = {}
    cmdList = []
    for nc in num_cores:
        for no in num_ops:
            for nl in num_locks:
                for al in acq_lock:
                    for ca in cl_access:
                        for ld in lock_delay:
                            n = nc
                            if (nc == 4):
                                n = 2
                                nx = 1
                            if (nc == 8):
                                n = 5
                                nx = 2
                            if (nc == 12):
                                n = 8
                                nx = 3
                            if (nc == 16):
                                n = 10
                                nx = 5
                            config = {'numCores': nc, 
                                      'numCCores': n,
                                      'numXCores': nx,
                                      'numOps' : no,
                                      'numLocks' : nl,
                                      'acqLock' : al,
                                      'clAccess' : ca,
                                      'lockDelay' : ld}
                            for gem5 in ['RISCV_EXCL']:#, 'RISCV_EXCL_ql']: 
                                cmdList.append(generateCmdEXCL(config, gem5, output_dir))
                            for gem5 in ['RISCV_LC_MSI']:#, 'RISCV_LC_MSI_ql']:
                                cmdList.append(generateCmdZIV(config, gem5, output_dir))

    for i in cmdList:
        print (i[0])
    #pool = Pool(1)
    #results = list(tqdm.tqdm(pool.imap_unordered(call_proc, cmdList), total=len(cmdList)))
    #pool.close()
    #pool.join()

    failure = 0
    failed_configs = []
    for config, retcode in results:
        if retcode != 0:
            failed_configs.append((config, retcode))
    print(f"Run completes: {len(cmdList) - len(failed_configs)} out of {len(cmdList)} passes")
    if failed_configs:
        print("Failed experiments:")
        for config, retcode in failed_configs:
            print(f"{config}: retcode {retcode}")
    

if __name__ == "__main__":
    run(sys.argv[1]) 
