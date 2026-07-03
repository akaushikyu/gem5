#!/usr/bin/python3

import random
import sys

def gen_enqueue_mcs(glock, llock, cid, ts, plock = None):
    llcmd = str(ts) + " " + str(cid) + " R " +  str(glock)
    sccmd = str(ts) + " " + str(cid) + " W " + str(glock)
    wrcmd = str(ts) + " " + str(cid) + " W " + str(llock)
    if (plock != None):
        wrcmdp = str(ts) + " " + str(cid) + " W " + str(plock)
        return ([llcmd, sccmd, wrcmd, wrcmdp])
 
    return ([llcmd, sccmd, wrcmd])


def gen_acquire_mcs(lock, cid, ts):
    acqcmd = str(ts) + " " + str(cid) + " R " + str(lock)

    return [acqcmd]

def gen_reference(cid, ts, cnt):
    cmdList = []
    for i in range(cnt):
        cmd = str(ts) + " " + str(cid) + " W " + str(hex(i*64 + cid*cnt*64)[2:])
        cmdList.append(cmd)
    return cmdList

def gen_release(llock, nlock, cid, ts):
    # Release TL with erence
    cmdList = []
    rdcmd = str(ts) + " " + str(cid) + " R " + str(llock)
    cmdList.extend([rdcmd])
    wrcmd = str(ts) + " " + str(cid) + " W " + str(nlock)
    cmdList.extend([wrcmd])

    return cmdList

def gen_mcs():
    
    interferenceCnt = 512
    ####
    # W.C scenario
    # Acq by i
    # 1 0 W 8000
    # 1 0 R 8000
    # < Interference that evicts 8000 from 0 >
    # Rel by i
    # 1 0 R 8000
    # < Interference that evicts 8000 from 0 >
    # 1 0 W 8000
    # Repeat
    ####
    lock = "FFAABC0"
    lock0 = "1234000" 
    lock1 = "2345000"
    lock2 = "3456000"
    lock3 = "4567000"
    lock4 = "5678000"
    lock5 = "6789000"
    lock6 = "789A000"
    lock7 = "89AB000"
    lock8 = "9ABC000"
    lock9 = "ABCD000"
    lock10 = "BCDE000"
    lock11 = "CDEF000"
    lock12 = "DEF1000"
    lock13 = "EF12000"
    lock14 = "F123000"
    lock15 = "FABCD00"

    cmdList = []

    cmdList.extend(gen_enqueue_mcs(lock, lock0, 0, 1))
    cmdList.extend(gen_enqueue_mcs(lock, lock1, 1, 1, lock0))
    cmdList.extend(gen_enqueue_mcs(lock, lock2, 2, 1, lock1))
    cmdList.extend(gen_enqueue_mcs(lock, lock3, 3, 1, lock2))
    #cmdList.extend(gen_enqueue_mcs(lock, lock4, 4, 1, lock3))
    #cmdList.extend(gen_enqueue_mcs(lock, lock5, 5, 1, lock4))
    #cmdList.extend(gen_enqueue_mcs(lock, lock6, 6, 1, lock5))
    #cmdList.extend(gen_enqueue_mcs(lock, lock7, 7, 1, lock6))
    #cmdList.extend(gen_enqueue_mcs(lock, lock8, 8, 1, lock7))
    #cmdList.extend(gen_enqueue_mcs(lock, lock9, 9, 1, lock8))
    #cmdList.extend(gen_enqueue_mcs(lock, lock10, 10, 1, lock9))
    #cmdList.extend(gen_enqueue_mcs(lock, lock11, 11, 1, lock10))
    #cmdList.extend(gen_enqueue_mcs(lock, lock12, 12, 1, lock11))
    #cmdList.extend(gen_enqueue_mcs(lock, lock13, 13, 1, lock12))
    #cmdList.extend(gen_enqueue_mcs(lock, lock14, 14, 1, lock13))
    #cmdList.extend(gen_enqueue_mcs(lock, lock15, 15, 1, lock14))

    cmdList.extend(gen_acquire_mcs(lock0, 0, 1))
    cmdList.extend(gen_acquire_mcs(lock0, 1, 1))
    cmdList.extend(gen_acquire_mcs(lock0, 2, 1))
    cmdList.extend(gen_acquire_mcs(lock0, 3, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 4, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 5, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 6, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 7, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 8, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 9, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 10, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 11, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 12, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 13, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 14, 1))
    #cmdList.extend(gen_acquire_mcs(lock0, 15, 1))

    cmdList.extend(gen_reference(0, 1, interferenceCnt))
    cmdList.extend(gen_release(lock0, lock1, 0,5000))

    cmdList.extend(gen_reference(0, 5000, interferenceCnt*50))
    cmdList.extend(gen_acquire_mcs(lock1, 1, 271500))
    cmdList.extend(gen_reference(1, 271500, interferenceCnt))
    cmdList.extend(gen_release(lock1, lock2, 1, 271500))

    cmdList.extend(gen_reference(1, 271500, interferenceCnt*50))
    cmdList.extend(gen_acquire_mcs(lock2, 2, 527000))
    cmdList.extend(gen_reference(2, 527000, interferenceCnt))
    cmdList.extend(gen_release(lock2, lock3, 2, 527000))

    cmdList.extend(gen_reference(2, 527000, interferenceCnt*50)) 
    cmdList.extend(gen_acquire_mcs(lock3, 3, 911000))
    #cmdList.extend(gen_reference(3, 911000, interferenceCnt))
    #cmdList.extend(gen_release(lock3, lock4, 3, 911000))

    #cmdList.extend(gen_reference(3, 911000, interferenceCnt*50)) 
    #cmdList.extend(gen_acquire_mcs(lock4, 4, 1422000))
    #cmdList.extend(gen_reference(4, 1422000, interferenceCnt))
    #cmdList.extend(gen_release(lock4, lock5, 4, 1422000))

    #cmdList.extend(gen_reference(4, 1422000, interferenceCnt*50)) 
    #cmdList.extend(gen_acquire_mcs(lock5, 5, 2062000))
    #cmdList.extend(gen_reference(5, 2062000, interferenceCnt))
    #cmdList.extend(gen_release(lock5, lock6, 5, 2062000))

    #cmdList.extend(gen_reference(5, 2062000, interferenceCnt*50)) 
    #cmdList.extend(gen_acquire_mcs(lock6, 6, 2830000))
    #cmdList.extend(gen_reference(6, 2830000, interferenceCnt))
    #cmdList.extend(gen_release(lock6, lock7, 6, 2830000))

    #cmdList.extend(gen_reference(6, 2830000, interferenceCnt*50)) 
    #cmdList.extend(gen_acquire_mcs(lock7, 7, 3730435))
    #cmdList.extend(gen_reference(7, 3730435, interferenceCnt))
    #cmdList.extend(gen_release(lock7, lock8, 7, 3730435)) 
#
#    cmdList.extend(gen_reference(7, 3730435, interferenceCnt*50)) 
#    cmdList.extend(gen_acquire_mcs(lock8, 8, 4753583))
#    cmdList.extend(gen_reference(8, 4753583, interferenceCnt))
#    cmdList.extend(gen_release(lock8, lock9, 8, 4753583)) 
#
#    cmdList.extend(gen_reference(8, 4753583, interferenceCnt*50)) 
#    cmdList.extend(gen_acquire_mcs(lock9, 9, 5923003))
#    cmdList.extend(gen_reference(9, 5923003, interferenceCnt))
#    cmdList.extend(gen_release(lock9, lock10, 9, 5923003)) 
#
#    cmdList.extend(gen_reference(9, 5923003, interferenceCnt*50)) 
#    cmdList.extend(gen_acquire_mcs(lock10, 10, 8005280))
#    cmdList.extend(gen_reference(10, 8005280, interferenceCnt))
#    cmdList.extend(gen_release(lock10, lock11, 10, 8005280)) 
#
#    cmdList.extend(gen_reference(10, 8005280, interferenceCnt*50)) 
#    cmdList.extend(gen_acquire_mcs(lock11, 11, 9415331))
#    cmdList.extend(gen_reference(11, 9415331, interferenceCnt))
#    cmdList.extend(gen_release(lock11, lock12, 11, 9415331)) 
#
#    cmdList.extend(gen_reference(11, 9415331, interferenceCnt*50)) 
#    cmdList.extend(gen_acquire_mcs(lock12, 12, 11000000))
#    cmdList.extend(gen_reference(12, 11000000, interferenceCnt))
#    cmdList.extend(gen_release(lock12, lock13, 12, 11000000)) 
#
#    cmdList.extend(gen_reference(12, 11000000, interferenceCnt*50)) 
#    cmdList.extend(gen_acquire_mcs(lock13, 13, 20821000))
#    cmdList.extend(gen_reference(13, 20821000, interferenceCnt))
#    cmdList.extend(gen_release(lock13, lock14, 13, 20821000)) 
#
#    cmdList.extend(gen_reference(13, 20821000, interferenceCnt*50)) 
#    cmdList.extend(gen_acquire_mcs(lock14, 14, 22620051))
#    cmdList.extend(gen_reference(14, 22620051, interferenceCnt))
#    cmdList.extend(gen_release(lock14, lock15, 14, 22620051)) 
#
#    cmdList.extend(gen_reference(14, 22610051, interferenceCnt*50)) 
#    cmdList.extend(gen_acquire_mcs(lock15, 15, 24536963))
#
    for i in cmdList:
        print (i)
    return

if __name__ == "__main__":
    gen_mcs()
