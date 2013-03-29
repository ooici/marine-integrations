#!/usr/bin/env python

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

import os
import sys

# Add /usr/local/include to the path for macs, fixes easy_install for several packages (like gevent and pyyaml)
if sys.platform == 'darwin':
    os.environ['C_INCLUDE_PATH'] = '/usr/local/include'

version = '0.2.1'

setup(  name = 'marine-integrations',
        version = version,
        description = 'OOI ION Marine Integrations',
        url = 'https://github.com/ooici/marine-integrations',
        download_url = 'http://sddevrepo.oceanobservatories.org/releases/',
        license = 'Apache 2.0',
        author = 'Michael Meisinger',
        author_email = 'mmeisinger@ucsd.edu',
        keywords = ['ooici','ioncore', 'pyon', 'coi'],
        packages = find_packages(),
        dependency_links = [
            'http://sddevrepo.oceanobservatories.org/releases/',
            'https://github.com/ooici/pyon/tarball/master#egg=pyon',
            #'https://github.com/ooici/utilities/tarball/v2012.12.12#egg=utilities-2012.12.12',
        ],
        test_suite = 'pyon',
        entry_points = {
            'console_scripts' : [
                'package_driver=ion.idk.scripts.package_driver:run',
                'start_driver=ion.idk.scripts.start_driver:run',
                'test_driver=ion.idk.scripts.test_driver:run',
            ],
        },
        install_requires = [
            'gitpy==0.6.0',
            'snakefood==1.4',
            'ntplib>=0.1.9',
            'apscheduler==2.1.0',
            #'utilities',
        ],
     )
