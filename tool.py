#!/usr/bin/env python

import os
import sys
import argparse
import subprocess
from make_patch import patchAll

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))
VENDOR_DIR = "vendor"
COMP_LOG = "compile.log"
RUN_LOG = "run.log"

class CIO:

    def __init__(self, crates, compiler_version):
        self.compiler_version = "mod" if compiler_version == None else "nightly-{}".format(compiler_version)
        self.crates = crates
        self.crate_paths = []
        for crate in self.crates: 
            crate_path = crate.replace("/", "-")
            self.crate_paths.append(crate_path)

    def revert_criterion_version(self):
        unsafe_crate_dir = os.path.join(ROOT_PATH, "unsafe-crates")
        os.chdir(unsafe_crate_dir)
        for crate_path in self.crate_paths: 
            os.chdir(crate_path)
            subprocess.run(["cargo", "rm", "criterion", "--dev"], 
                stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
            subprocess.run(["cargo", "add", "criterion@=0.3.2", "--dev"], 
                stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
            os.chdir(unsafe_crate_dir)

    def vendor_deps(self, curdir):
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

    def set_compiler_version(self):
        unsafe_crate_dir = os.path.join(ROOT_PATH, "unsafe-crates")
        os.chdir(unsafe_crate_dir)
        for crate_path in self.crate_paths:
            subprocess.run(["rustup", "override", "set", self.compiler_version],
                stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))

        safe_crate_dir = os.path.join(ROOT_PATH, "safe-crates")
        os.chdir(safe_crate_dir)
        for crate_path in self.crate_paths:
            subprocess.run(["rustup", "override", "set", self.compiler_version],
                stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))

    def download_crates(self):
        unsafe_crate_dir = os.path.join(ROOT_PATH, "unsafe-crates")
        subprocess.run(["mkdir", "-p", unsafe_crate_dir])
        os.chdir(unsafe_crate_dir)
        for crate in self.crates: 
            print("Downloading {}".format(crate.replace("/", "-")))
            link = "https://crates.io/api/v1/crates/{}/download".format(crate)
            subprocess.run(["wget", link],
                stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
            subprocess.run(["tar", "-xf", "download"])
            subprocess.run(["rm", "download"])

        self.revert_criterion_version()
        #self.vendor_deps(unsafe_crate_dir)
        safe_crate_dir = os.path.join(ROOT_PATH, "safe-crates")
        if os.path.isdir(safe_crate_dir):
            for crate_path in self.crate_paths:
                subprocess.run(["cp", "-r", crate_path, os.path.join(safe_crate_dir, crate_path)])
        else: 
            subprocess.run(["cp", "-r", unsafe_crate_dir, safe_crate_dir])

    def convert_safe(self, mod=False):
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
        print("Compiling unsafe baselines")
        unsafe_crate_dir = os.path.join(ROOT_PATH, "unsafe-crates")
        os.chdir(unsafe_crate_dir)
        for crate_path in self.crate_paths:
            print("\t{}".format(crate_path))
            os.chdir(crate_path)
            comp_log = open(COMP_LOG, "w")
            subprocess.run(["cargo", "clean"])
            try: 
                subprocess.run(["cargo", "bench", "--verbose", "--no-run"], timeout=1200, stdout=comp_log, stderr=comp_log)
            except subprocess.TimeoutExpired as err:
                print(err)
                subprocess.run(["touch", "compile-timedout"])
            finally:
                comp_log.close()
            os.chdir(unsafe_crate_dir)

        print("Compiling converted crates")
        safe_crate_dir = os.path.join(ROOT_PATH, "safe-crates")
        os.chdir(safe_crate_dir)
        for crate_path in self.crate_paths:
            print("\t{}".format(crate_path))
            os.chdir(crate_path)
            comp_log = open(COMP_LOG, "w")
            subprocess.run(["cargo", "clean"])
            try: 
                subprocess.run(["cargo", "bench", "--verbose", "--no-run"], timeout=1200, stdout=comp_log, stderr=comp_log)
            except subprocess.TimeoutExpired as err:
                print(err)
                subprocess.run(["touch", "compile-timedout"])
            finally:
                comp_log.close()
            os.chdir(safe_crate_dir)

def arg_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crates", "-c",
        metavar="name/v.v.v",
        type=str,
        nargs="+",
        help="versioned crates to download and benchmark")
    parser.add_argument("--compiler-version", "-v",
        metavar="yyyy-mm-dd",
        type=str,
        help="version of the Rust compiler with which to "\
            "compile crates")
    args = parser.parse_args()
    return args.crates, args.compiler_version

if __name__ == "__main__":
    crates, compiler_version = arg_parse()

    cio = CIO(crates, compiler_version)

    cio.download_crates()
    cio.set_compiler_version()
    if compiler_version == None: 
        cio.convert_safe(mod=True)
    else: 
        cio.convert_safe()
    cio.compile_benchmarks()
    #cio.run_benchmarks(numruns=10)
