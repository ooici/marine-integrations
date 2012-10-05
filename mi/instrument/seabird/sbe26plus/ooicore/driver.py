import mi.instrument.seabird.sbe26plus.driver
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue



# Packet config
STREAM_NAME_PARSED = DataParticleValue.PARSED
STREAM_NAME_RAW = DataParticleValue.RAW
PACKET_CONFIG = [STREAM_NAME_PARSED, STREAM_NAME_RAW]