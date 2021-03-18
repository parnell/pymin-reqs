#!/usr/bin/env python3

from setuptools import setup

setup(name='pymin_reqs',
      version='1.0.0',
      description='',
      author='Parnell',
      author_email='',
      install_requires=[
          
      ],
      url='https://github.com/parnell/pymin-reqs',
      packages=['pymin_reqs'],
      entry_points = {
              'console_scripts': [
                  'pymin_reqs = pymin_reqs.pymin_reqs:main'
              ],
          },
     )
