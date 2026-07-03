#!/usr/bin/python3

import re
import sys
import pandas as pd

cnt = 0

def subParse(lock, line, log):
    global cnt
    startTimeCore = r"[0-9]+ [0-9]+"
    lockStartRe = " ([0-9]+) ([0-9]+) Seq Begin > \[0x" + str(lock) + ", line 0x" + str(lock) + "\] ([A-Z]+)" 
    lockEndRe = " ([0-9]+) ([0-9]+) Seq Done > \[0x" + str(lock) + ", line 0x" + str(lock) + "\] ([0-9]+) cycles" 
    l = re.search(str(lock), str(line))
    if (l):
        x = re.search(lockStartRe, str(line))
        y = re.search(lockEndRe, str(line))
        if (x):
            #print (x.group(1), x.group(2), x.group(3))
            #print (cnt)
            log[cnt] = {}
            log[cnt]['addr'] = lock
            log[cnt]['core'] = x.group(2)
            log[cnt]['start'] = x.group(1)
            log[cnt]['operation'] = x.group(3)
            #print (log)
            cnt = cnt + 1

        if (y):
            #print (y.group(1), y.group(2), y.group(3))
            #print (log)
            for c in range(cnt+1):
                if (log[c]['core'] == y.group(2) and \
                    'end' not in log[c]):
                    log[c]['end'] = y.group(1)
                    log[c]['total'] = y.group(3)
                    #print (log)
                    break

def parse(ptFile):
    log = {}
    with open(ptFile, 'r') as fp:
        lines = fp.readlines()
        for line in lines:
            cx = re.sub(r'\s+', ' ', str(line))
            for lock in ["ffaabc0", "1234000", "2345000", "3456000", "4567000", "5678000", "6789000", "789a000", "89ab000", "9abc000", "abcd000", "bcde000", "cdef000", "def1000", "ef12000", "f123000", "fabcd00"]:
                subParse(lock, cx, log)

    print (log)
    df = pd.DataFrame.from_dict(log)
    print (df.T.to_string())

if __name__ == "__main__":
    parse(sys.argv[1])
