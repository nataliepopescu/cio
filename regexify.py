#!/usr/bin/env python3
# Convert get_unchecked(_mut), and from_raw_parts(_mut) to safe version
import re
import os
import subprocess
import argparse
from make_patch import patchAll

# [(line, col, fname), ...]
def dumpBCs(bcs, logfile=None):
    if not logfile:
        return

    with open(logfile, 'w') as fd:
        for (line, col, fname) in bcs:
            # get rid of the initial "./"
            if fname.startswith("./"):
                fname = fname[2:]

            # dump with the format that remove-bc pass can recognize
            fd.write("%d %d %s\n" % (line, col, fname))


def findTargetFiles(mir_file): #single_file):
    # a line in mir_filelist looks something like: src/lib.rs:28:42: 28:62 (#0)
    filelist = dict()

    lines = mir_file.readlines()
    #lines = mir_filelist.strip().split("\n")
    for line in lines:
        parts = line.split(":")
        filename = parts[0].strip()
        line_start = parts[1].strip()
        line_end = parts[3].strip()
        col_start = parts[2].strip()
        col_end = parts[4].split("(")[0].strip()

        # dictionary structure: 
        #  { 
        #    filename1: [
        #        [line_start, line_end, col_start, col_end], 
        #    ],
        #    filename2: [
        #        [line_start, line_end, col_start, col_end], 
        #        [line_start, line_end, col_start, col_end], 
        #    ],
        #  }
        if filelist.get(filename): 
            #print("filename already exists")
            entries = filelist.get(filename)
            new_entry = int(line_start) #, 
            #    int(line_end), 
            #    int(col_start), 
            #    int(col_end)
            #]
            if new_entry in entries: 
                continue
            entries.append(new_entry)
            filelist.update({filename: entries})
        else: 
            #print("filename does not yet exist")
            entry = int(line_start) #, 
            #    int(line_end), 
            #    int(col_start), 
            #    int(col_end)
            #]
            filelist.update({filename: [entry]})

    return filelist


def findTargetFilesOld():
    target = "."
    rs_files = subprocess.run(["find", target, "-name", "*.rs", "-type", "f"], 
            capture_output=True, text=True)
    filelist = rs_files.stdout.split()
    if os.path.exists("ignore.txt"):
        with open("ignore.txt", 'r') as fd:
            lines = fd.readlines()
            ignore_list = [i.strip() for i in lines]

        final_list = filelist.copy()
        for f in filelist:
            for ignore in ignore_list:
                if ignore in f:
                    if f in final_list:
                        final_list.remove(f)

        print("Removed", len(filelist) - len (final_list), "files")
        filelist = final_list
    return filelist


# Convert all things in place in one file
# old_fname is the file before conversion
# new_fname is the file after conversion 
# selective unsafe contains the lines that we want to keep the unsafe
def convertFile(old_fname, new_fname, selective_safe=[], make_selective_unsafe=False):
    # mutregex_in = r'([($a-zA-Z_][a-zA-Z0-9:_\.\(\)\*]*)\.get_unchecked_mut\(' #]([0-9a-zA-Z_][a-zA-Z0-9_\.\>\*\+ ]*)[)]'
    # mutregex_out = r'(&mut \1[' #\2])'
    # regex_in = r'([($a-zA-Z_][a-zA-Z0-9:_\.\(\)\*]*)\.get_unchecked\(' #]([0-9a-zA-Z_][a-zA-Z0-9_\.\>\*\+ ]*)[)]'
    # regex_out = r'(&\1[' #\2])'

    # # handle raw parts, emitted by the macro as get_unchecked_raw(_mut)
    # raw_mutregex_in = r'([$a-zA-Z_][a-zA-Z0-9:_\.\(\)]*)\.get_unchecked_raw_mut\(' #]([0-9a-zA-Z_][a-zA-Z0-9_\.\>\*\+ ]*)[)]'
    # raw_mutregex_out = r'(&mut \1[' #\2])'
    # raw_regex_in = r'([$a-zA-Z_][a-zA-Z0-9:_\.\(\)]*)\.get_unchecked_raw\(' #]([0-9a-zA-Z_][a-zA-Z0-9_\.\>\*\+ ]*)[)]'
    # raw_regex_out = r'(&\1[' #\2])'
    mutregex_in = r'\.get_unchecked_mut\(' #]([0-9a-zA-Z_][a-zA-Z0-9_\.\>\*\+ ]*)[)]'
    mutregex_out = r'.get_mut(' #\2])'
    regex_in = r'\.get_unchecked\(' #]([0-9a-zA-Z_][a-zA-Z0-9_\.\>\*\+ ]*)[)]'
    regex_out = r'.get(' #\2])'
    #raw_mutregex_in = r'\.get_unchecked_raw_mut\(' #]([0-9a-zA-Z_][a-zA-Z0-9_\.\>\*\+ ]*)[)]'
    #raw_mutregex_out = r'.get_mut(' #\2])'
    #raw_regex_in = r'\.get_unchecked_raw\(' #]([0-9a-zA-Z_][a-zA-Z0-9_\.\>\*\+ ]*)[)]'
    #raw_regex_out = r'.get(' #\2])'
    
    with open(old_fname, 'r') as fd:
        old_block = fd.read()

    block, bcs_mut = convertBlock(old_block, mutregex_in, mutregex_out, 1, selective_safe, make_selective_unsafe)
    if block == None or bcs_mut == None:
        print("Conversion failed in file %s" % old_fname)
        exit()

    block, bcs_immut = convertBlock(block, regex_in, regex_out, 1, selective_safe, make_selective_unsafe)
    if block == None or bcs_immut == None:
        print("Conversion failed in file %s" % old_fname)
        exit()

    #block, bcs_raw_mut = convertBlock(block, raw_mutregex_in, raw_mutregex_out)
    #if block == None or bcs_raw_mut == None:
    #    print("Conversion failed in file %s" % old_fname)
    #    exit()

    #block, bcs_raw_immut = convertBlock(block, raw_regex_in, raw_regex_out)
    #if block == None or bcs_raw_immut == None:
    #    print("Conversion failed in file %s" % old_fname)
    #    exit()

    new_block = block
    bcs = bcs_mut + bcs_immut # + bcs_raw_mut + bcs_raw_immut 

    with open(new_fname, 'w') as fd:
        fd.write(new_block)

    # add fname to the bcs
    bcs = [ (line, col, new_fname) for (line, col) in bcs ] 

    return bcs


# already have a left parenthesis, find the matching right parenthesis
def findMatchingParenthsis(block):
    # FIXME MIR pass returns full span
    depth = 1

    for pos, ch in enumerate(block):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if depth == 0:
            return pos

    # failed case 
    return -1


# when a x.get_unchecked( or x.get_unchecked_mut( is found
# Step 1: go back and replace the handle with regex
# Step 2: go forward and find matching parenthesis, replace it as "])"
# Step 3: convert whatever is inside
def convertBlock(block, regex_in, regex_out, cur_line=1, selective_safe=[], make_selective_unsafe=False):
    bcs = []
    new_block = ""

    # block == file
    # need finer re matching granularity, because some functions may not be 
    # converted in this file

    # convert all instances of regex_in (per line) one at a time
    while (match := re.search(regex_in, block)): 
        # put whatever before in it 
        pre_block = block[:match.span()[0]]
        cur_block = block[match.span()[0]:match.span()[1]]
        post_block = block[match.span()[1]:]

        # handle within function call
        # foo(xx.get_uncheck(
        right = 0
        for idx in reversed(range(len(cur_block) - 1)): # exclude the last '('
            if cur_block[idx] == ')':
                right += 1
            if cur_block[idx] == '(':
                right -= 1
            if right < 0:
                # found function start
                pre_block += cur_block[:idx+1]
                cur_block = cur_block[idx + 1:]
                break

        # calculate line and col
        skipped_lines = pre_block.count('\n')
        cur_line += skipped_lines

        # the column number of the starting point of old block
        old_col = pre_block.rfind('\n')
        if old_col == -1:
            old_col = len(pre_block) + 1
        else:
            old_col = len(pre_block) - old_col

        if make_selective_unsafe:
            if cur_line in selective_safe: # treat like selective_unsafe
                new_block += pre_block + cur_block
                block = post_block
                continue
        else:
            # if choose not to convert this line to safe
            if not cur_line in selective_safe:
                #print(cur_line)
                new_block += pre_block + cur_block
                block = post_block
                continue

        # find match parenthesis in post_block
        pos = findMatchingParenthsis(post_block)
        # self.get_unchecked() syntax, need to ignore
        if pos == 0: 
            new_block += pre_block + cur_block
            block = post_block
            continue

        if pos == -1:
            print("No enclosing parenthesis found, Line %d" % (cur_line))
            return None, None

        # replace with the safe syntax
        cur_block = re.sub(regex_in, regex_out, cur_block, count=1)
        new_col = old_col + len(cur_block) - 1

        new_middle_block, addition_bcs = convertBlock(post_block[:pos], regex_in, regex_out, cur_line, selective_safe, make_selective_unsafe)

        # add bounds checks from the middle block to the bcs
        if addition_bcs is None:
            return None, None
        else:
            bcs.extend(addition_bcs)

        # update new block
        # new_block += pre_block + cur_block + new_middle_block + "])"  # use the right parenthesis
        new_block += pre_block + cur_block + new_middle_block + ").unwrap()"  # use the right parenthesis

        # update block
        block = post_block[pos + 1:]

        # update bcs
        bcs.append((cur_line, new_col))

        # might have skipped several lines in the middle block
        skipped_lines = new_middle_block.count('\n')
        cur_line += skipped_lines

    # append whatever is left in the block
    new_block += block

    return new_block, bcs


def argParse():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", "-r",
            metavar="path",
            type=str,
            help="root path from where to start source code conversions")
    #parser.add_argument("--single-file", "-s",
    #        metavar="filename",
    #        type=str,
    #        nargs="?",
    #        help="Specify this if only want to apply this tool to a single file")
    parser.add_argument("--mir-filelist", "-f",
            metavar="filename",
            required=False,
            type=str,
            nargs=1,
            #default="/exploreunsafe/mir-filelist",
            help="Specify the mir output file that contains the filenames, line #s, and col #s /"
            "of the function calls to convert") #this if only want to apply this tool to a single file")
    parser.add_argument("--logfile", "-l",
            metavar="filename",
            type=str,
            nargs="?",
            const="/exploreunsafe/changes.txt",
            default="changes.txt",
            help="name of the file in which to store line/column/filename of changes; "\
                    "default is 'changes.txt' in the specified root dir")
    args = parser.parse_args()
    return args.root, args.logfile, args.mir_filelist


if __name__ == "__main__":
    root, logfile, mir_filelist = argParse()
    os.chdir(root)

    # vendor
    #subprocess.run(["cargo", "clean"])
    #subprocess.run(["cargo", "vendor", "--versioned-dirs"])
    #subprocess.run(["mkdir", "-p", ".cargo"])
    #with open(".cargo/config.toml", 'a') as fd: 
    #    fd.write("[source.crates-io]\nreplace-with = \x22vendored-sources\x22\n[source.vendored-sources]\ndirectory = \x22vendor\x22")

    ## patch Cargo.toml with vendored crates
    #patchAll(".", "vendor", "vendor")

    ## get list of get_unchecked to convert
    #os.environ["RUSTFLAGS"] = "-Z convert-unchecked-indexing"
    #mir_filelist = subprocess.run(["cargo", "bench", "--no-run"], capture_output=True, text=True)

    bcs = []

    if mir_filelist == None:
        filelist = findTargetFilesOld()
        for f in filelist:
            bcs.extend(convertFile(f, f, [], make_selective_unsafe=True))
    else:
        if "mozilla" in root: 
            #patchAll(".", "vendor", "vendor")
            fd = open(mir_filelist, 'r')
        else:
            fd = open(mir_filelist[0], 'r')
        filelist = findTargetFiles(fd)
        #print("\nFilelist: \n")
        #for f in filelist.items():
        #    print(f)
        #print()
    
        # List of all bounds checks
        for fname in filelist.keys():
            bcs.extend(convertFile(fname, fname, filelist[fname]))

    dumpBCs(bcs, logfile)

