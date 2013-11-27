"""
polling utilities -- general polling for condition, polling for file to appear in a directory
"""
import os
import glob
from threading import Thread
from gevent.event import Event
from ooi.logging import log
from Queue import Queue

class ConditionPoller(Thread):
    """
    generic polling mechanism: every interval seconds, check if condition returns a true value. if so, pass the value to callback
    if condition or callback raise exception, stop polling.
    """
    def __init__(self, condition, condition_callback, exception_callback, interval):
        self.polling_interval = interval
        self._shutdown_now = Event()
        self._condition = condition
        self._callback = condition_callback
        self._on_exception = exception_callback
        super(ConditionPoller,self).__init__()
        log.debug("ConditionPoller: __init__")

    def shutdown(self):
        log.debug("Shutting down poller: %s", self._shutdown_now)
        self.is_shutting_down = True
        self._shutdown_now.set()

    def run(self):
        try:
            while not self._shutdown_now.is_set():
                self._check_condition()
                self._shutdown_now.wait(self.polling_interval)
        except:
            log.error('thread failed', exc_info=True)
    def _check_condition(self):
        try:
            value = self._condition()
            if value:
                self._callback(value)
        except Exception as e:
            log.debug('stopping poller after exception', exc_info=True)
            self.shutdown()
            if self._on_exception:
                self._on_exception(e)
    def start(self):
        super(ConditionPoller,self).start()

class DirectoryPoller(ConditionPoller):
    """
    poll for new files added to a directory that match a wildcard pattern.
    expects files to be added only, and added in ASCII order.
    """
    def __init__(self, directory, wildcard, callback, exception_callback=None, interval=1):
        self._directory = directory
        self._path = directory + '/' + wildcard
        self._last_filename = None
        super(DirectoryPoller,self).__init__(self._check_for_files, callback, exception_callback, interval)

    def _check_for_files(self):
        if not os.path.isdir(self._directory):
            raise ValueError('%s is not a directory' % self._directory)

        filenames = glob.glob(self._path)
        filenames.sort()
        # files, but no change since last time
        if self._last_filename and filenames and filenames[-1]==self._last_filename:
            return None
        # no files yet, just like last time
        if not self._last_filename and not filenames:
            return None
        if self._last_filename:
            position = filenames.index(self._last_filename) # raises ValueError if file was removed
            out = filenames[position+1:]
        else:
            out = filenames
        self._last_filename = filenames[-1]
        log.trace('found files: %r', out)
        return out

class BlockingDirectoryIterator(object):
    """
    iterator that blocks and yields new files added to a directory

    use like this:
        for filename in PollingDirectoryIterator('/tmp','A*.DAT').get_files():
            print filename
    """
    def __init__(self, directory, wildcard, interval=1):
        self._values = Queue()
        self._exception = None
        self._ready = Event()
        self._poller = DirectoryPoller(directory, wildcard, self._on_condition, self._on_exception, interval)
        self._poller.start()
    def __iter__(self):
        return self
    def get_files(self):
        while True:
            # could have exception or list of filenames
            out = self._values.get()
            if isinstance(out, Exception):
                raise out
            else:
                yield out
    def cancel(self):
        self._poller.shutdown()
    def _on_condition(self, filenames):
        for file in filenames:
            self._values.put(file)
    def _on_exception(self, exception):
        self._values.put(exception)
