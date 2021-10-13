#!/usr/bin/env python

import os
import sys
import math
from subprocess import check_output
import numpy
import re
from aggregate import path_wrangle, writerow
from statistics import median

def stats2(array):
    list_arr = array.tolist()
    # drop two highest
    list_arr.remove(max(list_arr))
    list_arr.remove(max(list_arr))
    # drop two lowest
    list_arr.remove(min(list_arr))
    list_arr.remove(min(list_arr))
    # median calc
    med = median(list_arr)
    # standard deviation calc
    stdev = stddev(list_arr, average(list_arr))
    return med, stdev

def stats(array):
    # average calc
    avg = average(array)
    # standard deviation calc
    stdev = stddev(array, avg)
    return avg, stdev

def average(array):
    avg = 0
    t = 1
    for a in array:
        avg += (a - avg) / t
        t += 1
    return avg

def stddev(array, arr_avg):
    length = len(array)
    sqrs = []
    # squares of diffs
    for a in array:
        diff = arr_avg - a
        sqr = diff * diff
        sqrs.append(sqr)
    # average of squares of diffs
    sqrs_avg = average(sqrs)
    # square root
    res = math.sqrt(sqrs_avg)
    return res

def crunch(
    crate,
    data_file,
    data_file_loc,
    numnodes,
    numruns,
    ctgry):
    # Use same headers and will be using similar logic as "aggregate_bench.py" later on
    headers = ['#', 'bench-name', 'unmod-time', 'unmod-error', 'bcrm-time', 'bcrm-error']
    
    # Grab the numbers for each [benchmark x rustc] combo (per crate)
    base_file = "./downloaded_" + ctgry + "/" + crate + "/" + data_file_loc + "/" + data_file
    crunched_output = base_file + "-CRUNCHED.data"
    # Write headers
    path_wrangle(crunched_output, headers)

    # Each loop here represents a different .data file, meaning that
    # each loop iteration adds to all the arrays _once_ (one data point
    # per file); so the arrays we write to should be created outside of this
    # main processing loop
    get_names_file = base_file + "-0-1.data"

    totalruns = int(numnodes) * int(numruns)
    rows = len(open(get_names_file, 'r').readlines()) - 1
    cols = 2
    matrix = numpy.zeros((rows, cols, totalruns))

    get_names = True
    # Flag needed because bug in my regex for extracting benchmark names =>
    # creates an offset when process the numbers, leading program to try to parse
    # the actual benchmark name as a float (this bug only manifests sometimes, 
    # when there is only a single benchmark, don't know why)
    extra_name = False
    labels = []
    run = 0
    for i in range(int(numnodes)):
        for j in range(1, int(numruns) + 1):
            fd_data_file = base_file + "-" + str(i) + "-" + str(j) + ".data"
            fd_data = open(fd_data_file, 'r')

            row = 0
            for line in fd_data:
                # Skip header line
                if line[:1] == '#':
                    continue
                # Each line = results for one benchmark name/function run
                columns = line.split()
                col = 0
                for c in range(len(columns)):
                    if get_names == True and c == 0:
                        if columns[c] == "test":
                            extra_name = True
                            continue
                        else: 
                            labels.append(columns[c])
                    if extra_name == True and c == 1:
                        labels.append(columns[c])
                    # Collect numbers @ even columns (skipping first) if extra name column exists
                    if extra_name == True and c > 0 and c % 2 == 0:
                        elem = columns[c]
                        matrix[row][col][run] = elem
                        col += 1
                    # Otherwise collect numbers @ odd columns
                    elif extra_name == False and c % 2 == 1:
                        elem = columns[c]
                        matrix[row][col][run] = elem
                        col += 1
                row += 1
            get_names = False
            run += 1

    fd_crunched_output = open(crunched_output, 'a')
    # Now that we've populated our matrix, can start crunching numbers
    for r in range(rows):
        row = []
        label = labels[r]
        row.append(label)
        for c in range(cols):
            avg, stdev = stats(matrix[r][c])
            row.append(str(avg))
            row.append(str(stdev))
        writerow(fd_crunched_output, row)

# Called like: python3 "$CRUNCH" "$crate" "$FNAME" "$LOCAL_OUTPUT" "$numnodes" "$runs"
if __name__ == "__main__":
    if len(sys.argv) != 7: 
        sys.exit("Wrong number of arguments! Need 7.")
    crate = sys.argv[1]
    data_file_name = sys.argv[2]
    data_file_loc = sys.argv[3]
    numnodes = sys.argv[4]
    numruns = sys.argv[5]
    ctgry = sys.argv[6]

    # Get average and stddev across all nodes + runs
    crunch(
        crate=crate,
        data_file=data_file_name,
        data_file_loc=data_file_loc,
        numnodes=numnodes,
        numruns=numruns,
        ctgry=ctgry,
    )
