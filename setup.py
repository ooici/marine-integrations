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

version = '0.1'

setup(  name = 'marine-integrations',
        version = version,
        description = 'OOI ION Marine Integrations',
        url = 'https://github.com/ooici/marine-integrations',
        download_url = 'http://ooici.net/releases',
        license = 'Apache 2.0',
        author = 'Michael Meisinger',
        author_email = 'mmeisinger@ucsd.edu',
        keywords = ['ooici','ioncore', 'pyon', 'coi'],
        packages = find_packages(),
        dependency_links = [
            'http://ooici.net/releases',
            'https://github.com/ooici/pyon/tarball/master#egg=pyon'
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
            'pyon',
            'coi-services',
        ],
     )
