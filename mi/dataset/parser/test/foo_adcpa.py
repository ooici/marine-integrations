import gevent
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

def pub_callback(pub):
    """ Call back method to watch what comes in via the publish callback """
    publish_callback_value = pub
 

config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcpa',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'ADCPA_PD0_PARSED_DataParticle'
        }

position = {StateKey.POSITION: 0}
stream_handle = open('mi/dataset/driver/moas/gl/adcpa/resource/LA101636.PD0','rb')

position_callback_value = None
publish_callback_value = None

parser = AdcpaParser(config, position, stream_handle, pos_callback, pub_callback)


stream_handle.close()



import re
from functools import partial
from mi.core.instrument.chunker import BinaryChunker, StringChunker

ADCPA_PD0_PARSED_REGEX = (
    b'(\x7f\x7f[\x00-\xFF]{2}\x00[\x06|\x07]{1})'  # find the start of the next ensemble, of the EOF
)
ADCPA_PD0_PARSED_MATCHER = re.compile(ADCPA_PD0_PARSED_REGEX, re.DOTALL)

f = open('mi/dataset/driver/moas/gl/adcpa/resource/LA101636.PD0','rb')
f.seek(0)
schunk = StringChunker(partial(StringChunker.regex_sieve_function, regex_list=[ADCPA_PD0_PARSED_MATCHER]))

data = f.read(1024)
schunk.add_chunk(data, 0.0)
i = 0.0
while len(data) > 0:
    data = f.read(1024)
    schunk.add_chunk(data, i)
    i += 1

f.close()

(time, result, start, end) = schunk.get_next_data_with_index(True)
while time is not None:
    print time, start, end
    (time, result, start, end) = schunk.get_next_data_with_index(True)


