#!/home/mworden/Workspace/code/marine-integrations/bin/python

import msgpack
import random
import sys
import getopt
import ntplib

RAW_TIME_MICROSECS_RANGE = (100000, 999999)
RAW_TIME_SECS_RANGE = (1385254223, 1385254240)
CALIBRATED_PHASE_RANGE = (20.0000, 45.0000)
OPTODE_TEMPERATURE_RANGE = (5.0000, 12.0000)


def generate_yaml_and_msgpack(count):

    yml_fd = open("test.yml", 'w')
    msgpack_fd = open("test.mpk", 'wb')

    yml_fd.write("header:\n  particle_object: \'MULTIPLE\'\n  particle_type: \'MULTIPLE\'\n\ndata:\n")

    counter = 1

    for x in range(count):
    
        microsecs = random.randint(RAW_TIME_MICROSECS_RANGE[0],RAW_TIME_MICROSECS_RANGE[1])
        secs = random.randint(RAW_TIME_SECS_RANGE[0],RAW_TIME_SECS_RANGE[1])
        internal_timestamp = ntplib.system_to_ntp_time(secs + microsecs/1000000.0)
        calibrated_phase = round(random.uniform(CALIBRATED_PHASE_RANGE[0], CALIBRATED_PHASE_RANGE[1]), 4)
        optode_temperature = round(random.uniform(OPTODE_TEMPERATURE_RANGE[0], OPTODE_TEMPERATURE_RANGE[1]), 4)

        yml_fd.write("  - _index: %d\n" % (counter,))
        yml_fd.write("    particle_object: DostaAbcdjmMmpCdsParserDataParticle\n")
        yml_fd.write("    particle_type: dosta_abcdjm_mmp_cds_instrument\n")
        yml_fd.write("    internal_timestamp: %.10f\n" % (internal_timestamp,))
        yml_fd.write("    raw_time_microseconds: %d\n" % (microsecs,))
        yml_fd.write("    raw_time_seconds: %.10f\n" % (secs,))
        yml_fd.write("    calibrated_phase: %.10f\n" % (calibrated_phase,))
        yml_fd.write("    optode_temperature: %.4f\n" % (optode_temperature,))

        msgpack_fd.write(msgpack.packb([secs, microsecs, {'doconcs': calibrated_phase, 't': optode_temperature}]))

        counter += 1

        print internal_timestamp, secs, microsecs, calibrated_phase, optode_temperature

    yml_fd.close()
    msgpack_fd.close()

def usage():
  print 'Usage: '+sys.argv[0]+' -c <sample_count>'

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:v", ["help", "count="])
    except getopt.GetoptError as err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    count = None
    verbose = False
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-c", "--count"):
            try:
                count = int(a)
            except ValueError:
                usage()
                sys.exit(2)
        else:
            assert False, "unhandled option"

    if count:
        generate_yaml_and_msgpack(count)
    else:
        usage()
        sys.exit(2)

if __name__ == "__main__":
    main()

