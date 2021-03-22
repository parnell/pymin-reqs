#!/usr/bin/env python3

from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pymin-reqs",
    version="1.0.2",
    description="Create a minimal requirements.txt file from Python source code",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Parnell",
    author_email="",
    install_requires=["pip>=20.0"],
    url="https://github.com/parnell/pymin-reqs",
    packages=["pymin_reqs"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": ["pymin_reqs = pymin_reqs.pymin_reqs:main"],
    },
)
