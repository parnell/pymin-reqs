import argparse
import ast
import glob
import logging
import os
import re
import subprocess
import sys
from collections import defaultdict
from functools import lru_cache

import pip._internal.operations as pipops
import pip._internal.utils.misc as misc
import pkg_resources
import setuptools
from pip._internal.operations import freeze


class SkippableException(Exception):
    pass


class Package:
    def __init__(self):
        self.count = 0
        self.pip_dist = None
        self.conda_dist = None
        self.name = None
        self.version = None

    def __str__(self):
        return f"(Package {self.name}, pip={self.pip_dist}, count={self.count}]"


class PackageResolver:
    def __init__(self):
        self._pip_freeze = None
        self._conda_freeze = None

    @property
    def pip_freeze(self):
        if self._pip_freeze is not None:
            return self._pip_freeze
        self._pip_freeze = {}
        for e in freeze.freeze():
            self._pip_freeze[e.split("==")[0].lower()] = e
        return self._pip_freeze

    @property
    def conda_freeze(self):
        if self._conda_freeze is not None:
            return self._conda_freeze

        self._conda_freeze = {}
        if "CONDA_DEFAULT_ENV" in os.environ:
            cmd = ["conda", "list", "--export"]
            p = subprocess.check_output(cmd)
            lines = p.decode("utf-8").split("\n")
            for l in lines:
                if "==" not in l:
                    continue
                self._conda_freeze[l.split("==")[0].lower()] = l
        return self._conda_freeze


def _add_pkg_to_dict(d: dict, imp: str, pkg_res: PackageResolver = None):
    pkgname = imp.lower()
    # Check for endings that we can't import
    if pkgname.endswith((".*", ".", "*", "_")):
        return
    if pkgname.startswith(("_")):
        return
    if imp in d:
        pkg = d[imp]
        pkg.count += 1
    else:
        pkg = d[imp]
        pkg.name = pkgname
        pkg.pip_dist = misc.get_distribution(pkgname)
        if pkg.pip_dist:
            pkg.version = pkg.pip_dist.version
        if pkg_res and pkgname in pkg_res.conda_freeze:
            pkg.version = pkg_res.conda_freeze[pkgname].split("==")[1]

    if "." in imp:
        _add_pkg_to_dict(d, imp.split(".")[0], pkg_res)


def get_dir_installs(indir, needs_conda, ignore_errors=False):
    pr = PackageResolver() if needs_conda else None

    imports = defaultdict(Package)
    logging.debug(f"# Parsing Files")
    for infile in glob.glob(f"{indir}/**/*.py", recursive=True):
        logging.debug(f"Parsing {infile}")
        try:
            with open(infile) as f:
                tree = ast.parse(f.read())
        except Exception as e:
            if ignore_errors:
                logging.error(f"{e}")
            else:
                raise SkippableException(str(e)) from e
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                logging.debug(f" - {[e.name for e in n.names]}")
                for n2 in n.names:
                    _add_pkg_to_dict(imports, n2.name, pr)

            elif isinstance(n, ast.ImportFrom):
                logging.debug(f" - {n.module} imports {[e.name for e in n.names]}")
                for n2 in n.names:
                    _add_pkg_to_dict(imports, f"{n.module}.{n2.name}", pr)
                    _add_pkg_to_dict(imports, n2.name, pr)

    return imports


def _make_minimal_reqs(
    directory,
    outpipe,
    show_pip=True,
    show_conda=False,
    overwrite=False,
    ignore_errors=False,
):
    pkgs = get_dir_installs(directory, show_conda, ignore_errors)
    logging.debug(f"# Found minimal imports")
    self_pkg_names = None
    if os.path.exists(f"{directory}/setup.py"):
        bn = os.path.basename(os.path.abspath(directory))
        try:
            self_pkg = pkg_resources.require(bn)[0]
            n = self_pkg.__dict__["project_name"]
            self_pkg_names = [n] if "-" not in n else [n, n.replace("-", "_")]
        except Exception as e:
            if not ignore_errors:
                raise SkippableException(str(e)) from e

    # Print out our found packages
    for name, pkg in {k: pkgs[k] for k in sorted(pkgs)}.items():
        # Ignore our own project
        if self_pkg_names and name.lower() in self_pkg_names:
            continue
        if show_pip and pkg.pip_dist or show_conda and pkg.conda_dist:
            outpipe.write(f"{pkg.name}=={pkg.version}\n")


def make_minimal_reqs(
    directory,
    outfile,
    show_pip=True,
    show_conda=False,
    overwrite=False,
    ignore_errors=False,
):
    if isinstance(outfile, str):
        if not overwrite and os.path.exists(outfile):
            raise IOError(f"Exception: File '{outfile}' already exists. Use --force to write over")
        with open(outfile, "w") as of:
            _make_minimal_reqs(directory, of, show_pip, show_conda, overwrite, ignore_errors)
    else:
        _make_minimal_reqs(directory, outfile, show_pip, show_conda, overwrite, ignore_errors)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--directory",
        default=".",
        help="Specify the input directory. Default: '.'",
    )
    parser.add_argument(
        "-c",
        "--conda",
        action="store_true",
        help="Output conda requirements instead of pip. Use --pip --conda to show both",
    )
    parser.add_argument("-p", "--pip", action="store_const", const=1, default=None)

    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-e", "--ignore-errors", action="store_true")
    parser.add_argument(
        "-o",
        "--outfile",
        default=sys.stdout,
        help="Specify the output file. Default 'requirements.txt'",
    )
    args = parser.parse_args()
    show_pip = not args.conda or args.pip == 1

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    if not args.directory:
        if not os.getenv("HISTFILE"):
            raise Exception("History file was not found")
        directory = os.getenv("HISTFILE")
    else:
        directory = args.directory

    try:
        make_minimal_reqs(
            directory,
            args.outfile,
            show_pip=show_pip,
            show_conda=args.conda,
            overwrite=args.force,
            ignore_errors=args.ignore_errors,
        )
    except SkippableException as e:
        logging.error(e)
        logging.error(f"Use --ignore-errors to ignore this error")


if __name__ == "__main__":
    main()
