#!/usr/bin/python3

import random
import sys

def gen_enqueue_tl(lock, cid, ts):
    llcmd = str(ts) + " " + str(cid) + " R " +  str(lock)
    sccmd = str(ts) + " " + str(cid) + " W " + str(lock)
    
    return ([llcmd, sccmd])

def gen_acquire_tl(lock, cid, ts):
    acqcmd = str(ts) + " " + str(cid) + " R " + str(lock)

    return [acqcmd]

def gen_interference(cid, ts, cnt):
    cmdList = []
    for i in range(cnt):
        cmd = str(ts) + " " + str(cid) + " W " + str(hex(i*64 + cid*cnt*64)[2:])
        cmdList.append(cmd)
    return cmdList

def gen_release(lock, cid, ts):
    # Release TL with interference
    cmdList = []
    rdcmd = str(ts) + " " + str(cid) + " R " + str(lock)
    cmdList.extend([rdcmd])
    #cmdList.extend(gen_interference(cid, ts, 16))
    wrcmd = str(ts) + " " + str(cid) + " W " + str(lock)
    cmdList.extend([wrcmd])
    #cmdList.extend(gen_interference(cid, ts, 16))

    return cmdList

def gen_tl():
    
    interferenceCnt = 512
    ####
    # W.C scenario
    # Acq by i
    # 1 0 W 24000
    # 1 0 R 24000
    # < Interference that evicts 24000 from 0 >
    # Rel by i
    # 1 0 R 24000
    # < Interference that evicts 24000 from 0 >
    # 1 0 W 24000
    # Repeat
    ####
    lock = "DEADB000" 
    cmdList = []

    cmdList.extend(gen_enqueue_tl(lock, 0, 1))
    cmdList.extend(gen_enqueue_tl(lock, 1, 1))
    cmdList.extend(gen_enqueue_tl(lock, 2, 1))
    cmdList.extend(gen_enqueue_tl(lock, 3, 1))
    cmdList.extend(gen_enqueue_tl(lock, 4, 1))
    cmdList.extend(gen_enqueue_tl(lock, 5, 1))
    cmdList.extend(gen_enqueue_tl(lock, 6, 1))
    cmdList.extend(gen_enqueue_tl(lock, 7, 1))
    cmdList.extend(gen_enqueue_tl(lock, 8, 1))
    cmdList.extend(gen_enqueue_tl(lock, 9, 1))
    cmdList.extend(gen_enqueue_tl(lock, 10, 1))
    cmdList.extend(gen_enqueue_tl(lock, 11, 1))
    cmdList.extend(gen_enqueue_tl(lock, 12, 1))
    cmdList.extend(gen_enqueue_tl(lock, 13, 1))
    cmdList.extend(gen_enqueue_tl(lock, 14, 1))
    cmdList.extend(gen_enqueue_tl(lock, 15, 1))

    cmdList.extend(gen_acquire_tl(lock, 0, 1))
    cmdList.extend(gen_interference(0, 1, interferenceCnt))
    cmdList.extend(gen_release(lock, 0, 1))

    cmdList.extend(gen_interference(0, 1, interferenceCnt*80))

    cmdList.extend(gen_acquire_tl(lock, 1, 153000))
    cmdList.extend(gen_interference(1, 153000, interferenceCnt))
    cmdList.extend(gen_release(lock, 1, 153000))

    cmdList.extend(gen_interference(1, 153000, interferenceCnt*80))

    cmdList.extend(gen_acquire_tl(lock, 2, 420000))
    cmdList.extend(gen_interference(2, 420000, interferenceCnt))
    cmdList.extend(gen_release(lock, 2, 420000))

    cmdList.extend(gen_interference(2, 420000, interferenceCnt*80)) 

    cmdList.extend(gen_acquire_tl(lock, 3, 832000))
    cmdList.extend(gen_interference(3, 832000, interferenceCnt))
    cmdList.extend(gen_release(lock, 3, 832000))

    cmdList.extend(gen_interference(3, 832000, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 4, 1488000))
    cmdList.extend(gen_interference(4, 1488000, interferenceCnt))
    cmdList.extend(gen_release(lock, 4, 1488000))

    cmdList.extend(gen_interference(4, 1488000, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 5, 2400000))
    cmdList.extend(gen_interference(5, 2400000, interferenceCnt))
    cmdList.extend(gen_release(lock, 5, 2400000))

    cmdList.extend(gen_interference(5, 2400000, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 6, 3300000))
    cmdList.extend(gen_interference(6, 3300000, interferenceCnt))
    cmdList.extend(gen_release(lock, 6, 3300000))

    cmdList.extend(gen_interference(6, 3300000, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 7, 4300000))
    cmdList.extend(gen_interference(7, 4300000, interferenceCnt))
    cmdList.extend(gen_release(lock, 7, 4300000))

    cmdList.extend(gen_interference(7, 4300000, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 8, 5321000))
    cmdList.extend(gen_interference(8, 5321000, interferenceCnt))
    cmdList.extend(gen_release(lock, 8, 5321000))

    cmdList.extend(gen_interference(8, 5321000, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 9, 6474068))
    cmdList.extend(gen_interference(9, 6474068, interferenceCnt))
    cmdList.extend(gen_release(lock, 9, 6474068))

    cmdList.extend(gen_interference(9, 6474068, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 10, 7900000))
    cmdList.extend(gen_interference(10, 7900000, interferenceCnt))
    cmdList.extend(gen_release(lock, 10, 7900000))

    cmdList.extend(gen_interference(10, 7900000, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 11, 9380000))
    cmdList.extend(gen_interference(11, 9380000, interferenceCnt))
    cmdList.extend(gen_release(lock, 11, 9380000))

    cmdList.extend(gen_interference(11, 9380000, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 12, 11200000))
    cmdList.extend(gen_interference(12, 11200000, interferenceCnt))
    cmdList.extend(gen_release(lock, 12, 11200000))

    cmdList.extend(gen_interference(12, 11200000, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 13, 12858972))
    cmdList.extend(gen_interference(13, 12858972, interferenceCnt))
    cmdList.extend(gen_release(lock, 13, 12858972))

    cmdList.extend(gen_interference(13, 12858972, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 14, 15800000))
    cmdList.extend(gen_interference(14, 15800000, interferenceCnt))
    cmdList.extend(gen_release(lock, 14, 15800000))

    cmdList.extend(gen_interference(14, 158000000, interferenceCnt*80)) 
    cmdList.extend(gen_acquire_tl(lock, 15, 17714084))

    for i in cmdList:
        print (i)
    return

def gen_mcs():
    return

if __name__ == "__main__":
    #gen_mcs(sys.argv[1])
    gen_tl()
