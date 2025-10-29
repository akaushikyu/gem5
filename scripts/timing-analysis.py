#!/usr/bin/python3
import pandas as pd
import numpy as np
import sys

def analyze(input_csv):
    df = pd.read_csv(input_csv, header=None, index_col=False, names=['Address', 'PC', 'IssueC', 'IssueT', 'CompleteC', 'CompleteT', 'Total', 'CID'])
    print (df)
    wct = df.loc[df['Total'].idxmax()]
    print (wct)

    df['Max'] = df.groupby('PC')['Total'].transform('max')

    cdf = df[['PC', 'Max']].copy().drop_duplicates()

    print (cdf)

if __name__ == "__main__":
    analyze(sys.argv[1]) 
