import gevent
import json
from nose.plugins.attrib import attr

from mi.core.log import get_logger

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.adcpa import AdcpaParser, ADCPA_PD0_PARSED_DataParticle, StateKey

log = get_logger()


def pos_callback(pos):
    """ Call back method to watch what comes in via the position callback """
    position_callback_value = pos
    return position_callback_value


def pub_callback(pub):
    """ Call back method to watch what comes in via the publish callback """
    publish_callback_value = pub
    return publish_callback_value

config = {DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcpa',
          DataSetDriverConfigKeys.PARTICLE_CLASS: 'ADCPA_PD0_PARSED_DataParticle'
          }

position = {StateKey.POSITION: 0}
position_callback_value = None
publish_callback_value = None

with open('mi/dataset/driver/moas/gl/adcpa/resource/LA101636.PD0', 'rb') as stream_handle:
    parser = AdcpaParser(config, position, stream_handle, pos_callback, pub_callback)

    particles = parser.get_records(10)
    print position, parser._state

    internal_timestamp = []
    ensemble_start_time = []
    echo_intensity_beam1 = []
    correlation_magnitude_beam1 = []
    error_velocity = []
    offset_data_types = []
    percent_bad_beams = []
    water_velocity_east = []
    water_velocity_north = []
    water_velocity_up = []

    for particle in particles:

        jdata = particle.generate_dict()
        internal_timestamp.append(jdata['internal_timestamp'])

        values = {}
        for value in jdata['values']:
            values[value['value_id']] = value['value']

        ensemble_start_time.append(values['ensemble_start_time'])
        echo_intensity_beam1.append(values['echo_intensity_beam1'])
        correlation_magnitude_beam1.append(values['correlation_magnitude_beam1'])
        error_velocity.append(values['error_velocity'])
        offset_data_types.append(values['offset_data_types'])
        percent_bad_beams.append(values['percent_bad_beams'])
        water_velocity_east.append(values['water_velocity_east'])
        water_velocity_north.append(values['water_velocity_north'])
        water_velocity_up.append(values['water_velocity_up'])

    particles = parser.get_records(1)
    print position, parser._state
    particles = parser.get_records(1)
    print position, parser._state
    particles = parser.get_records(1)
    print position, parser._state
    particles = parser.get_records(1)
    print position, parser._state
    particles = parser.get_records(1)
    print position, parser._state
    particles = parser.get_records(1)
    print position, parser._state
