#!/usr/bin/python3

import math
import random
import sys


def gen_enqueue_tl(lock, cid, ts):
    llcmd = str(ts) + " " + str(cid) + " R " + str(lock)
    sccmd = str(ts) + " " + str(cid) + " W " + str(lock)

    return [llcmd, sccmd]


def gen_acquire_tl(lock, cid, ts):
    cmdList = []
    acqcmd = str(ts) + " " + str(cid) + " R " + str(lock)
    cmdList.append(acqcmd)
    return cmdList


def gen_interference(cid, ts, cnt):
    cmdList = []
    for i in range(cnt):
        cmd = (
            str(ts)
            + " "
            + str(cid)
            + " W "
            + str(hex(i * 64 + cid * cnt * 64)[2:])
        )
        cmdList.append(cmd)
    return cmdList


def gen_critical_section_execution(cid, ts, cnt):
    cmdList = []
    for i in range(cnt):
        cmd = (
            str(ts)
            + " "
            + str(cid)
            + " W "
            + str(hex(i * 64 + cid * cnt * 64)[2:])
        )
        cmdList.append(cmd)
    return cmdList


def gen_release_detect(lock, cid, ts):
    # Release TL with interference
    cmdList = []
    rdcmd = str(ts) + " " + str(cid) + " R " + str(lock)
    cmdList.extend([rdcmd])

    return cmdList


def gen_release_tx(lock, cid, ts):
    # Release TL with interference
    cmdList = []
    wrcmd = str(ts) + " " + str(cid) + " W " + str(lock)
    cmdList.extend([wrcmd])

    return cmdList


def gen_spinning_interference(lock, cid, ts, repeatRange):
    cmdList = []
    cCnt = 16
    spin = [
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        [],
        [1],
        [1, 2],
        [1, 2, 3],
        [1, 2, 3, 4],
        [1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 5, 6, 7],
        [1, 2, 3, 4, 5, 6, 7, 8],
        [1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
    ]
    for repeat in range(repeatRange):
        for i in spin[cid]:
            rdcmd = str(ts) + " " + str(i) + " R " + str(lock)
            cmdList.extend([rdcmd])
        # ts = ts + 100

    return cmdList


def gen_lock_phases_tl(lock, cid, ts):
    csLength = 64
    cmdList = []
    spinningRange = 4000
    cCnt = 16
    if cid == 0:
        spinningRange = math.ceil((cid + 1) * 1.04 * 4000)
    else:
        spinningRange = math.ceil((cCnt - cid + 1) * 1.04 * 4000)
    cmdList.extend(gen_spinning_interference(lock, cid, ts, spinningRange))
    cmdList.extend(gen_acquire_tl(lock, cid, ts))
    cmdList.extend(gen_critical_section_execution(cid, ts, csLength))
    cmdList.extend(gen_release_detect(lock, cid, ts))
    cmdList.extend(gen_release_tx(lock, cid, ts))
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

    cmdList.extend(gen_lock_phases_tl(lock, 0, 5110))
    cmdList.extend(gen_interference(0, 180000, interferenceCnt * 5000))

    cmdList.extend(gen_lock_phases_tl(lock, 15, 200000))
    cmdList.extend(gen_interference(15, 400000, interferenceCnt * 4000))

    cmdList.extend(gen_lock_phases_tl(lock, 14, 500000))
    cmdList.extend(gen_interference(14, 500000, interferenceCnt * 3000))

    cmdList.extend(gen_lock_phases_tl(lock, 13, 800000))
    cmdList.extend(gen_interference(13, 1000000, interferenceCnt * 2000))

    cmdList.extend(gen_lock_phases_tl(lock, 12, 1200000))
    cmdList.extend(gen_interference(12, 1400000, interferenceCnt * 1000))

    cmdList.extend(gen_lock_phases_tl(lock, 11, 1500000))
    cmdList.extend(gen_interference(11, 1900000, interferenceCnt * 900))

    cmdList.extend(gen_lock_phases_tl(lock, 10, 2000000))
    cmdList.extend(gen_interference(10, 2000000, interferenceCnt * 800))

    cmdList.extend(gen_lock_phases_tl(lock, 9, 5000000))
    cmdList.extend(gen_interference(9, 5000000, interferenceCnt * 700))

    cmdList.extend(gen_lock_phases_tl(lock, 8, 6000000))
    cmdList.extend(gen_interference(8, 6000000, interferenceCnt * 600))

    cmdList.extend(gen_lock_phases_tl(lock, 7, 7000000))
    cmdList.extend(gen_interference(7, 7000000, interferenceCnt * 500))

    cmdList.extend(gen_lock_phases_tl(lock, 6, 8000000))
    cmdList.extend(gen_interference(6, 8000000, interferenceCnt * 500))

    cmdList.extend(gen_lock_phases_tl(lock, 5, 9000000))
    cmdList.extend(gen_interference(5, 9000000, interferenceCnt * 500))

    cmdList.extend(gen_lock_phases_tl(lock, 4, 10000000))
    cmdList.extend(gen_interference(4, 10000000, interferenceCnt * 400))

    cmdList.extend(gen_lock_phases_tl(lock, 3, 11000000))
    cmdList.extend(gen_interference(3, 11000000, interferenceCnt * 400))

    cmdList.extend(gen_lock_phases_tl(lock, 2, 12000000))
    cmdList.extend(gen_interference(2, 12000000, interferenceCnt * 300))

    cmdList.extend(gen_lock_phases_tl(lock, 1, 13000000))

    #   cmdList.extend(gen_interference(7, 14000000, interferenceCnt*180))
    #    cmdList.extend(gen_lock_phases_tl(lock, 8, 16000000))
    #    cmdList.extend(gen_interference(8, 16000000, interferenceCnt*180))
    #    cmdList.extend(gen_lock_phases_tl(lock, 9, 18000000))
    #    cmdList.extend(gen_interference(9, 18000000, interferenceCnt*180))
    #    cmdList.extend(gen_lock_phases_tl(lock, 10, 20000000))
    #    cmdList.extend(gen_interference(10, 20000000, interferenceCnt*180))
    #    cmdList.extend(gen_lock_phases_tl(lock, 11, 22000000))
    #    cmdList.extend(gen_interference(11, 22000000, interferenceCnt*180))
    #    cmdList.extend(gen_lock_phases_tl(lock, 12, 24000000))
    #    cmdList.extend(gen_interference(12, 24000000, interferenceCnt*180))
    #    cmdList.extend(gen_lock_phases_tl(lock, 13, 26000000))
    #    cmdList.extend(gen_interference(13, 26000000, interferenceCnt*180))
    #    cmdList.extend(gen_lock_phases_tl(lock, 14, 28000000))
    #    cmdList.extend(gen_interference(14, 28000000, interferenceCnt*180))
    #    cmdList.extend(gen_lock_phases_tl(lock, 15, 30000000))
    #
    #    cmdList.extend(gen_acquire_tl(lock, 0, 5110))
    #    cmdList.extend(gen_interference(0, 5500, interferenceCnt))
    #    cmdList.extend(["7000 1 R " + str(lock)])
    #    cmdList.extend(gen_release_detect(lock, 0, 135730))
    #    cmdList.extend(gen_release_tx(lock, 0, 137930))
    #
    #    cmdList.extend(gen_interference(0, 137930, interferenceCnt*80))
    #
    #    cmdList.extend(gen_lock_phases_tl(lock, 1, 138000))
    #
    #    cmdList.extend(gen_acquire_tl(lock, 1, 138000))
    #    cmdList.extend(gen_interference(1, 138000, interferenceCnt))
    #    cmdList.extend(["140000 2 R " + str(lock)])
    #    cmdList.extend(gen_release_detect(lock, 1, 392200))
    #    cmdList.extend(gen_release_tx(lock, 1, 394000))
    #
    #    cmdList.extend(gen_interference(1, 394000, interferenceCnt*80))
    #
    #    cmdList.extend(gen_acquire_tl(lock, 2, 394250))
    #    cmdList.extend(gen_interference(2, 394250, interferenceCnt))
    #    cmdList.extend(["397400 3 R " + str(lock)])
    #    cmdList.extend(gen_release_detect(lock, 2, 394250))
    #    cmdList.extend(gen_release_tx(lock, 2, 396550))
    #
    #    cmdList.extend(gen_interference(2, 396250, interferenceCnt*80))
    #
    #    cmdList.extend(gen_acquire_tl(lock, 3, 779000))
    #    cmdList.extend(gen_interference(3, 832000, interferenceCnt))
    #    cmdList.extend(["11397400 3 R " + str(lock)])
    #    cmdList.extend(gen_release_detect(lock, 3, 1122550))
    #    cmdList.extend(gen_release_tx(lock, 3, 1124850))
    #
    #    cmdList.extend(gen_interference(3, 1124850, interferenceCnt*80))
    #
    #    cmdList.extend(gen_acquire_tl(lock, 4, 1125000))
    #    cmdList.extend(gen_interference(4, 111488000, interferenceCnt))
    #    cmdList.extend(gen_release_detect(lock, 4, 1128440))
    #    cmdList.extend(gen_release_tx(lock, 4, 1131840))
    #
    #    cmdList.extend(gen_interference(4, 1132000, interferenceCnt*80))
    #
    #    cmdList.extend(gen_acquire_tl(lock, 5, 1132800))
    #    cmdList.extend(gen_interference(5, 112400000, interferenceCnt))
    #    cmdList.extend(gen_release_detect(lock, 5, 1133200))
    #    cmdList.extend(gen_release_tx(lock, 5, 1135800))
    #
    #    cmdList.extend(gen_interference(5, 1135800, interferenceCnt*80))
    #
    #    cmdList.extend(gen_acquire_tl(lock, 6, 1135800))
    #    cmdList.extend(gen_interference(6, 113300000, interferenceCnt))
    #    cmdList.extend(gen_release_detect(lock, 6, 1139000))
    #    cmdList.extend(gen_release_tx(lock, 6, 1142000))
    #
    #    cmdList.extend(gen_interference(6, 1142000, interferenceCnt*80))
    #
    #    cmdList.extend(gen_acquire_tl(lock, 7, 1145000))
    #    #cmdList.extend(gen_interference(7, 4300000, interferenceCnt))
    # cmdList.extend(gen_release(lock, 7, 43000))

    #    cmdList.extend(gen_interference(7, 43000, interferenceCnt*80))

    #    cmdList.extend(gen_contending_acq(lock, 8, 44600))
    #    cmdList.extend(gen_acquire_tl(lock, 8, 45600))
    #    #cmdList.extend(gen_interference(8, 5321000, interferenceCnt))
    #    cmdList.extend(gen_contending_acq(lock, 8, 46400))
    #    cmdList.extend(gen_release(lock, 8, 47100))
    #
    #    cmdList.extend(gen_interference(8, 47100, interferenceCnt*80))
    #
    #    cmdList.extend(gen_contending_acq(lock, 9, 49500))
    #    cmdList.extend(gen_acquire_tl(lock, 9, 50100))
    #    #cmdList.extend(gen_interference(9, 6474068, interferenceCnt))
    #    cmdList.extend(gen_contending_acq(lock, 9, 53300))
    #    cmdList.extend(gen_release(lock, 9, 54500))
    #
    #    cmdList.extend(gen_interference(9, 54500, interferenceCnt*80))
    #
    #    cmdList.extend(gen_contending_acq(lock, 10, 56300))
    #    cmdList.extend(gen_acquire_tl(lock, 10, 57700))
    #    #cmdList.extend(gen_interference(10, 7900000, interferenceCnt))
    #    cmdList.extend(gen_contending_acq(lock, 10, 60100))
    #    cmdList.extend(gen_release(lock, 10, 60820))
    #
    #    cmdList.extend(gen_interference(10, 60820, interferenceCnt*80))
    #
    #    cmdList.extend(gen_contending_acq(lock, 10, 63200))
    #    cmdList.extend(gen_acquire_tl(lock, 11, 66500))
    #    #cmdList.extend(gen_interference(11, 9380000, interferenceCnt))
    #    cmdList.extend(gen_contending_acq(lock, 11, 77300))
    #    cmdList.extend(gen_release(lock, 11, 77700))
    #
    #    cmdList.extend(gen_interference(11, 77700, interferenceCnt*80))
    #
    #    cmdList.extend(gen_contending_acq(lock, 12, 80300))
    #    cmdList.extend(gen_acquire_tl(lock, 12, 83300))
    #    #cmdList.extend(gen_interference(12, 11200000, interferenceCnt))
    #    cmdList.extend(gen_contending_acq(lock, 12, 94100))
    #    cmdList.extend(gen_release(lock, 12, 95500))
    #
    #    cmdList.extend(gen_interference(12, 95500, interferenceCnt*80))
    #
    #    cmdList.extend(gen_contending_acq(lock, 13, 98000))
    #    cmdList.extend(gen_acquire_tl(lock, 13, 99300))
    #    #cmdList.extend(gen_interference(13, 12858972, interferenceCnt))
    #    cmdList.extend(gen_contending_acq(lock, 13, 121800))
    #    cmdList.extend(gen_release(lock, 13, 123000))
    #
    #    cmdList.extend(gen_interference(13, 123000, interferenceCnt*80))
    #
    #    cmdList.extend(gen_contending_acq(lock, 14, 126000))
    #    cmdList.extend(gen_acquire_tl(lock, 14, 126000))
    #    #cmdList.extend(gen_interference(14, 15800000, interferenceCnt))
    #    cmdList.extend(gen_contending_acq(lock, 14, 149800))
    #    cmdList.extend(gen_release(lock, 14, 153000))
    #
    #    cmdList.extend(gen_interference(14, 153000, interferenceCnt*80))
    #
    #    cmdList.extend(gen_acquire_tl(lock, 15, 158000))
    #
    for i in cmdList:
        print(i)
    return


def gen_mcs():
    return


if __name__ == "__main__":
    # gen_mcs(sys.argv[1])
    gen_tl()
