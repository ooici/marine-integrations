"""
@file mi/idk/instrument_agent_client.py
@author Bill French
@brief Helper class start the instrument_agent_client
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import os
import sys
import nose
import signal
import subprocess
import time

from mi.core.log import log

from mi.idk.config import Config

from mi.idk.exceptions import TestNoDeployFile

from pyon.util.int_test import IonIntegrationTestCase
from pyon.container.cc import Container
from pyon.util.context import LocalContextMixin

from interface.services.icontainer_agent import ContainerAgentClient
from pyon.agent.agent import ResourceAgentClient

DEFAULT_DEPLOY = 'res/deploy/r2deploy.yml'

class InstrumentAgentClient(object):
    """
    Launch a capability container and instrument agent client
    """
    container = Container.instance

    class FakeProcess(LocalContextMixin):
        """
        A fake process used because the test case is not an ion process.
        """
    name = ''
    id=''
    process_type = ''

    def start_client(self, name, module, cls, config, resource_id, deploy_file = DEFAULT_DEPLOY):
        """
        @brief Start up the instrument agent client
        """
        self.start_container(deploy_file=deploy_file)

        # Start instrument agent.
        log.debug("Starting Instrument Agent Client")
        container_client = ContainerAgentClient(node=self.container.node,
            name=self.container.name)

        instrument_agent_pid = container_client.spawn_process(
            name=name,
            module=module,
            cls=cls,
            config=config)
        log.info('Agent pid=%s.', instrument_agent_pid)

        ia_client = ResourceAgentClient(resource_id, process=self.FakeProcess())

        log.info('Got ia client %s.', str(ia_client))

        self.instrument_agent_client = ia_client


    def start_container(self, deploy_file = DEFAULT_DEPLOY):
        """
        @brief Launch the instrument agent
        """
        log.info("Startup Instrument Agent")

        self.start_couchdb()
        self.start_rabbitmq_server()

        # No need to start the container twice
        self.container = Container.instance
        if self.container:
            return

        if not os.path.exists(deploy_file):
            raise TestNoDeployFile(deploy_file)

        # Derive a special test case so we can instantiate a testcase object.
        # then we can run start_container which initialized the capability container
        # There will eventually be a better way to do this I'm sure.
        class _StartContainer(IonIntegrationTestCase):
            def runTest(self): pass

        testcase = _StartContainer()

        # Start container.
        log.info("Starting the capability container")
        testcase._start_container()
        container = testcase.container

        log.debug( "Capability container id: %s" % testcase.container.id )

        # Bring up services in a deploy file (no need to message)
        log.info("Initialize container with %s" % deploy_file)
        container.start_rel_from_url(deploy_file)

        self.container = container

    def stop_container(self):
        log.info("Stop the instrument agent")

        if not self.container:
            log.warn("Container not running.")
            return

        # Derive a special test case so we can instantiate a testcase object.
        # then we can run start_container which initiallized the capability container
        class _StartContainer(IonIntegrationTestCase):
            def runTest(self): pass

        testcase = _StartContainer()
        testcase.container = self.container
        testcase._stop_container()

        self.stop_couchdb()
        self.stop_rabbitmq_server()

        self.container = None

    def start_couchdb(self):
        """
        @brief Start the instrument agent
        """
        # Do nothing if rabbit is already running
        pid = self._read_pidfile(self._pid_filename("couchdb"))
        if pid:
            return

        cmd = Config().get("couchdb")
        if not cmd:
            raise MissingConfig("couchdb")

        self._run_process(cmd, '-b', self._pid_filename("couchdb"), False)

    def stop_couchdb(self):
        """
        @brief Stop the instrument agent
        """
        log.info("Stopping CouchDB")
        pid = self._read_pidfile(self._pid_filename("couchdb"))

        if not pid > 0:
            return

        cmd = Config().get("couchdb")
        if not cmd:
            raise MissingConfig("couchdb")

        self._run_process(cmd, '-k')

        os.remove(self._pid_filename("couchdb"))

    def start_rabbitmq_server(self):
        """
        @brief Start the instrument agent
        """
        # Do nothing if rabbit is already running
        pid = self._read_pidfile(self._pid_filename("rabbitmq"))
        if pid:
            return

        cmd = Config().get("rabbitmq")
        if not cmd:
            raise MissingConfig("rabbitmq")

        # The rabbit startup file is a script that starts the erl program.  If
        # erl isn't in the path the server doesn't start.
        # TODO: put this in a config parameter
        os.environ['PATH'] = "%s:%s" % (os.environ['PATH'], "/usr/local/bin")
        self._run_process(cmd, '', self._pid_filename("rabbitmq"), False)

    def stop_rabbitmq_server(self):
        """
        @brief Stop the instrument agent
        """
        log.info("Stopping RabbitMQ")
        pid = self._read_pidfile(self._pid_filename("rabbitmq"))

        if not pid > 0:
            return

        log.debug("-- send sigterm to pid %s", pid)
        try:
            os.kill(pid, signal.SIGTERM)
        except:
            pass

        os.remove(self._pid_filename("rabbitmq"))

    def _run_process(self, cmd, args = None, pidfile = None, raise_error = True):
        """
        @brief Start an external process and store the PID
        """
        if not args: args = ''
        name = os.path.basename(cmd)
        log.info("Start process: %s" % name)
        log.debug( "cmd: %s %s" % (cmd, args))

        if not os.path.exists(cmd):
            raise MissingExecutable(cmd)

        command_line = "%s %s" % (cmd, args);

        process = subprocess.Popen(command_line, shell=True)
        time.sleep(1)

        log.debug("Process pid: %d" % process.pid )
        if process.pid > 0:
            if pidfile:
                self._write_pidfile(process.pid, pidfile)
        else:
            log.error( "Failed to launch application: %s " % command_line)
            if(raise_error):
                raise FailedToLaunch(command_line)


    def _write_pidfile(self, pid, pidfile):
        log.debug("write pid %d to file %s" % (pid, pidfile))
        outfile = open(pidfile, "w")
        outfile.write("%s" % pid)
        outfile.close()

    def _read_pidfile(self, pidfile):
        log.debug( "read pidfile %s" % pidfile)
        try:
            infile = open(pidfile, "r")
            pid = infile.read()
            infile.close()
        except IOError, e:
            return None

        if pid:
            return int(pid)
        else:
            return 0

    def _pid_filename(self, name):
        return "%s/%s_%d.pid" % (Config().get('tmp_dir'), name, os.getpid())

