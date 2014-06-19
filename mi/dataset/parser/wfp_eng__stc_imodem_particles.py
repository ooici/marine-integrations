#!/usr/bin/env python

"""
@package mi.dataset.parser.wfp_eng__stc_imodem_particles
@file marine-integrations/mi/dataset/parser/wfp_eng__stc_imodem_particles.py
@author Mark Worden
@brief Particles for the WFP_ENG__STC_IMODEM dataset driver
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

import struct

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.exceptions import SampleException
from mi.dataset.parser.WFP_E_file_common import SAMPLE_BYTES, PROFILE_MATCHER, WFP_E_COASTAL_FLAGS_HEADER_MATCHER


class DataParticleType(BaseEnum):
    START_TIME_RECOVERED = 'wfp_eng_stc_imodem_start_time_recovered'
    STATUS_RECOVERED = 'wfp_eng__stc_imodem_status_recovered'
    ENGINEERING_RECOVERED = 'wfp_eng_stc_imodem_engineering_recovered'
    START_TIME_TELEMETERED = 'wfp_eng_stc_imodem_start_time'
    STATUS_TELEMETERED = 'wfp_eng_stc_imodem_status'
    ENGINEERING_TELEMETERED = 'wfp_eng_stc_imodem_engineering'


class WfpEngStcImodemStatusDataParticleKey(BaseEnum):
    INDICATOR = 'wfp_indicator'
    RAMP_STATUS = 'wfp_ramp_status'
    PROFILE_STATUS = 'wfp_profile_status'
    SENSOR_STOP = 'wfp_sensor_stop'
    PROFILE_STOP = 'wfp_profile_stop'


class WfpEngStcImodemStatusDataParticle(DataParticle):
    """
    Class for building a WfpEngStcImodemStatusDataParticle
    """

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        match_prof = PROFILE_MATCHER.match(self.raw_data)

        if not match_prof:
            raise SampleException("WfpEngStcImodemStatusDataParticle: No regex match of parsed sample data: [%s]",
                                  self.raw_data)

        try:
            fields_prof = struct.unpack('>ihhII', match_prof.group(0))
            indicator = int(fields_prof[0])
            ramp_status = int(fields_prof[1])
            profile_status = int(fields_prof[2])
            profile_stop = int(fields_prof[3])
            sensor_stop = int(fields_prof[4])
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match_prof.group(0)))

        result = [self._encode_value(WfpEngStcImodemStatusDataParticleKey.INDICATOR, indicator, int),
                  self._encode_value(WfpEngStcImodemStatusDataParticleKey.RAMP_STATUS, ramp_status, int),
                  self._encode_value(WfpEngStcImodemStatusDataParticleKey.PROFILE_STATUS, profile_status,
                                     int),
                  self._encode_value(WfpEngStcImodemStatusDataParticleKey.SENSOR_STOP, sensor_stop, int),
                  self._encode_value(WfpEngStcImodemStatusDataParticleKey.PROFILE_STOP, profile_stop, int)]
        log.debug('WfpEngStcImodemStatusDataParticle: particle=%s', result)
        return result


class WfpEngStcImodemStatusRecoveredDataParticle(WfpEngStcImodemStatusDataParticle):
    """
    Class for building a WfpEngStcImodemStatusRecoveredDataParticle
    """

    _data_particle_type = DataParticleType.STATUS_RECOVERED


class WfpEngStcImodemStatusTelemeteredDataParticle(WfpEngStcImodemStatusDataParticle):
    """
    Class for building a WfpEngStcImodemStatusTelemeteredDataParticle
    """

    _data_particle_type = DataParticleType.STATUS_TELEMETERED


class WfpEngStcImodemStartDataParticleKey(BaseEnum):
    SENSOR_START = 'wfp_sensor_start'
    PROFILE_START = 'wfp_profile_start'


class WfpEngStcImodemStartDataParticle(DataParticle):
    """
    Class for building a WfpEngStcImodemStartDataParticle
    """

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        match = WFP_E_COASTAL_FLAGS_HEADER_MATCHER.match(self.raw_data)

        if not match:
            raise SampleException(
                "WfpEngStcImodemStartDataParticle: No regex match of parsed sample data: [%s]",
                self.raw_data)

        try:
            fields = struct.unpack('>II', match.group(2))
            sensor_start = int(fields[0])
            profile_start = int(fields[1])
            log.debug('Unpacked sensor start %d, profile start %d', sensor_start, profile_start)
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))

        result = [self._encode_value(WfpEngStcImodemStartDataParticleKey.SENSOR_START, sensor_start, int),
                  self._encode_value(WfpEngStcImodemStartDataParticleKey.PROFILE_START, profile_start, int)]
        log.debug('WfpEngStcImodemStartDataParticle: particle=%s', result)
        return result


class WfpEngStcImodemStartRecoveredDataParticle(WfpEngStcImodemStartDataParticle):
    """
    Class for building a WfpEngStcImodemStartRecoveredDataParticle
    """

    _data_particle_type = DataParticleType.START_TIME_RECOVERED


class WfpEngStcImodemStartTelemeteredDataParticle(WfpEngStcImodemStartDataParticle):
    """
    Class for building a WfpEngStcImodemStartTelemeteredDataParticle
    """

    _data_particle_type = DataParticleType.START_TIME_TELEMETERED


class WfpEngStcImodemEngineeringDataParticleKey(BaseEnum):
    TIMESTAMP = 'wfp_timestamp'
    PROF_CURRENT = 'wfp_prof_current'
    PROF_VOLTAGE = 'wfp_prof_voltage'
    PROF_PRESSURE = 'wfp_prof_pressure'


class WfpEngStcImodemEngineeringDataParticle(DataParticle):
    """
    Class for parsing data from the WFP_ENG__STC_IMODEM data set
    """

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        # data sample can be any bytes, no need to check regex
        if len(self.raw_data) < SAMPLE_BYTES:
            raise SampleException(
                "WfpEngStcImodemEngineeringDataParticle: Not enough bytes of sample data: [%s]",
                self.raw_data)
        try:
            fields = struct.unpack('>Ifff', self.raw_data[:16])
            timestamp = int(fields[0])
            profile_current = float(fields[1])
            profile_voltage = float(fields[2])
            profile_pressure = float(fields[3])
        except(ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data[:16]))

        result = [self._encode_value(WfpEngStcImodemEngineeringDataParticleKey.TIMESTAMP,
                                     timestamp, int),
                  self._encode_value(WfpEngStcImodemEngineeringDataParticleKey.PROF_CURRENT,
                                     profile_current, float),
                  self._encode_value(WfpEngStcImodemEngineeringDataParticleKey.PROF_VOLTAGE,
                                     profile_voltage, float),
                  self._encode_value(WfpEngStcImodemEngineeringDataParticleKey.PROF_PRESSURE,
                                     profile_pressure, float)]
        log.debug('WfpEngStcImodemEngineeringDataParticle: particle=%s', result)
        return result


class WfpEngStcImodemEngineeringRecoveredDataParticle(WfpEngStcImodemEngineeringDataParticle):
    """
    Class for building a WfpEngStcImodemEngineeringRecoveredDataParticle
    """

    _data_particle_type = DataParticleType.ENGINEERING_RECOVERED


class WfpEngStcImodemEngineeringTelemeteredDataParticle(WfpEngStcImodemEngineeringDataParticle):
    """
    Class for building a WfpEngStcImodemEngineeringTelemeteredDataParticle
    """

    _data_particle_type = DataParticleType.ENGINEERING_TELEMETERED

