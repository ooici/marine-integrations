import binascii
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
stream_handle = open('mi/dataset/driver/moas/gl/adcpa/resource/LA101636.PD0', 'rb')

position_callback_value = None
publish_callback_value = None

parser = AdcpaParser(config, position, stream_handle, pos_callback, pub_callback)

particles = parser.get_records(10)

stream_handle.close()

jdata = json.loads(particles[0].generate())
values = {}
for value in jdata['values']:
    values[value['value_id']] = value['value']

