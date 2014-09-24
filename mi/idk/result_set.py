#!/usr/bin/env python

"""
@file coi-services/mi/idk/result_set.py
@author Bill French
@brief Read a result set file and use the data to verify
data particles.

Usage:

from mi.core.log import log

rs = ResultSet(result_set_file_path)
if not rs.verify(particles):
    log.info("Particle verified")
else:
    log.error("Particle validate failed")
    log.error(rs.report())

Result Set File Format:
  result files are yml formatted files with a header and data section.
  the data is stored in record elements with the key being the parameter name.
     - two special fields are internal_timestamp and _index.
     - internal timestamp can be input in text string or ntp float format

eg.

# Result data for verifying particles. Comments are ignored.

header:
  particle_object: CtdpfParserDataParticleKey
  particle_type: ctdpf_parsed

data:
  -  _index: 1
     internal_timestamp: 07/26/2013 21:01:03
     temperature: 4.1870
     conductivity: 10.5914
     pressure: 161.06
     oxygen: 2693.0
  -  _index: 2
     internal_timestamp: 07/26/2013 21:01:04
     temperature: 4.1872
     conductivity: 10.5414
     pressure: 161.16
     oxygen: 2693.1

If a driver returns multiple particle types, the particle type must be specified in each particle

header:
  particle_object: 'MULTIPLE'
  particle_type: 'MULTIPLE'

data:
  -  _index: 1
     particle_object: CtdpfParser1DataParticleKey
     particle_type: ctdpf_parsed_1
     internal_timestamp: 07/26/2013 21:01:03
     temperature: 4.1870
     conductivity: 10.5914
     pressure: 161.06
     oxygen: 2693.0
  -  _index: 2
     particle_object: CtdpfParser2DataParticleKey
     particle_type: ctdpf_parsed_2
     internal_timestamp: 07/26/2013 21:01:04
     temperature: 4.1872
     conductivity: 10.5414
     pressure: 161.16
     oxygen: 2693.1


"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import re
import yaml
import ntplib
import time
from dateutil import parser

from mi.core.instrument.data_particle import DataParticle

from mi.core.log import get_logger ; log = get_logger()

DATE_PATTERN = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$'
DATE_MATCHER = re.compile(DATE_PATTERN)

class ResultSet(object):
    """
    Result Set object
    Read result set files and compare to parsed particles.
    """
    def __init__(self, result_file_path):
        self.yaml = dict()

        log.debug("read result file: %s" % result_file_path)
        stream = file(result_file_path, 'r')
        result_set = yaml.load(stream)

        self._set_result_set(result_set)

        self._clear_report()

    def verify(self, particles):
        """
        Verify particles passed in against result set read
        in the ctor.

        Ensure:
          - Verify particles as a set
          - Verify individual particle data

        store verification result in the object and
        return success or failure.
        @param particls: list of particles to verify.
        @return True if verification successful, False otherwise
        """
        self._clear_report()
        result = True

        if self._verify_set(particles):
            result = self._verify_particles(particles)
        else:
            result = False

        if not result:
            log.error("Failed verification: \n%s", self.report())

        return result

    def report(self):
        """
        Return an ascii formatted verification failure report.
        @return string report
        """
        if len(self._report):
            return "\n".join(self._report)
        else:
            return None

    ###
    #   Helpers
    ###
    def _add_to_report(self, messages, indent = 0):
        """
        Add a message to the report buffer, pass an indent factor to
        indent message in the ascii report.
        """
        if not isinstance(messages, list): messages = [messages]

        for message in messages:
            ind = ""
            for i in range(0, indent):
                ind += "    "
            self._report.append("%s%s" %(ind, message))
            log.warn(message)

    def _clear_report(self):
        """
        Add a message to the report buffer, pass an indent factor to
        indent message in the ascii report.
        """
        self._report = []

    def _set_result_set(self, result_set):
        """
        Take data from yaml file and store it in internal objects for
        verifying data.  Raise an exception on error.
        """
        log.trace("Parsing result set header: %s", result_set)

        self._result_set_header = result_set.get("header")
        if not self._result_set_header: raise IOError("Missing result set header")
        log.trace("Header: %s", self._result_set_header)

        if self._result_set_header.get("particle_object") is None:
            IOError("header.particle_object not defined")

        if self._result_set_header.get("particle_type") is None:
            IOError("header.particle_type not defined")

        self._result_set_data = {}
        data = result_set.get("data")
        if not data: raise IOError("Missing result set data")

        for particle in data:
            index = particle.get("_index")
            if index is None:
                log.error("Particle definition missing _index: %s", particle)
                raise IOError("Particle definition missing _index")

            if self._result_set_data.get(index) is not None:
                log.error("Duplicate particle definition for _index %s: %s", index, particle)
                raise IOError("Duplicate definition found for index: %s"% index)

            self._result_set_data[index] = particle
            log.trace("Result set data: %s", self._result_set_data)

    def _verify_set(self, particles):
        """
        Verify the particles as a set match what we expect.
        - All particles are of the expected type
        - Check particle count
        """
        errors = []

        if len(self._result_set_data) != len(particles):
            errors.append("result set records != particles to verify (%d != %d)" %
                          (len(self._result_set_data), len(particles)))

        # if this driver returns multiple particle classes, type checking happens
        # for each particle in _get_particle_data_errors
        if self._result_set_header.get("particle_object") != 'MULTIPLE' and \
        self._result_set_header.get("particle_type") != 'MULTIPLE':
            for particle in particles:
                if not self._verify_particle_type(particle):
                    log.error("particle type mismatch: %s", particle)
                    errors.append('particle type mismatch')

        if len(errors):
            self._add_to_report("Header verification failure")
            self._add_to_report(errors, 1)
            return False

        return True

    def _verify_particles(self, particles):
        """
        Verify data in the particles individually.
        - Verify order based on _index
        - Verify parameter data values
        - Verify there are extra or missing parameters
        """
        result = True
        index = 1
        for particle in particles:
            particle_def = self._result_set_data.get(index)
            errors = []

            # No particle definition, we fail
            if particle_def is None:
                errors.append("no particle result defined for index %d" % index)

            # Otherwise lets do some validation
            else:
                errors += self._get_particle_header_errors(particle, particle_def)
                errors += self._get_particle_data_errors(particle, particle_def)

            if len(errors):
                self._add_to_report("Failed particle validation for index %d" % index)
                self._add_to_report(errors, 1)
                result = False

            index += 1

        return result

    def _verify_particle_type(self, particle):
        """
        Verify that the object is a DataParticle and is the
        correct type.
        """
        if isinstance(particle, dict):
            return True

        expected = self._result_set_header['particle_object']

        cls = particle.__class__.__name__

        if not issubclass(particle.__class__, DataParticle):
            log.error("type not a data particle")

        if expected != cls:
            log.error("type mismatch: %s != %s", expected, cls)
            return False

        return True

    def _get_particle_header_errors(self, particle, particle_def):
        """
        Verify all parameters defined in the header:
        - Stream type
        - Internal timestamp
        """
        errors = []
        particle_dict = self._particle_as_dict(particle)
        particle_timestamp = particle_dict.get('internal_timestamp')
        expected_time = particle_def.get('internal_timestamp')
        allow_diff = .000001

        # Verify the timestamp
        if particle_timestamp and not expected_time:
            errors.append("particle_timestamp defined in particle, but not expected")
        elif not particle_timestamp and expected_time:
            errors.append("particle_timestamp expected, but not defined in particle")

        elif particle_timestamp:
            if isinstance(expected_time, str):
                expected = self._string_to_ntp_date_time(expected_time)
            else:
                # if not a string, timestamp should alread be in ntp
                expected = expected_time
            ts_diff =  abs(particle_timestamp - expected)
            log.debug("verify timestamp: abs(%s - %s) = %s", expected, particle_timestamp, ts_diff)

            if ts_diff > allow_diff:
                errors.append("expected internal_timestamp mismatch, %.9f != %.9f (%.9f)" %
                              (expected, particle_timestamp, ts_diff))

        # verify the stream name, unless multiple are returned, type checking is done
        # in get_particle_data_errors if so
        particle_stream = particle_dict['stream_name']
        if self._result_set_header['particle_type'] != 'MULTIPLE':
            expected_stream =  self._result_set_header['particle_type']
            if particle_stream != expected_stream:
                errors.append("expected stream name mismatch: %s != %s" %
                              (expected_stream, particle_stream))

        return errors

    def _get_particle_data_errors(self, particle, particle_def):
        """
        Verify that all data parameters are present and have the
        expected value
        """
        errors = []
        particle_dict = self._particle_as_dict(particle)
        log.debug("Particle to test: %s", particle_dict)
        log.debug("Particle definition: %s", particle_def)
        particle_values = particle_dict['values']

        # particle object and particle type keys will only be present for drivers
        # returning multiple particle types
        if 'particle_object' in particle_def:
            expected_object = particle_def.get('particle_object')
            expected_type = particle_def.get('particle_type', None)

            # particle is either a class or dictionary, if it is a
            # dictionary there is no class to compare
            if not isinstance(particle, dict):
                # particle is an actual class, check that the class matches
                cls = particle.__class__.__name__
                if not issubclass(particle.__class__, DataParticle):
                    errors.append("Particle class %s is not a subclass of DataParticle" %
                                  particle.__class__)

                if expected_object != cls:
                    errors.append("Class mismatch, expected: %s, received: %s" %
                                  (expected_object, cls))

            particle_stream = particle_dict['stream_name']
            if particle_stream != expected_type:
                log.debug("Stream type mismatch, expected: %s, received: %s" % (expected_type, particle_stream))
                errors.append("Stream type mismatch, expected: %s, received: %s" % (expected_type, particle_stream))

        expected_keys = []
        for (key, value) in particle_def.items():
            if(key not in ['_index', '_new_sequence', 'internal_timestamp', 'particle_object', 'particle_type']):
                expected_keys.append(key)

        particle_keys = []
        pv = {}
        for value in particle_values:
            particle_keys.append(value['value_id'])
            pv[value['value_id']] = value['value']

        if sorted(expected_keys) != sorted(particle_keys):
            errors.append("expected / particle keys mismatch: %s != %s" %
                          (sorted(expected_keys), sorted(particle_keys)))

        else:
            for key in expected_keys:
                expected_value = particle_def[key]
                particle_value = pv[key]
                log.debug("Verify value for '%s'", key)
                e = self._verify_value(expected_value, particle_value)
                if e:
                    errors.append("'%s' %s"  % (key, e))

        return errors

    def _verify_value(self, expected_value, particle_value):
        """
        Verify a value matches what we expect.  If the expected value (from the yaml)
        is a dict then we expect the value to be in a 'value' field.  Otherwise just
        use the parameter as a raw value.

        when passing a dict you can specify a 'round' factor.
        """
        if isinstance(expected_value, dict):
            ex_value = expected_value['value']
            round_factor = expected_value.get('round')
        else:
            ex_value = expected_value
            round_factor = None

        if ex_value is None:
            log.debug("No value to compare, ignoring")
            return None

        if round_factor is not None and particle_value is not None:
            particle_value = round(particle_value, round_factor)
            log.debug("rounded value to %s", particle_value)

        if ex_value != particle_value:
            return "value mismatch, %s != %s (decimals may be rounded)" % (ex_value, particle_value)

        return None

    def _string_to_ntp_date_time(self, datestr):
        """
        Extract an ntp date from a ISO8601 formatted date string.
        @param str an ISO8601 formatted string containing date information
        @retval an ntp date number (seconds since jan 1 1900)
        @throws InstrumentParameterException if datestr cannot be formatted to
        a date.
        """
        if not isinstance(datestr, str):
            raise IOError('Value %s is not a string.' % str(datestr))
        if not DATE_MATCHER.match(datestr):
            raise ValueError("date string not in ISO8601 format YYYY-MM-DDTHH:MM:SS.SSSSZ")

        try:
            # This assumes input date string are in UTC (=GMT)
            if datestr[-1:] != 'Z':
                datestr += 'Z'

            # the parsed date time represents a GMT time, but strftime
            # does not take timezone into account, so these are seconds from the
            # local start of 1970
            local_sec = float(parser.parse(datestr).strftime("%s.%f"))
            # remove the local time zone to convert to gmt (seconds since gmt jan 1 1970)
            gmt_sec = local_sec - time.timezone
            # convert to ntp (seconds since gmt jan 1 1900)
            timestamp = ntplib.system_to_ntp_time(gmt_sec)

        except ValueError as e:
            raise ValueError('Value %s could not be formatted to a date. %s' % (str(datestr), e))

        log.debug("converting time string '%s', unix_ts: %s ntp: %s", datestr, gmt_sec, timestamp)

        return timestamp

    def _particle_as_dict(self, particle):
        if isinstance(particle, dict):
            return particle

        return particle.generate_dict()
