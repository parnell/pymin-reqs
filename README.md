# pymin_reqs

This module attempt to make a minimal `requirements.txt` file based on the imports are used inside of the code of your project, `.py` files. These requirements are a subset of what would be given using `pip freeze` or `conda list --export` as these commands give everything that is used inside of the Python environment. This is useful if a project is used inside of a shared environment or if you want a cleaner `requirements.txt ` that only has your imported modules but not the dependencies, and sub-dependencies, of those modules.

## Install With Pip
> `python3 -m pip install git+https://github.com/parnell/pymin-reqs`

## Usage
```
usage: pymin_reqs [-h] [-d DIRECTORY] [-c] [-p] [-f] [--counts] [-v] [-e] [-o OUTFILE]

optional arguments:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Specify the input directory. Default: '.'
  -c, --conda           Output conda requirements instead of pip. Use --pip --conda to show both
  -p, --pip             Show pip requirements. not required by default unless --conda is also specified
  -f, --force           Force overwrite of the given file in --outfile
  --counts              Show import counts for project. This number grows with each import on a from statement
  -v, --verbose         Verbose mode
  -e, --ignore-errors   Ignore errors when possible
  -o OUTFILE, --outfile OUTFILE
                        Specify the output file. Default 'requirements.txt'
```
## Examples
Show requirements on command line
> `pymin_reqs`

Output requirements to a file "requirements.txt"
> `pymin_reqs -o requirements.txt`

Output requirements to a file "requirements.txt" and force overwrite
> `pymin_reqs -f -o requirements.txt`

This module uses the abstract syntax tree(ast module) to find imports. If there are invalid python file this might cause errors in parsing. To get around this you can specify `--ignore-errors`
> `pymin_reqs --ignore-errors`



### Example output from commands
```
pip==20.2.4
setuptools==50.3.1
```
