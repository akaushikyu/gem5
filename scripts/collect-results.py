#!/usr/bin/python3

import numpy as np
import pandas as pd
import sys
import os
from pathlib import Path
import re

def collectResults (topDir, config):
    resultsMap = {}
    p = Path(topDir) 
    files = str(config) + '*/stats.txt'
    statsFiles = p.glob(files)
    tickRe = ".*finalTick.* ([0-9]+).*"
    fileRe = "(RISCV_EXCL|RISCV_EXCL_ql)-([0-9]+-[0-9]+-[0-9]+-[0-9]+-[0-9]+)"
    for s in statsFiles:
        y = re.search(fileRe, str(s))
        ss = str(s).split('/')
        with open(s, 'r') as fp:
            for line in enumerate(fp):
                if 'finalTick' in str(line):
                    x = re.search(tickRe, str(line))
                    resultsMap[y.group(2)] = x.group(1)

    return resultsMap
if __name__ == "__main__":
    resultsExcl = collectResults(sys.argv[1], "RISCV_EXCL")
    resultsExclQl = collectResults(sys.argv[1], "RISCV_EXCL_ql")

    dfExcl = pd.DataFrame.from_dict(resultsExcl, orient='index')
    dfExclQl = pd.DataFrame.from_dict(resultsExclQl, orient='index')

    dfExcl.columns = ['excl']
    dfExclQl.columns = ['exclQl']

    result = pd.merge(dfExcl, dfExclQl, left_index=True, right_index=True)

    result['speedup'] = result['excl'].astype(int)/result['exclQl'].astype(int)

    #print (result)
    print(result.sort_values(by=['speedup'], ascending=False).to_string())
    


