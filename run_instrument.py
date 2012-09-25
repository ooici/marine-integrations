#!/Users/deverett/tools/virtenvs/ion27/bin/python

import sys
sys.path[0:0] = [
    '/Users/deverett/src/ucsd/marine-integrations/extern/coi-services',
    '/Users/deverett/src/ucsd/marine-integrations',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/utilities-2012.9.13.15-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/ntplib-0.3.0-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/snakefood-1.4-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/gitpy-0.6.0-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/pyparsing-1.5.6-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/elasticpy-0.10-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/netCDF4-1.0-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/Pydap-3.1.RC1-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/setuptools-0.6c11-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/matplotlib-1.1.0-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/seawater-2.0.1-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/requests-0.13.5-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/WebTest-1.4.0-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/python_dateutil-1.5-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/Flask-0.8-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/extern/pyon',
    '/Users/deverett/src/ucsd/marine-integrations/extern/coverage-model',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/graypy-0.2.6-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/develop-eggs/PyYAML-3.10-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/simplejson-2.1.6-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/PasteDeploy-1.5.0-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/PasteScript-1.7.5-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/Paste-1.7.5.1-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/Genshi-0.6-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/httplib2-0.7.6-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/numpy-1.6.2-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/WebOb-1.2.2-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/Jinja2-2.6-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/Werkzeug-0.8.3-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/lxml-2.3.4-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/python_gevent_profiler-0.2-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/develop-eggs/h5py-2.0.1-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/ndg_xacml-0.5.1-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/mock-0.8.0-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/readline-6.2.1-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/ipython-0.11-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/nose-1.1.2-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/coverage-3.5.2-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/M2Crypto-0.21.1_pl1-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/python_daemon-1.6-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/CouchDB-0.8-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/zope.interface-4.0.1-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/gevent_zeromq-0.2.5-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/develop-eggs/pyzmq-2.2.0-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/pika-0.9.5patch3-py2.7.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/setproctitle-1.1.2-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/msgpack_python-0.1.13-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/develop-eggs/gevent-0.13.7-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/greenlet-0.4.0-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/numexpr-2.0.1-py2.7-macosx-10.6-intel.egg',
    '/Users/deverett/src/ucsd/marine-integrations/eggs/lockfile-0.9.1-py2.7.egg',
    ]



import os
os.environ['PATH'] = os.pathsep.join([os.path.join('/Users/deverett/src/ucsd/marine-integrations/parts/port_agent', 'bin'), os.environ.get('PATH', '')])
# print os.environ.get('PATH')
from mi.core.log import LoggerManager
LoggerManager()

import mi.idk.scripts.run_instrument

if __name__ == '__main__':
    sys.exit(mi.idk.scripts.run_instrument.run())
