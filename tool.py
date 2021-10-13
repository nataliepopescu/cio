#!/usr/bin/env python

import os
import sys
import argparse
import subprocess
from make_patch import patchAll
import random
import datetime
from aggregate import dump_benchmark, path_wrangle, writerow
from crunch import stats2

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))
VENDOR_DIR = "vendor"
COMP_LOG = "compile.log"
RUN_LOG = "run.log"
UNSAFE_DIR = os.path.join(ROOT_PATH, "unsafe-crates")
SAFE_DIR = os.path.join(ROOT_PATH, "safe-crates")
EXP_DIRS = [UNSAFE_DIR, SAFE_DIR]
RESULT_DIR = os.path.join(ROOT_PATH, "results")
CRUNCHED = "crunched.data"

HEADERS = ['#', 'bench-name', 'unmod-time', 'unmod-error', 'regex-time', 'regex-error']

class CIO:

    def __init__(self, crates, rust_version, vendor, num_runs):
        self.rust_version = "mod" if rust_version == None else "nightly-{}".format(rust_version)
        self.vendor = vendor
        self.num_runs = 10 if num_runs == None else num_runs
        self.crates = crates
        self.crate_paths = []
        for crate in self.crates: 
            crate_path = crate.replace("/", "-")
            self.crate_paths.append(crate_path)

    def revert_criterion_version(self):
        os.chdir(UNSAFE_DIR)
        for crate_path in self.crate_paths: 
            os.chdir(crate_path)
            subprocess.run(["cargo", "rm", "criterion", "--dev"], 
                stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
            subprocess.run(["cargo", "add", "criterion@=0.3.2", "--dev"], 
                stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
            os.chdir(UNSAFE_DIR)

    def vendor_deps(self):
        os.chdir(UNSAFE_DIR)
        for crate_path in self.crate_paths:
            print("Vendoring {}".format(crate_path))
            os.chdir(crate_path)
            subprocess.run(["cargo", "vendor", "--versioned-dirs", VENDOR_DIR],
                stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
            subprocess.run(["mkdir", "-p", ".cargo"])
            with open(".cargo/config.toml", 'a') as fd:
                fd.write("[source.crates-io]\nreplace-with = \x22vendored-sources\x22\n\n[source.vendored-sources]\ndirectory = \x22{}\x22\n".format(VENDOR_DIR))
            patchAll(".", VENDOR_DIR, VENDOR_DIR)
            os.chdir(curdir)

    # Rustup directory override is not carried by copy, 
    # must be done for each directory individually
    def set_rust_version(self):
        for DIR in EXP_DIRS:
            os.chdir(DIR)
            for crate_path in self.crate_paths:
                subprocess.run(["rustup", "override", "set", self.rust_version],
                    stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))

    def download_crates(self):
        subprocess.run(["mkdir", "-p", UNSAFE_DIR])
        os.chdir(UNSAFE_DIR)
        for crate in self.crates: 
            print("Downloading {}".format(crate.replace("/", "-")))
            subprocess.run(["wget", "https://crates.io/api/v1/crates/{}/download".format(crate)],
                stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
            subprocess.run(["tar", "-xf", "download"])
            subprocess.run(["rm", "download"])

        # Set the correct criterion version and vendor
        # in UNSAFE_DIR (will just be copied to SAFE_DIR)
        self.revert_criterion_version()
        if self.vendor: 
            self.vendor_deps()

        # If SAFE_DIR already exists, copy crates over
        # individually from UNSAFE_DIR
        if os.path.isdir(SAFE_DIR):
            for crate_path in self.crate_paths:
                subprocess.run(["cp", "-r", crate_path, os.path.join(SAFE_DIR, crate_path)])
        # Otherwise, copy the entire UNSAFE_DIR into (new) SAFE_DIR
        else: 
            subprocess.run(["cp", "-r", UNSAFE_DIR, SAFE_DIR])

    def convert_to_safe(self, mod=False):
        # If our modified rustc is used we can rely on the 
        # generated 'mir-filelist' file for converting 
        # unchecked indexing
        if mod:
            safe_crate_dir = os.path.join(ROOT_PATH, "safe-crates")
            mir_filelist = "/exploreunsafe/mir-filelist"
            os.chdir(safe_crate_dir)
            for crate_path in self.crate_paths:
                print("Compiling {}".format(crate_path))
                os.chdir(crate_path)
                subprocess.run(["rm", "-f", mir_filelist])
                subprocess.run(["cargo", "clean"])
                subprocess.run(["cargo", "bench", "--verbose", "--no-run"],
                    stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
                subprocess.run(["mv", mir_filelist, "mir-filelist"])
                subprocess.run(["cargo", "clean"])
                print("Converting {}".format(crate_path))
                subprocess.run(["python3", "../../regexify.py", "--root", 
".", "--mir-filelist", "mir-filelist"])
                os.chdir(safe_crate_dir)
        # For all other rustc versions we 
        # solely rely on our regexify implementation
        else: 
            safe_crate_dir = os.path.join(ROOT_PATH, "safe-crates")
            os.chdir(safe_crate_dir)
            for crate_path in self.crate_paths:
                os.chdir(crate_path)
                subprocess.run(["cargo", "clean"])
                print("Converting {}".format(crate_path))
                subprocess.run(["python3", "../../regexify.py", "--root", "."])
                os.chdir(safe_crate_dir)

    def compile_benchmarks(self):
        for DIR in EXP_DIRS: 
            if DIR == UNSAFE_DIR:
                print("Compiling unsafe baselines")
            else: 
                print("Compiling converted crates")
            os.chdir(DIR)
            for crate_path in self.crate_paths:
                print("\t{}".format(crate_path))
                os.chdir(crate_path)
                with open(COMP_LOG, "w") as comp_log: 
                    subprocess.run(["cargo", "clean"])
                    try: 
                        subprocess.run(["cargo", "bench", "--verbose", "--no-run"], 
                            timeout=1200, stdout=comp_log, stderr=comp_log)
                    except subprocess.TimeoutExpired as err:
                        print(err)
                        subprocess.run(["mkdir", "-p", "timeouts"])
                        subprocess.run(["touch", "timeouts/compile-timedout"])
                os.chdir(DIR)
        os.chdir(ROOT_PATH)

    def run_benchmarks(self):
        # Create results directory
        for DIR in EXP_DIRS: 
            for crate in self.crate_paths: 
                os.chdir(os.path.join(DIR, crate))
                subprocess.run(["mkdir", "-p", RESULT_DIR])
                
        for run in range(self.num_runs): 
            print("Run #{}".format(run))
            # In even runs benchmark safe crates first, 
            # in odd runs benchmark unsafe crates first
            if run % 2 == 0:
                EXP_DIRS = [SAFE_DIR, UNSAFE_DIR]
            # Randomize crate order for every new run
            random.shuffle(self.crate_paths)
            count = 0
            for crate in self.crate_paths:
                count += 1
                print("\tBenchmarking {} ({}/{} crates)".format(crate, count, len(self.crate_paths)))
                for DIR in EXP_DIRS:
                    if DIR == UNSAFE_DIR:
                        print("\t\tconverted")
                    else: 
                        print("\t\toriginal")
                    os.chdir(os.path.join(DIR, crate))
                    run_log = os.path.join(RESULT_DIR, run, RUN_LOG)
                    with open(run_log, "w") as fd: 
                        try: 
                            subprocess.run(["cargo", "bench", "--verbose"], 
                                timeout=1800, stdout=fd, stderr=fd)
                        except subprocess.TimeoutExpired as err:
                            print(err)
                            subprocess.run(["mkdir", "-p", "timeouts"])
                            subprocess.run(["touch", "timeouts/run-{}-timedout".format(run)])
        os.chdir(ROOT_PATH)

    def aggregate_results(self):
        print("Aggregating results")

        # Parse per-run data
        subprocess.run(["mkdir", "-p", RESULT_DIR])
        for crate_path in self.crate_paths: 
            subprocess.run(["mkdir", "-p", crate_path])
            for run in range(self.num_runs):
                unsafe_res = os.path.join(UNSAFE_DIR, crate_path, "results", str(run), RUN_LOG)
                safe_res = os.path.join(SAFE_DIR, crate_path, "results", str(run), RUN_LOG)
                outfile = os.path.join(RESULT_DIR, crate_PATH, "run-{}".format(str(run)))
                dump_benchmark(outfile, unsafe_res, safe_res, 1)
        os.chdir(RESULT_DIR)

        # Aggregate across runs
        for crate_path in self.crate_paths: 
            crunchedfile = os.path.join(RESULT_DIR, crate_path, CRUNCHED)
            path_wrangle(crunchedfile, HEADERS)

            samplefile = os.path.join(RESULT_DIR, crate_path, "run-0")
            with open(samplefile, "w") as fd: 
                rows = len(fd.readlines()) - 1
            cols = 2
            matrix = numpy.zeros((rows, cols, self.num_runs))

            bench_names = []
            for run in range(self.num_runs):
                infile = os.path.join(RESULT_DIR, crate_path, "run-{}".format(str(run)))
                with open(infile, "r") as infd: 
                    for row, line in enumerate(infd): 
                        # Skip header
                        if row == 0: 
                            continue
                        columns = line.split()
                        for col in range(len(columns)):
                            # Get benchmark names from single file
                            if run == 0 and col == 0: 
                                bench_names.append(columns[col])
                            # Collect <time> columns
                            if col % 2 == 1: 
                                mcol_idx = int((col - 1) / 2)
                                matrix[row-1][mcol_idx][run] = columns[col]

            # Crunch matrix
            with open(crunchedfile, 'a') as crunchfd: 
                for row in range(rows):
                    cur = []
                    bench_name = bench_names[row]
                    cur.append(bench_name)
                    for col in range(cols):
                        med, stdev = stats2(matrix[row][col])
                    cur.append(str(med))
                    cur.append(str(stdev))
                writerow(crunchfd, cur)

def arg_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crates", "-c",
        metavar="name/v.v.v",
        type=str,
        nargs="+",
        help="versioned crates to download and benchmark")
    parser.add_argument("--rust-version", "-r",
        metavar="yyyy-mm-dd",
        type=str,
        help="version of the Rust compiler with which to "\
            "compile crates")
    parser.add_argument("--vendor", "-v",
        action="store_true",
        help="convert vendored dependencies")
    parser.add_argument("--num-runs", "-n",
        metavar="N",
        type=int,
        help="specify the number of times to run each benchmark "\
            "(if not specified, default is 10)")
    args = parser.parse_args()
    return args.crates, args.rust_version, args.vendor, args.num_runs

if __name__ == "__main__":
    crates, rust_version, vendor, num_runs = arg_parse()

    cio = CIO(crates, rust_version, vendor, num_runs)

    cio.download_crates()
    cio.set_rust_version()
    if rust_version == None: 
        cio.convert_to_safe(mod=True)
    else: 
        cio.convert_to_safe()

    start = datetime.datetime.now()
    # Compile benchmarks and log duration
    cio.compile_benchmarks()
    end = datetime.datetime.now()
    duration = end - start
    durfile = "duration-compile"
    with open(durfile, "w") as fd: 
        fd.write("start:\t\t{}\n".format(start))
        fd.write("end:\t\t{}\n".format(end))
        fd.write("duration:\t{}\n".format(duration))

    start = datetime.datetime.now()
    # Run benchmarks and log duration
    cio.run_benchmarks()
    end = datetime.datetime.now()
    duration = end - start
    durfile = "duration-benchmark"
    with open(durfile, "w") as fd: 
        fd.write("start:\t\t{}\n".format(start))
        fd.write("end:\t\t{}\n".format(end))
        fd.write("duration:\t{}\n".format(duration))

    # Aggregate results
    cio.aggregate_results()
