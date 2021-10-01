#!/usr/bin/env python3.8

import argparse
import os
import re
import subprocess
import shutil

def convert(root):
    if os.path.exists(root): 
        for dep in os.listdir(root):
            full_path = os.path.join(root, dep)
            if os.path.isdir(full_path): 
                any_gu = subprocess.run(["grep", "-rn", "fn get_unchecked", 
                        full_path], capture_output=True, text=True)
                num_gu = len(any_gu.stdout.split())
                # if any locally-defined get_unchecked[_mut]s, 
                # remove from the set of crates to convert
                if num_gu > 0: 
                    print("deleting {}".format(dep))
                    try: 
                        shutil.rmtree(full_path)
                    except OSError as err: 
                        print("Error: {} : {}".format(full_path, err.strerror))

def patchAll(toml_dir, rel_root, root):
    toml = open(os.path.join(toml_dir, "Cargo.toml"), "a")
    to_patch = os.listdir(root)
    patches = dict()
    versioned = []
    unversioned = []
    for dep in to_patch:
        # if crate is versioned, come back to it later
        if re.search('[-][0-9]+[.][0-9]+[.][0-9]+', dep): 
            versioned.append(dep)
        else: 
            unversioned.append(dep)
    processed_versioned = []
    for v_crate in versioned: 
        m = re.search('[-][0-9]+[.][0-9]+[.][0-9]+', v_crate)
        end = m.span()[0]
        name = v_crate[:end]
        for u_crate in unversioned: 
            if u_crate == name:
                unversioned.remove(u_crate)
                processed_versioned.append(v_crate)
                u_patch = {
                    "path": os.path.join(rel_root, u_crate),
                }
                patches.update({u_crate: u_patch})
                vname = "{}01".format(name)
                v_patch = {
                    "path": os.path.join(rel_root, v_crate),
                    "package": name
                }
                patches.update({vname: v_patch})
    leftover_versioned = [c for c in versioned if c not in processed_versioned]
    for l_crate in leftover_versioned: 
        m = re.search('[-][0-9]+[.][0-9]+[.][0-9]+', l_crate)
        end = m.span()[0]
        name = l_crate[:end]
        patch = {
                "path": os.path.join(rel_root, l_crate),
                "package": name
            }
        patches.update({name: patch})
    for u_crate in unversioned: 
        patch = {
                "path": os.path.join(rel_root, u_crate),
                "package": u_crate
            }
        patches.update({u_crate: patch})
    for patch in patches: 
        patch_str = []
        patch_str.append("[patch.crates-io.{}]\n".format(patch))
        info = patches.get(patch)
        for field in info: 
            value = info.get(field)
            patch_str.append("{} = \"{}\"\n".format(field, value))
        patch_str.append("\n")
        #all_lines = "".join(patch_str)
        #print(all_lines)
        toml.write("".join(patch_str))

def patch(toml_dir, rel_root, root):
    toml = open(os.path.join(toml_dir, "Cargo.toml"), "a")

    # only patch the crates that have actually been converted
    to_patch = []
    changes = open(os.path.join(root, "changes.txt"), "r")
    for line in changes.readlines():
        print(line)
        changed_file = line.split()[2]
        crate = changed_file.split("/")[0]
        to_patch.append(crate)
    to_patch = list(dict.fromkeys(to_patch))
    for p in to_patch: 
        print(p)

    patches = dict()
    versioned = []
    unversioned = []
    for dep in to_patch:
        # if crate is versioned, come back to it later
        if re.search('[-][0-9]+[.][0-9]+[.][0-9]+', dep): 
            versioned.append(dep)
        else: 
            unversioned.append(dep)
    processed_versioned = []
    for v_crate in versioned: 
        m = re.search('[-][0-9]+[.][0-9]+[.][0-9]+', v_crate)
        end = m.span()[0]
        name = v_crate[:end]
        for u_crate in unversioned: 
            if u_crate == name:
                unversioned.remove(u_crate)
                processed_versioned.append(v_crate)
                u_patch = {
                    "path": os.path.join(rel_root, u_crate),
                }
                patches.update({u_crate: u_patch})
                vname = "{}01".format(name)
                v_patch = {
                    "path": os.path.join(rel_root, v_crate),
                    "package": name
                }
                patches.update({vname: v_patch})
    leftover_versioned = [c for c in versioned if c not in processed_versioned]
    for l_crate in leftover_versioned: 
        m = re.search('[-][0-9]+[.][0-9]+[.][0-9]+', l_crate)
        end = m.span()[0]
        name = l_crate[:end]
        patch = {
                "path": os.path.join(rel_root, l_crate),
                "package": name
            }
        patches.update({name: patch})
    for u_crate in unversioned: 
        patch = {
                "path": os.path.join(rel_root, u_crate),
                "package": u_crate
            }
        patches.update({u_crate: patch})
    for patch in patches: 
        patch_str = []
        patch_str.append("[patch.crates-io.{}]\n".format(patch))
        info = patches.get(patch)
        for field in info: 
            value = info.get(field)
            patch_str.append("{} = \"{}\"\n".format(field, value))
        patch_str.append("\n")
        #all_lines = "".join(patch_str)
        #print(all_lines)
        toml.write("".join(patch_str))

def arg_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument("--toml", "-t",
            metavar="path/to/root/toml/",
            type=str,
            required=True,
            help="path to the directory containing the root Cargo.toml file to "\
                    "append to")
    parser.add_argument("--rel_root", "-r",
            metavar="path/to/deps/",
            type=str,
            required=True,
            help="path to the directory containing the dependencies to convert, "\
                    "relative to the root Cargo.toml")
    args = parser.parse_args()
    return args.toml, args.rel_root

if __name__ == "__main__":
    toml, rel_root = arg_parse()
    root = os.path.join(toml, rel_root)
    #print("check for locally-defined get_unchecked")
    #convert(root)
    #print("convert")
    #subprocess.run(["python3", 
    #        os.path.join(os.path.dirname(os.path.abspath(__file__)), "regexify.py"), 
    #        "--root", root])
    print("editing cargo.toml")
    patchAll(toml, rel_root, root)
