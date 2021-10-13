#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A wrapper for cargo bench
Its numeric output is parsed and dumped to a csv
Pass an an optional independent variable from the command line
And also any other static keys and values

USAGE: python aggregate.py [independent variable]
Writes to measurements.csv in the cwd by default, pass a different filepath to alter this
any other keyword arguments will be written as a header row and value. Be careful with that.

(C) Stephan Hügel 2016
License: MIT

Original: https://github.com/urschrei/lonlat_bng/blob/master/aggregate_bench.py
Adapted by: Natalie Popescu 2020
"""
import os
import sys
from subprocess import check_output
import re
import argparse

default_type = 1

def dump_benchmark(
    filepath,
    unmod,
    regex,
    bench_type,
    headers=['#','bench-name','unmod-time', 'unmod-error','regex-time','regex-error'],
    **kwargs):
    """
    Customise with your own output path and header row.
    idep_var is an optional independent variable.
    """
    if bench_type == 0:
        pattern = "bench:\s+([0-9,]*)\D+([0-9,]*)"
        name_pattern = "(?<=test\s).*(?=\s+[.]{3}\s+bench)"
    else: 
        #pattern = "time:\s+\[([0-9,.]+)\s[a-z]s\s+([0-9,.]+)\s[a-z]s\s+([0-9,.]+)\s[a-z]s\]"
        pattern = "time:\s+\[([0-9,.]+)\s[a-z]+s\s+([0-9,.]+)\s[a-z]+s\s+([0-9,.]+)\s[a-z]+s\]"
        name_pattern = "(?<=Analyzing\n).+(?=\s+time)"

    # capture benchmark output
    bnames = re.findall(name_pattern, check_output(["cat", unmod]).decode('utf-8'))
    unmod_result = re.findall(pattern, check_output(["cat", unmod]).decode('utf-8'))
    regex_result = re.findall(pattern, check_output(["cat", regex]).decode('utf-8'))
    print(bnames)
    print()
    print(unmod_result)
    print(regex_result)
    # get rid of nasty commas
    output = []
    unmod_len = len(unmod_result)
    regex_len = len(regex_result)
    length = unmod_len if unmod_len < regex_len else regex_len
    print(length)
    for i in range(length):
        line = []
        # grab and append benchmark name to line
        bname = re.sub("\s", "_", bnames[i].strip())
        line.append(bname)
        # grab each matched line
        unmod_line = unmod_result[i]
        regex_line = regex_result[i]
        if bench_type == 0:
            # grab each of the two numbers per line
            for num in unmod_line:
                tnum = num.translate({ord(','): None})
                line.append(tnum)
            for num in regex_line:
                tnum = num.translate({ord(','): None})
                line.append(tnum)
        else: 
            # three number per line; middle is the best estimate
            unmod_mid = unmod_line[1]
            regex_mid = regex_line[1]
            # other two numbers we take the avg of diff -> error
            u_lo = float(unmod_mid) - float(unmod_line[0])
            u_hi = float(unmod_line[2]) - float(unmod_mid)
            unmod_err = str((u_lo + u_hi) / 2)
            b_lo = float(regex_mid) - float(regex_line[0])
            b_hi = float(regex_line[2]) - float(regex_mid)
            regex_err = str((b_lo + b_hi) / 2)
            # add to line
            line.append(unmod_mid)
            line.append(unmod_err)
            line.append(regex_mid)
            line.append(regex_err)
        output.append(line)
    # any other kwargs will be written as a CSV header row and value
    # nothing prevents you from writing rows that don't have a header
    for k, v in kwargs.items():
        headers.append(k),
        output.append(v)
    # check that path and file exist, or create them
    path_wrangle(filepath, headers)
    # write data to the file
    with open(filepath, 'a') as handle:
        for elem in output:
            writerow(handle, elem)

def path_wrangle(filepath, headers):
    """ Check for or create path and output file
    There's no error handling, because noisy failure's probably a good thing
    """
    # check for or create directory path
    directory = os.path.split(filepath)[0]
    if not os.path.exists(directory):
            os.makedirs(directory)
    # regardless if file itself exists or not, want blank slate so:
    # create new or overwrite existing data
    with open(filepath, 'w') as newhandle:
        writerow(newhandle, headers)

def writerow(filehandle, array):
    """ Write the contents of the array as a white-space
    delimited row in the file
    """
    for elem in array:
        filehandle.write(elem)
        filehandle.write("\t")
    filehandle.write("\n")

#def arg_parge():
#    parser = argparse.ArgumentParser()
#    parser.add_argument()

if __name__ == "__main__":
    # So brittle. Shhh.
    filepath = "./bench.data"
    unmod = "./UNMOD.bench"
    regex = "./REGEX.bench"
    # 0 == bencher; 1 == criterion
    bench_type = default_type
    if len(sys.argv) == 5:
        filepath = sys.argv[1]
        unmod = sys.argv[2]
        regex = sys.argv[3]
        bench_type = sys.argv[4]
    else: 
        print("Wrong number of arguments")
        quit()

    dump_benchmark(
            filepath=filepath,
            unmod=unmod,
            regex=regex,
            bench_type=bench_type
            )
