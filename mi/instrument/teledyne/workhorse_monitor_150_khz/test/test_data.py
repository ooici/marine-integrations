from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import NEWLINE

SAMPLE_RAW_DATA1 = \
"\x7F\x7F\xF0\x02\x00\x06\x12\x00\x4D\x00\x8E\x00\x80\x01\xFA\x01\x74\x02\x00\x00\x32\x28\xC9\x41\x00\x0D\x04\x1E\x0A\x00\x20\x03\x00\x00\x01\xFF\x09\x00\x0F\x27\x00\x00\x00\x1F\x00\x00\x00\x00\x7D\x3D\x71\x03\x61\x03\x05\x06\x32\x00\x62\x00\x28\x00\x00\x06\xFE\xD0\xFC\x09\x01\x00\xF0\x00\xA1\x48\x00\x00\x14\x80\x00\x01\x00\x0D\x05\x16\x12\x0C\x35\x5C\x00\x00\x00\x00\x06\x09\x00\xA7\x14\xC5\xEE\x93\xEE\x28\x00\x24\x09\x00\x00\x00\x00\x00\x00\x41\x4A\x53\x4A\x4A\x52\x82\x9F\x80\x81\x00\x88\xA3\xBE\x28\x02\x00\x00\x9C\x06\x00\x00\x00\x14\x0D\x05\x16\x12\x0C\x35\x5C\x00\x01\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x02\x2E\x5A\x38\x4D\x10\x0B\x0B\x0E\x0C\x0D\x0B\x0E\x0D\x0E\x0D\x0C\x0C\x0A\x0B\x0D\x0C\x0C\x0C\x0D\x0D\x0D\x0D\x0B\x0D\x0C\x0E\x0D\x0C\x0C\x0B\x0D\x11\x0A\x12\x0A\x0C\x0F\x0C\x0C\x0E\x0E\x0D\x0C\x0B\x00\x00\x0D\x0D\x00\x00\x0E\x0D\x00\x00\x0A\x0E\x00\x00\x0B\x0C\x00\x00\x0D\x0E\x00\x00\x0B\x0E\x00\x00\x0F\x0C\x00\x00\x0E\x0F\x00\x00\x0B\x0E\x00\x00\x0C\x0B\x00\x00\x0E\x0B\x00\x00\x09\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x16\x17\x22\x16\x0B\x09\x0D\x0B\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0D\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0D\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x00\x04\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x98\x25\x4F\x6E"
SAMPLE_RAW_DATA2 = \
"\x7F\x7F\xF0\x02\x00\x06\x12\x00\x4D\x00\x8E\x00\x80\x01\xFA\x01\x74\x02\x00\x00\x32\x28\xC9\x41\x00\x0D\x04\x1E\x0A\x00\x20\x03\x00\x00\x01\xFF\x09\x00\x0F\x27\x00\x00\x00\x1F\x00\x00\x00\x00\x7D\x3D\x71\x03\x61\x03\x05\x06\x32\x00\x62\x00\x28\x00\x00\x06\xFE\xD0\xFC\x09\x01\x00\xF0\x00\xA1\x48\x00\x00\x14\x80\x00\x02\x00\x0D\x05\x16\x12\x0E\x35\x5C\x00\x00\x00\x00\x06\x11\x00\x98\x14\xC5\xEE\x93\xEE\x28\x00\x23\x09\x00\x00\x00\x00\x00\x00\x41\x4B\x53\x4A\x4A\x52\x82\x9F\x00\x00\x00\x88\xA4\xBE\xFC\x06\x00\x00\xD7\x06\x00\x00\x00\x14\x0D\x05\x16\x12\x0E\x35\x5C\x00\x01\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x02\x32\x5B\x3B\x4D\x10\x0A\x0C\x0E\x0D\x0C\x0A\x0B\x0D\x0E\x0C\x0D\x0C\x0D\x0D\x0C\x0D\x0D\x0B\x0B\x0C\x0D\x0C\x0A\x0B\x0E\x0D\x0D\x10\x0D\x09\x0A\x0C\x0C\x0A\x0C\x0C\x0D\x11\x0D\x0D\x0C\x0E\x0D\x0D\x00\x00\x0A\x0E\x00\x00\x0F\x0C\x00\x00\x0E\x0E\x00\x00\x0C\x0B\x00\x00\x0D\x09\x00\x00\x0F\x0E\x00\x00\x0F\x0C\x00\x00\x0E\x0F\x00\x00\x0D\x0F\x00\x00\x0E\x0C\x00\x00\x0A\x0F\x00\x00\x0C\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x16\x18\x23\x16\x0B\x09\x0E\x0B\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0D\x0A\x0B\x08\x0D\x0A\x0B\x09\x0C\x0A\x0B\x09\x0D\x0A\x0B\x09\x0D\x0A\x0B\x08\x0D\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0D\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0B\x0B\x09\x0C\x0A\x0B\x09\x0D\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x00\x04\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x9B\x26\x78\x6E"
SAMPLE_RAW_DATA3 = \
"\x7F\x7F\xF0\x02\x00\x06\x12\x00\x4D\x00\x8E\x00\x80\x01\xFA\x01\x74\x02\x00\x00\x32\x28\xC9\x41\x00\x0D\x04\x1E\x0A\x00\x20\x03\x00\x00\x01\xFF\x09\x00\x0F\x27\x00\x00\x00\x1F\x00\x00\x00\x00\x7D\x3D\x71\x03\x61\x03\x05\x06\x32\x00\x62\x00\x28\x00\x00\x06\xFE\xD0\xFC\x09\x01\x00\xF0\x00\xA1\x48\x00\x00\x14\x80\x00\x03\x00\x0D\x05\x16\x12\x10\x35\x5C\x00\x00\x00\x00\x06\x08\x00\x8D\x14\xC5\xEE\x93\xEE\x28\x00\x23\x09\x00\x00\x00\x00\x00\x00\x41\x4A\x53\x4A\x4A\x52\x82\x9F\x00\x00\x00\x88\xA4\xBE\x30\x01\x00\x00\xD8\x07\x00\x00\x00\x14\x0D\x05\x16\x12\x10\x35\x5C\x00\x01\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x02\x36\x59\x3E\x4B\x0F\x0A\x0D\x0A\x0B\x0D\x0D\x0B\x0D\x0C\x0B\x0B\x0C\x0B\x0D\x0D\x0D\x0E\x0E\x0A\x0C\x0D\x0C\x0C\x0C\x0B\x0D\x0C\x0C\x0D\x0F\x0C\x10\x0F\x10\x0B\x0C\x0C\x0B\x0E\x0E\x0D\x0C\x0E\x0D\x00\x00\x0E\x0C\x00\x00\x0E\x0F\x00\x00\x0B\x0D\x00\x00\x0B\x0D\x00\x00\x0F\x0A\x00\x00\x0D\x0E\x00\x00\x0D\x0D\x00\x00\x0B\x0D\x00\x00\x0C\x0C\x00\x00\x0C\x0E\x00\x00\x0E\x10\x00\x00\x0D\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x16\x17\x24\x16\x0B\x09\x0E\x0B\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0D\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0D\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0D\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x00\x04\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x9C\x28\x9E\x6D"
SAMPLE_RAW_DATA4 = \
"\x7F\x7F\xF0\x02\x00\x06\x12\x00\x4D\x00\x8E\x00\x80\x01\xFA\x01\x74\x02\x00\x00\x32\x28\xC9\x41\x00\x0D\x04\x1E\x0A\x00\x20\x03\x00\x00\x01\xFF\x09\x00\x0F\x27\x00\x00\x00\x1F\x00\x00\x00\x00\x7D\x3D\x71\x03\x61\x03\x05\x06\x32\x00\x62\x00\x28\x00\x00\x06\xFE\xD0\xFC\x09\x01\x00\xF0\x00\xA1\x48\x00\x00\x14\x80\x00\x04\x00\x0D\x05\x16\x12\x12\x35\x5C\x00\x00\x00\x00\x06\x09\x00\x94\x14\xC5\xEE\x93\xEE\x28\x00\x23\x09\x00\x00\x00\x00\x00\x00\x41\x4B\x53\x4A\x4A\x52\x82\x9F\x00\x00\x00\x88\xA4\xBE\x05\x03\x00\x00\xD2\x05\x00\x00\x00\x14\x0D\x05\x16\x12\x12\x35\x5C\x00\x01\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x02\x36\x5A\x38\x4E\x0F\x0D\x0D\x10\x0F\x0C\x0F\x0E\x0E\x0C\x0E\x0E\x0A\x10\x0E\x0B\x0B\x0E\x0D\x0D\x0B\x09\x0E\x0B\x0C\x0E\x0C\x0E\x0E\x0E\x0E\x0A\x0D\x0F\x0B\x0A\x0D\x10\x0B\x0C\x0F\x0C\x0F\x10\x0C\x00\x00\x0B\x0D\x00\x00\x0D\x0B\x00\x00\x0F\x0F\x00\x00\x0B\x0C\x00\x00\x0E\x0D\x00\x00\x0F\x0B\x00\x00\x0F\x0F\x00\x00\x0D\x0B\x00\x00\x0B\x0D\x00\x00\x0B\x0D\x00\x00\x0B\x0A\x00\x00\x0D\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x16\x17\x23\x16\x0C\x09\x0D\x0B\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x08\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0C\x0A\x0B\x09\x0D\x0A\x0B\x09\x0C\x0A\x00\x04\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x00\x00\x64\x00\x9E\x26\x85\x6D"




break_success_str = NEWLINE + "[BREAK Wakeup A]" + NEWLINE +\
"WorkHorse Broadband ADCP Version 50.40" + NEWLINE +\
"Teledyne RD Instruments (c) 1996-2010" + NEWLINE +\
"All Rights Reserved." + NEWLINE +\
">"


break_alarm_str = NEWLINE + "[ALARM Wakeup A]" + NEWLINE +\
"WorkHorse Broadband ADCP Version 50.40" + NEWLINE +\
"Teledyne RD Instruments (c) 1996-2010" + NEWLINE +\
"All Rights Reserved." + NEWLINE +\
">"

EF_CHAR = '\xef'

CALIBRATION_RAW_DATA = \
"ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM" + NEWLINE + \
"               Calibration date and time: 9/22/2012  11:53:32" + NEWLINE + \
"                             S inverse" + NEWLINE + \
"          " + EF_CHAR + "                                                  " + EF_CHAR + NEWLINE + \
"     Bx   " + EF_CHAR + "   4.1275e-01  4.2168e-01 -2.0631e-02 -2.8440e-05 " + EF_CHAR + NEWLINE + \
"     By   " + EF_CHAR + "  -4.9163e-03  4.7625e-06 -2.7393e-03 -5.6853e-01 " + EF_CHAR + NEWLINE + \
"     Bz   " + EF_CHAR + "   2.1975e-01 -2.0662e-01 -3.0120e-01  2.7459e-03 " + EF_CHAR + NEWLINE + \
"     Err  " + EF_CHAR + "   4.8227e-01 -4.4007e-01  6.5367e-01 -7.3235e-03 " + EF_CHAR + NEWLINE + \
"          " + EF_CHAR + "                                                  " + EF_CHAR + NEWLINE + \
"                             Coil Offset" + NEWLINE + \
"                         " + EF_CHAR + "                " + EF_CHAR + NEWLINE + \
"                         " + EF_CHAR + "   3.3914e+04   " + EF_CHAR + NEWLINE + \
"                         " + EF_CHAR + "   3.3331e+04   " + EF_CHAR + NEWLINE + \
"                         " + EF_CHAR + "   3.4030e+04   " + EF_CHAR + NEWLINE + \
"                         " + EF_CHAR + "   3.4328e+04   " + EF_CHAR + NEWLINE + \
"                         " + EF_CHAR + "                " + EF_CHAR + NEWLINE + \
"                             Electrical Null" + NEWLINE + \
"                              " + EF_CHAR + "       " + EF_CHAR + NEWLINE + \
"                              " + EF_CHAR + " 33989 " + EF_CHAR + NEWLINE + \
"                              " + EF_CHAR + "       " + EF_CHAR + NEWLINE + \
"                    TILT CALIBRATION MATRICES in NVRAM" + NEWLINE + \
"                Calibration date and time: 9/22/2012  11:50:48" + NEWLINE + \
"              Average Temperature During Calibration was   25.7 " + EF_CHAR + "C" + NEWLINE + \
NEWLINE + \
"                   Up                              Down" + NEWLINE + \
NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + NEWLINE + \
" Roll   " + EF_CHAR + "  -1.7305e-07  -2.9588e-05 " + EF_CHAR + "     " + EF_CHAR + "   3.0294e-07   3.1274e-05 " + EF_CHAR + NEWLINE + \
" Pitch  " + EF_CHAR + "  -2.9052e-05  -5.6057e-07 " + EF_CHAR + "     " + EF_CHAR + "  -3.1059e-05  -5.2326e-07 " + EF_CHAR + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + NEWLINE + \
NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + NEWLINE + \
" Offset " + EF_CHAR + "   3.2805e+04   3.2384e+04 " + EF_CHAR + "     " + EF_CHAR + "   3.3287e+04   3.1595e+04 " + EF_CHAR + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + NEWLINE + \
NEWLINE + \
"                             " + EF_CHAR + "       " + EF_CHAR + NEWLINE + \
"                      Null   " + EF_CHAR + " 33272 " + EF_CHAR + NEWLINE + \
"                             " + EF_CHAR + "       " + EF_CHAR + NEWLINE + \
NEWLINE + \
NEWLINE + \
NEWLINE + \
NEWLINE + \
NEWLINE + \
">"

PS0_RAW_DATA = \
"Instrument S/N:  18593" + NEWLINE +\
"       Frequency:  153600 HZ" + NEWLINE +\
"   Configuration:  4 BEAM, JANUS" + NEWLINE +\
"     Match Layer:  10" + NEWLINE +\
"      Beam Angle:  20 DEGREES" + NEWLINE +\
"    Beam Pattern:  CONVEX" + NEWLINE +\
"     Orientation:  UP" + NEWLINE +\
"       Sensor(s):  HEADING  TILT 1  TILT 2  DEPTH  TEMPERATURE  PRESSURE" + NEWLINE +\
"Pressure Sens Coefficients:" + NEWLINE +\
"              c3 = +1.629386E-10" + NEWLINE +\
"              c2 = -1.886023E-06" + NEWLINE +\
"              c1 = +1.364779E+00" + NEWLINE +\
"          Offset = -2.457906E+01" + NEWLINE +\
NEWLINE +\
"Temp Sens Offset:  -0.17 degrees C" + NEWLINE +\
NEWLINE +\
"    CPU Firmware:  50.40 [0]" + NEWLINE +\
"   Boot Code Ver:  Required:  1.16   Actual:  1.16" + NEWLINE +\
"    DEMOD #1 Ver:  ad48, Type:  1f" + NEWLINE +\
"    DEMOD #2 Ver:  ad48, Type:  1f" + NEWLINE +\
"    PWRTIMG  Ver:  85d3, Type:   6" + NEWLINE +\
NEWLINE +\
"Board Serial Number Data:" + NEWLINE +\
"   98  00 00 06 FF 13 A0  09 HPI727-3007-00A" + NEWLINE +\
"   28  00 00 06 FE D0 FC  09 CPU727-2011-00E" + NEWLINE +\
"   0C  00 00 06 FF 13 BA  09 HPA727-3009-02B" + NEWLINE +\
"   E7  00 00 06 B2 C6 7D  09 REC727-1004-05A" + NEWLINE +\
"   70  00 00 06 F5 AF 73  09 DSP727-2001-05H" + NEWLINE +\
"   F0  00 00 06 F5 B2 EB  09 TUN727-1005-05A" + NEWLINE +\
">"


PS3_RAW_DATA = \
"Beam Width:   3.7 degrees" + NEWLINE +\
NEWLINE +\
"Beam     Elevation     Azimuth" + NEWLINE +\
"  1         -69.81      269.92" + NEWLINE +\
"  2         -70.00       89.92" + NEWLINE +\
"  3         -69.82        0.07" + NEWLINE +\
"  4         -69.89      180.08" + NEWLINE +\
NEWLINE +\
"Beam Directional Matrix (Down):" + NEWLINE +\
"  0.3453    0.0005    0.9385    0.2421" + NEWLINE +\
" -0.3421   -0.0005    0.9397    0.2444" + NEWLINE +\
" -0.0005   -0.3451    0.9386   -0.2429" + NEWLINE +\
"  0.0005    0.3438    0.9390   -0.2438" + NEWLINE +\
NEWLINE +\
"Instrument Transformation Matrix (Down):    Q14:" + NEWLINE +\
"  1.4587   -1.4508   -0.0010   -0.0051       23899  -23770     -16     -83" + NEWLINE +\
" -0.0008    0.0033   -1.4532    1.4500         -13      54  -23809   23757" + NEWLINE +\
"  0.2650    0.2676    0.2657    0.2667        4342    4384    4353    4370" + NEWLINE +\
"  1.0225    1.0323   -1.0257   -1.0297       16752   16913  -16805  -16871" + NEWLINE +\
"Beam Angle Corrections Are Loaded." + NEWLINE +\
">"

PS4_RAW_DATA = \
"Ping Sequence:  W W W W W W W W W W" + NEWLINE +\
">" 

FD_RAW_DATA = \
"Total Unique Faults   =     2" + NEWLINE +\
"Overflow Count        =     0" + NEWLINE +\
"Time of first fault:    12/11/29,19:40:37.02" + NEWLINE +\
"Time of last fault:     12/12/12,20:31:37.14" + NEWLINE +\
NEWLINE +\
"Fault Log:" + NEWLINE +\
"Entry #  0 Code=0a08h  Count=    2  Delta=112625967 Time=12/12/12,20:31:36.99" + NEWLINE +\
" Parameter = 00000000h" + NEWLINE +\
"  Tilt axis X over range." + NEWLINE +\
"Entry #  1 Code=0a09h  Count=    2  Delta=112625966 Time=12/12/12,20:31:37.14" + NEWLINE +\
" Parameter = 00000000h" + NEWLINE +\
"  Tilt axis Y over range." + NEWLINE +\
"End of fault log." + NEWLINE + NEWLINE +\
"Fault Log Dump:  addr=007EADC8" + NEWLINE +\
"a5 01 00 02 00 00 00 00 20 13 28 25 0b 1d 0c 06" + NEWLINE +\
"0e 14 1f 25 0c 0c 0c 05 01 f2 0a 08 00 00 00 02" + NEWLINE +\
"63 14 1f 24 0c 0c 0c 05 06 b6 89 2f 00 00 00 00" + NEWLINE +\
"02 6c 0a 09 00 00 00 02 0e 14 1f 25 0c 0c 0c 05" + NEWLINE +\
"06 b6 89 2e 00 00 00 00 02 18 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01" + NEWLINE +\
">"



PT200_RAW_DATA = \
"Ambient  Temperature =    23.43 Degrees C" + NEWLINE +\
"  Attitude Temperature =    23.96 Degrees C" + NEWLINE +\
"  Internal Moisture    = 8C66h" + NEWLINE +\
NEWLINE +\
"Correlation Magnitude: Narrow Bandwidth" + NEWLINE +\
NEWLINE +\
"               Lag  Bm1  Bm2  Bm3  Bm4" + NEWLINE +\
"                 0  255  255  255  255" + NEWLINE +\
"                 1  140  159  178  149" + NEWLINE +\
"                 2   37   63   92   54" + NEWLINE +\
"                 3   15   17   42    9" + NEWLINE +\
"                 4   16    6   20    5" + NEWLINE +\
"                 5    7    4   12    4" + NEWLINE +\
"                 6   10    1   12    4" + NEWLINE +\
"                 7    8    2    9    4" + NEWLINE +\
NEWLINE +\
"  High Gain RSSI:    67   65   72   65" + NEWLINE +\
"   Low Gain RSSI:    11    8   12   10" + NEWLINE +\
NEWLINE +\
"  SIN Duty Cycle:    49   50   48   48" + NEWLINE +\
"  COS Duty Cycle:    50   50   50   49" + NEWLINE +\
NEWLINE +\
"Receive Test Results = 00000000 ... PASS" + NEWLINE +\
NEWLINE +\
"IXMT    =      0.8 Amps rms  [Data=45h]" + NEWLINE +\
"VXMT    =     43.8 Volts rms [Data=4ah]" + NEWLINE +\
"   Z    =     55.5 Ohms" + NEWLINE +\
"Transmit Test Results = $0 ... PASS" + NEWLINE +\
NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"   12   12   12   12" + NEWLINE +\
"  255  255  255  255" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"   12   12   12   12" + NEWLINE +\
"  255  255  255  255" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"   12   12   12   12" + NEWLINE +\
"  255  255  255  255" + NEWLINE +\
"Electronics Test Results = $00000000" + NEWLINE +\
"Receive Bandwidth:" + NEWLINE +\
"    Sample      bw    bw    bw    bw    bw" + NEWLINE +\
"      rate  expect   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
"        38      12    13    12    10    14 Khz" + NEWLINE +\
"   results          PASS  PASS  PASS  PASS" + NEWLINE +\
"RSSI Time Constant:" + NEWLINE +\
NEWLINE +\
"RSSI Filter Strobe 1 =   38400 Hz" + NEWLINE +\
"  time   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
"  msec  cnts  cnts  cnts  cnts" + NEWLINE +\
"     1     5     7     6     7" + NEWLINE +\
"     2    11    14    11    12" + NEWLINE +\
"     3    15    19    15    17" + NEWLINE +\
"     4    19    23    19    22" + NEWLINE +\
"     5    22    27    22    25" + NEWLINE +\
"     6    25    29    25    28" + NEWLINE +\
"     7    27    32    27    30" + NEWLINE +\
"     8    29    33    29    32" + NEWLINE +\
"     9    31    35    31    34" + NEWLINE +\
"    10    32    36    32    35" + NEWLINE +\
"   nom    40    43    41    43" + NEWLINE +\
"result    PASS  PASS  PASS  PASS" + NEWLINE +\
">" 



powering_down_str = NEWLINE +\
"Powering Down"

# typed CS, got samples
# sent a break 300
# instrument wokeup, but 10 minutes later had not sent below warning...
# From Lytle
self_deploy_str = NEWLINE +\
"System will self-deploy in 1 minute unless valid command entered!"

get_params_output = \
            "CI?" + NEWLINE +\
            "CI = 000 ----------------- Instrument ID (0-255)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CP?" + NEWLINE +\
            "CP = 0 ------------------- PolledMode (1=ON, 0=OFF;  BREAK resets)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CQ?" + NEWLINE +\
            "CQ = 255 ----------------- Xmt Power (0=Low, 255=High)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TB?" + NEWLINE +\
            "TB 00:00:00.00 --------- Time per Burst (hrs:min:sec.sec/100)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TC?" + NEWLINE +\
            "TC 00002 --------------- Ensembles Per Burst (0-65535)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TE?" + NEWLINE +\
            "TE 01:00:00.00 --------- Time per Ensemble (hrs:min:sec.sec/100)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TF?" + NEWLINE +\
            "TF **/**/**,**:**:** --- Time of First Ping (yr/mon/day,hour:min:sec)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TG?" + NEWLINE +\
            "TG ****/**/**,**:**:** - Time of First Ping (CCYY/MM/DD,hh:mm:ss)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TP?" + NEWLINE +\
            "TP 01:20.00 ------------ Time per Ping (min:sec.sec/100)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TT?" + NEWLINE +\
            "TT 2013/02/28,07:55:33 - Time Set (CCYY/MM/DD,hh:mm:ss)" + NEWLINE +\
            ">" + NEWLINE +\
            ">TX?" + NEWLINE +\
            "TX 00:00:00 ------------ Buffer Output Period: (hh:mm:ss)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WA?" + NEWLINE +\
            "WA 255,001 ------------- False Target Threshold (Max)(0-255),[Start Bin]" + NEWLINE +\
            ">" + NEWLINE +\
            ">WC?" + NEWLINE +\
            "WC 064 ----------------- Correlation Threshold" + NEWLINE +\
            ">" + NEWLINE +\
            ">WD?" + NEWLINE +\
            "WD 111100000 ----------- Data Out (Vel;Cor;Amp  PG;St;P0  P1;P2;P3)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WE?" + NEWLINE +\
            "WE 5000 ---------------- Error Velocity Threshold (0-5000 mm/s)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WF?" + NEWLINE +\
            "WF 0088 ---------------- Blank After Transmit (cm)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WI?" + NEWLINE +\
            "WI 0 ------------------- Clip Data Past Bottom (0=OFF,1=ON)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WJ?" + NEWLINE +\
            "WJ 1 ------------------- Rcvr Gain Select (0=Low,1=High)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WL?" + NEWLINE +\
            "WL 001,005 ------------- Water Reference Layer:  Begin Cell (0=OFF), End Cell" + NEWLINE +\
            ">" + NEWLINE +\
            ">WM?" + NEWLINE +\
            "WM 1 ------------------- Profiling Mode (1-15)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WN?" + NEWLINE +\
            "WN 030 ----------------- Number of depth cells (1-255)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WP?" + NEWLINE +\
            "WP 00045 --------------- Pings per Ensemble (0-16384)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WS?" + NEWLINE +\
            "WS 0800 ---------------- Depth Cell Size (cm)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WT?" + NEWLINE +\
            "WT 0000 ---------------- Transmit Length (cm) [0 = Bin Length]" + NEWLINE +\
            ">" + NEWLINE +\
            ">WU?" + NEWLINE +\
            "WU 0 ------------------- Ping Weighting (0=Box,1=Triangle)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WV?" + NEWLINE +\
            "WV 175 ----------------- Mode 1 Ambiguity Vel (cm/s radial)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CC?" + NEWLINE +\
            "CC = 000 000 000 --------- Choose External Devices (x;x;x  x;x;x  x;x;SBMC)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CH?" + NEWLINE +\
            "CH = 1 ------------------- Suppress Banner" + NEWLINE +\
            ">" + NEWLINE +\
            "CJ?" + NEWLINE +\
            "CJ = 0 ------------------- IMM Output Enable (0=Disable,1=Enable)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CL?" + NEWLINE +\
            "CL = 0 ------------------- Sleep Enable (0 = Disable, 1 = Enable, 2 See Manual)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CM?" + NEWLINE +\
            "CM = 0 ------------------- RS-232 Sync Master (0 = OFF, 1 = ON)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CN?" + NEWLINE +\
            "CN = 1 ------------------- Save NVRAM to recorder (0 = ON, 1 = OFF)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CW?" + NEWLINE +\
            "CW = 00250 --------------- Trigger Timeout (ms; 0 = no timeout)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CX?" + NEWLINE +\
            "CX = 1 ------------------- Trigger Enable (0 = OFF, 1 = ON)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EA?" + NEWLINE +\
            "EA = +00000 -------------- Heading Alignment (1/100 deg)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EB?" + NEWLINE +\
            "EB = +00000 -------------- Heading Bias (1/100 deg)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EC?" + NEWLINE +\
            "EC = 1500 ---------------- Speed Of Sound (m/s)" + NEWLINE +\
            ">" + NEWLINE +\
            ">ED?" + NEWLINE +\
            "ED = 00000 --------------- Transducer Depth (0 - 65535 dm)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EH?" + NEWLINE +\
            "EH = 00000 --------------- Heading (1/100 deg)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EP?" + NEWLINE +\
            "EP = +0000 --------------- Tilt 1 Sensor (1/100 deg)" + NEWLINE +\
            ">" + NEWLINE +\
            ">ER?" + NEWLINE +\
            "ER = +0000 --------------- Tilt 2 Sensor (1/100 deg)" + NEWLINE +\
            ">" + NEWLINE +\
            ">ES?" + NEWLINE +\
            "ES = 35 ------------------ Salinity (0-40 pp thousand)" + NEWLINE +\
            ">" + NEWLINE +\
            ">ET?" + NEWLINE +\
            "ET = +2500 --------------- Temperature (1/100 deg Celsius)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EX?" + NEWLINE +\
            "EX = 00000 --------------- Coord Transform (Xform:Type; Tilts; 3Bm; Map)" + NEWLINE +\
            ">" + NEWLINE +\
            ">EZ?" + NEWLINE +\
            "EZ = 1111101 ------------- Sensor Source (C;D;H;P;R;S;T)" + NEWLINE +\
            ">" + NEWLINE +\
            ">PB?" + NEWLINE +\
            "PB = 001,000,1 ------------- PD12 Bin Select (first;num;sub)" + NEWLINE +\
            ">" + NEWLINE +\
            ">PD?" + NEWLINE +\
            "PD = 00 ------------------ Data Stream Select (0-18)" + NEWLINE +\
            ">" + NEWLINE +\
            ">PE?" + NEWLINE +\
            "PE = 00001 --------------- PD12 Ensemble Select (1-65535)" + NEWLINE +\
            ">" + NEWLINE +\
            ">PO?" + NEWLINE +\
            "PO = 1111 ---------------- PD12 Velocity Component Select (v1;v2;v3;v4)" + NEWLINE +\
            ">" + NEWLINE +\
            ">SA?" + NEWLINE +\
            "SA = 001 ----------------- Synch Before/After Ping/Ensemble Bottom/Water/Both" + NEWLINE +\
            ">" + NEWLINE +\
            ">SB?" + NEWLINE +\
            "SB = 1 ------------------- Channel B Break Interrupts are ENABLED" + NEWLINE +\
            ">" + NEWLINE +\
            ">SI?" + NEWLINE +\
            "SI = 00000 --------------- Synch Interval (0-65535)" + NEWLINE +\
            ">" + NEWLINE +\
            ">SM?" + NEWLINE +\
            "SM = 1 ------------------- Mode Select (0=OFF,1=MASTER,2=SLAVE,3=NEMO)" + NEWLINE +\
            ">" + NEWLINE +\
            ">SS?" + NEWLINE +\
            "SS = 0 ------------------- RDS3 Sleep Mode (0=No Sleep)" + NEWLINE +\
            ">" + NEWLINE +\
            ">ST?" + NEWLINE +\
            "ST = 00000 --------------- Slave Timeout (seconds,0=indefinite)" + NEWLINE +\
            ">" + NEWLINE +\
            ">SW?" + NEWLINE +\
            "SW = 00100 --------------- Synch Delay (1/10 msec)" + NEWLINE +\
            ">" + NEWLINE +\
            ">DW?" + NEWLINE +\
            "DW  0 ------------------ Current ID on RS-485 Bus" + NEWLINE +\
            ">" + NEWLINE +\
            ">RI?" + NEWLINE +\
            NEWLINE +\
            "Deployment Auto Increment is ENABLED" + NEWLINE +\
            NEWLINE +\
            ">" + NEWLINE +\
            ">RN?" + NEWLINE +\
            NEWLINE +\
            "Current deployment name = _RDI_" + NEWLINE +\
            NEWLINE +\
            ">" + NEWLINE +\
            ">WB?" + NEWLINE +\
            "WB 1 ------------------- Bandwidth Control (0=Wid,1=Nar)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WG?" + NEWLINE +\
            "WG 000 ----------------- Percent Good Minimum (1-100%)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WQ?" + NEWLINE +\
            "WQ 0 ------------------- Sample Ambient Sound (0=OFF,1=ON)" + NEWLINE +\
            ">" + NEWLINE +\
            ">WW?" + NEWLINE +\
            "WW 004 ----------------- Mode 1 Pings before Mode 4 Re-acquire" + NEWLINE +\
            ">" + NEWLINE +\
            ">WZ?" + NEWLINE +\
            "WZ 010 ----------------- Mode 5 Ambiguity Velocity (cm/s radial)" + NEWLINE +\
            ">" + NEWLINE +\
            ">AZ?" + NEWLINE +\
            NEWLINE +\
            " 13.386345" + NEWLINE +\
            NEWLINE +\
            ">" + NEWLINE +\
            ">CB?" + NEWLINE +\
            "CB = 411 ----------------- Serial Port Control (Baud [4=9600]; Par; Stop)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CD?" + NEWLINE +\
            "CD = 000 000 000 --------- Serial Data Out (Vel;Cor;Amp  PG;St;P0  P1;P2;P3)" + NEWLINE +\
            ">" + NEWLINE +\
            ">CF?" + NEWLINE +\
            "CF = 11110 --------------- Flow Ctrl (EnsCyc;PngCyc;Binry;Ser;Rec)" + NEWLINE +\
            ">" + NEWLINE +\
            ">DB?" + NEWLINE +\
            "DB 411 ----------------- RS-485 Port Control (Baud; N/U; N/U)" + NEWLINE +\
            ">" + NEWLINE
