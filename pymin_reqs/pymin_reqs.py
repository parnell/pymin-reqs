import argparse
import ast
import glob
import logging
import os
import re
import subprocess
import sys
import typing
from collections import defaultdict
from enum import Enum
from functools import lru_cache

import pip._internal.utils.misc as misc
import pkg_resources


class Source(Enum):
    pip = "pip"
    conda = "conda"


class SkippableException(Exception):
    pass


class Package:
    def __init__(self):
        self.count = 0
        self.source = ""
        self.name = None
        self.version = None
        self.files = set()

    def __str__(self):
        return f"(Package {self.name}, source={self.source}, count={self.count}]"

    def ispip(self):
        return self.source == Source.pip

    def isconda(self):
        return self.source == Source.conda


class PackageResolver:
    def __init__(self):
        self._pip_freeze = None
        self._conda_freeze = None

    @property
    def pip_freeze(self):
        if self._pip_freeze is not None:
            return self._pip_freeze
        self._pip_freeze = {}
        cmd = ["pip", "freeze"]
        p = subprocess.check_output(cmd)
        for l in p.decode("utf-8").split("\n"):
            if "==" not in l:
                continue
            self._pip_freeze[l.split("==")[0].lower()] = l
        return self._pip_freeze

    @property
    def conda_freeze(self):
        if self._conda_freeze is not None:
            return self._conda_freeze

        self._conda_freeze = {}
        if "CONDA_DEFAULT_ENV" in os.environ:
            cmd = ["conda", "list", "--export"]
            p = subprocess.check_output(cmd)
            for l in p.decode("utf-8").split("\n"):
                if "==" not in l:
                    continue
                self._conda_freeze[l.split("==")[0].lower()] = l
        return self._conda_freeze


def get_version(string: str):
    return string.split("==")[1]


def _add_pkg_to_dict(
    d: dict,
    pkg_res: PackageResolver,
    pot_pkg: str,
    src_file: str,
    show_pip: bool = True,
    show_conda: bool = False,
):
    pkgname = pot_pkg.lower()
    # Check for files that we can't import
    if pkgname.endswith((".*", ".", "*", "_")) or pkgname.startswith(("_")):
        return
    src = os.path.relpath(src_file)
    if pot_pkg in d:
        pkg = d[pot_pkg]
        pkg.count += 1
        pkg.files.add(src)
    else:
        pkg = d[pot_pkg]
        pkg.count += 1
        pkg.name = pkgname
        pkg.files.add(src)
        if show_pip:
            pkg.pip_dist = misc.get_distribution(pkgname)
            pip_name = pkg.pip_dist.project_name.lower() if pkg.pip_dist else None
            for n in [pkgname, pip_name]:
                if n and n in pkg_res.pip_freeze:
                    pkg.source = Source.pip
                    pkg.version = get_version(pkg_res.pip_freeze[pip_name])
                    logging.debug(f"  # Found pip package {pkg.name}=={pkg.version}")
        if show_conda and pkgname in pkg_res.conda_freeze:
            pkg.source = Source.conda
            pkg.version = get_version(pkg_res.conda_freeze[pkgname])
            logging.debug(f"  # Found conda package {pkg.name}=={pkg.version}")

    if "." in pot_pkg:
        _add_pkg_to_dict(d, pkg_res, pot_pkg.split(".")[0], src_file)


def get_dir_installs(indir: str, show_pip: bool, show_conda: bool, ignore_errors: bool = False):
    pr = PackageResolver()

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
                    _add_pkg_to_dict(
                        imports, pr, n2.name, infile, show_pip=show_pip, show_conda=show_conda
                    )

            elif isinstance(n, ast.ImportFrom):
                logging.debug(f" - {n.module} imports {[e.name for e in n.names]}")
                for n2 in n.names:

                    _add_pkg_to_dict(
                        imports,
                        pr,
                        f"{n.module}.{n2.name}",
                        infile,
                        show_pip=show_pip,
                        show_conda=show_conda,
                    )
                    _add_pkg_to_dict(
                        imports, pr, n2.name, infile, show_pip=show_pip, show_conda=show_conda
                    )

    return imports


def _make_minimal_reqs(
    directory: str,
    outpipe: typing.TextIO,
    show_pip: bool = True,
    show_conda: bool = False,
    overwrite: bool = False,
    ignore_errors: bool = False,
    show_stats: bool = False,
):
    pkgs = get_dir_installs(
        directory, show_pip=show_pip, show_conda=show_conda, ignore_errors=ignore_errors
    )
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
    res = []
    for name, pkg in {k: pkgs[k] for k in sorted(pkgs)}.items():
        # Ignore our own project
        if self_pkg_names and name.lower() in self_pkg_names:
            continue
        if show_pip and pkg.ispip() or show_conda and pkg.isconda():
            if show_stats:
                files = sorted(list(pkg.files))
                outpipe.write(f"# {pkg.name} found in {files} count={len(files)}\n")
            outpipe.write(f"{pkg.name}=={pkg.version}\n")

    return res


def make_minimal_reqs(
    directory: str,
    outfile,
    show_pip: bool = True,
    show_conda: bool = False,
    overwrite: bool = False,
    ignore_errors: bool = False,
    show_stats: bool = False,
):
    try:
        of = open(outfile, "w") if isinstance(outfile, str) else outfile

        return _make_minimal_reqs(
            directory,
            of,
            show_pip=show_pip,
            show_conda=show_conda,
            overwrite=overwrite,
            ignore_errors=ignore_errors,
            show_stats=show_stats,
        )
    finally:
        if isinstance(outfile, str):
            of.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--directory",
        default=".",
        help="Specify the input directory. Default: '.'",
    )
    parser.add_argument(
        "--conda",
        action="store_true",
        help="Output conda requirements instead of pip. Use --pip --conda to show both",
    )
    parser.add_argument(
        "--pip",
        action="store_const",
        default=None,
        const=1,
        help="Show pip requirements. not required by default unless --conda is also specified",
    )

    parser.add_argument(
        "-f", "--force", action="store_true", help="Force overwrite of the given file in --outfile"
    )
    parser.add_argument(
        "-s",
        "--stats",
        action="store_true",
        help="Show import locations and count of imported modules.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        help="Verbose mode",
        default=logging.INFO,
        const=logging.DEBUG,
    )
    parser.add_argument(
        "-e", "--ignore-errors", action="store_true", help="Ignore errors when possible"
    )
    parser.add_argument(
        "-o",
        "--outfile",
        default=sys.stdout,
        help="Specify the output file. Default 'requirements.txt'",
    )
    args = parser.parse_args()
    show_pip = args.pip == 1 or not args.conda

    logging.basicConfig(level=args.verbose)

    try:
        make_minimal_reqs(
            args.directory,
            args.outfile,
            show_pip=show_pip,
            show_conda=args.conda,
            overwrite=args.force,
            ignore_errors=args.ignore_errors,
            show_stats=args.stats,
        )
    except SkippableException as e:
        logging.error(e)
        logging.error(f"Use --ignore-errors to ignore this error")


if __name__ == "__main__":
    main()
