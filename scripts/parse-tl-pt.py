#!/usr/bin/python3

import re
import sys
import pandas as pd

def parse(ptFile):
    lockLine = r"deadb000"
    startTimeCore = r"[0-9]+ [0-9]+"
    lockStartRe = r" ([0-9]+) ([0-9]+) Seq Begin > \[0xdeadb000, line 0xdeadb000\] ([A-Z]+)"
    lockEndRe = r" ([0-9]+) ([0-9]+) Seq Done > \[0xdeadb000, line 0xdeadb000\] ([0-9]+) cycles"

    log = {}
    cnt = 0
    with open(ptFile, 'r') as fp:
        lines = fp.readlines()
        for line in lines:
            cx = re.sub(r'\s+', ' ', str(line))
            l = re.search(lockLine, str(cx))
            if (l):
                x = re.search(lockStartRe, str(cx))
                y = re.search(lockEndRe, str(cx))
                if (x):
                    #print (x.group(1), x.group(2), x.group(3))
                    log[cnt] = {}
                    log[cnt]['core'] = x.group(2)
                    log[cnt]['start'] = x.group(1)
                    log[cnt]['operation'] = x.group(3)
                    cnt = cnt + 1

                if (y):
                    #print (y.group(1), y.group(2), y.group(3))
                    #print (log)
                    for c in range(cnt+1):
                        if (log[c]['core'] == y.group(2) and \
                                'end' not in log[c]):
                            log[c]['end'] = y.group(1)
                            log[c]['total'] = y.group(3)
                            break

    print (log)
    df = pd.DataFrame.from_dict(log)
    #df.T.to_csv("out.csv")
    print (df.T.to_string())


if __name__ == "__main__":
    parse(sys.argv[1])
