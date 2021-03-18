import argparse
import ast
import glob
import os
import re
import sys
from collections import defaultdict

from pip._internal.operations import freeze


def get_pip_installs():
    d = {}
    for e in freeze.freeze():
        d[e.split("==")[0].lower()] = e
    return d


def _add_to_dict(d, imp):
    d[imp.lower()] += 1
    if "." in imp:
        d[imp.split(".")[0].lower()] += 1


def get_dir_installs(indir, verbose=False, ignore_errors=False):
    imports = defaultdict(int)
    if verbose:
        print(f"# Parsing Files")
    for infile in glob.glob(f"{indir}/**/*.py", recursive=True):
        if verbose:
            print(f"Parsing {infile}")
        try:
            with open(infile) as f:
                tree = ast.parse(f.read())
        except Exception as e:
            if ignore_errors:
                print(f"{e}", file=sys.stderr)
            else:
                raise
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for n2 in n.names:
                    _add_to_dict(imports, n2.name)

            elif isinstance(n, ast.ImportFrom):
                _add_to_dict(imports, n.module)

    return imports


def _make_minimal_reqs(directory, outpipe, overwrite=False, verbose=False, ignore_errors=False):
    cl = get_dir_installs(directory, verbose, ignore_errors)
    d = get_pip_installs()
    if verbose:
        print(f"# Found minimal imports")
    for m, count in cl.items():
        if m in d:
            if verbose:
                print(f"{d[m]}")
            outpipe.write(f"{d[m]}\n")


def make_minimal_reqs(directory, outfile, overwrite=False, verbose=False, ignore_errors=False):
    if isinstance(outfile, str):
        if not overwrite and os.path.exists(outfile):
            raise IOError(
                f"Exception: File '{outfile}' already exists. Use --overwrite to write over"
            )
        with open(outfile, "w") as of:
            _make_minimal_reqs(directory, of, overwrite, verbose, ignore_errors)
    else:
        _make_minimal_reqs(directory, outfile, overwrite, verbose, ignore_errors)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--directory", default=".", help="Specify the input directory. Default: '.'")
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-e", "--ignore-errors", action="store_true")
    parser.add_argument("-o", "--outfile", default="requirements.txt", help="Specify the output file. Default 'requirements.txt'")
    args = parser.parse_args()

    if not args.directory:
        if not os.getenv("HISTFILE"):
            raise Exception("History file was not found")
        directory = os.getenv("HISTFILE")
    else:
        directory = args.directory
    if args.outfile.lower() == "pipe":
        args.outfile = sys.stdout

    make_minimal_reqs(
        directory, args.outfile, overwrite=args.force, verbose=args.verbose, ignore_errors=args.ignore_errors
    )


if __name__ == "__main__":
    main()
