#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.pd0
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/pd0.py
@author Carlos Rueda
@brief Support class for the PD0 output data structure (adapted from similar
       class in SIAM).
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'

import datetime
from struct import pack, unpack

ID_HEADER = 0x7F
ID_DATA_SOURCE = 0x7F
ID_FIXED_LEADER = 0x0000
ID_VELOCITY = 0x0100
ID_CORRELATION_MAGNITUDE = 0x0200
ID_ECHO_INTENSITY = 0x0300
ID_PERCENT_GOOD = 0x0400
ID_VARIABLE_LEADER = 0x0080
DATATYPE_FIXED_LEADER = 1
DATATYPE_VARIABLE_LEADER = 2


#################
# some utilities
#################

def toSignedShort(a, b):
    """
    Converts the 2 unsigned bytes to a signed (2-byte) short.
    @param a least significant byte
    @param b most significant byte
    """
    p = pack('BB', a & 0xff, b & 0xff)
    s = unpack('h', p)[0]
    return s


def getShort(index, data):
    """
    Convert two contiguous bytes to a short, starting at specified
    index of dataBytes; assumes little-endian.

    @param index
    @retval the value
    """
    lsb = data[index]
    msb = data[index + 1]
    return toSignedShort(lsb, msb)


class InvalidEnsemble(Exception):
    pass


class PD0DataStructure(object):
    """
    Encapsulates access to the workhorses binary data format.
    Adapted from SIAM.
    """

    def __init__(self, data):
        if data is None:
            raise ValueError("data is None")

        data = bytearray(data)

        def error(m):
            raise InvalidEnsemble("Invalid workhorse data ensemble: %s" % m)

        try:
            if data[0] != ID_HEADER:
                error("data[0]=%d is not %d" % (data[0], ID_HEADER))

            if data[1] != ID_DATA_SOURCE:
                error("data[1]=%d is not %d" % (data[1], ID_DATA_SOURCE))
        except IndexError, e:
            error("too short data array; %s" % e)

        header_len = self.getHeaderLength(data)
        if header_len + 2 >= len(data):
            raise InvalidEnsemble("index header_len + 2 = %d out of range" %
                                  (header_len + 2))

        if getShort(header_len + 1, data) != ID_FIXED_LEADER:
            self.data = data
        else:
            raise ValueError("Not a valid workhorse data ensemble")

    def __str__(self):
        s = []
        s.append("NumberOfBytesInEnsemble = %d" % \
                     self.getNumberOfBytesInEnsemble())
        s.append("HeaderLength = %d" % \
                     self.getHeaderLength())
        s.append("NumberOfCells = %d" % self.getNumberOfCells())
        s.append("PingsPerEnsemble = %d" % self.getPingsPerEnsemble())
        s.append("DepthCellLength = %d" % self.getDepthCellLength())
        s.append("ErrorVelocityMaximum = %s" % self.getErrorVelocityMaximum())
        s.append("BinOneDistance = %s" % self.getBinOneDistance())
        s.append("SpeedOfSound = %s" % self.getSpeedOfSound())
        s.append("EnsembleNumber = %s" % self.getEnsembleNumber())
        s.append("Time = %s" % str(self.getTime()))
        s.append("DepthOfTransducer = %s" % self.getDepthOfTransducer())
        s.append("Heading = %s" % self.getHeading())
        s.append("Pitch = %s" % self.getPitch())
        s.append("Roll = %s" % self.getRoll())
        s.append("Salinity = %s" % self.getSalinity())
        s.append("Temperature = %s" % self.getTemperature())

        offsets = [self.getOffsetForDataType(i + 1) for i in range(self.getNumberOfDataTypes())]
        s.append("NumberOfDataTypes = %d -> %s" % (self.getNumberOfDataTypes(), offsets))

        s.append("NumberOfBeams = %d" % self.getNumberOfBeams())
        for i in range(self.getNumberOfBeams()):
            beam = i + 1
            s.append("  Velocity_%d = %s" %
                     (beam, self.getVelocity(beam)))
            s.append("  CorrelationMagnitude_%d = %s" %
                     (beam, self.getCorrelationMagnitude(beam)))
            s.append("  EchoIntensity_%d = %s" %
                     (beam, self.getEchoIntensity(beam)))
            s.append("  PercentGood_%d = %s" %
                     (beam, self.getPercentGood(beam)))

        return "\n".join(s)

    def getShort(self, index, data=None):
        data = data or self.data
        return getShort(index, data)

    def getBytes(self, index, length):
        copy = self.data[index: index + length]
        return copy

    def getNumberOfDataTypes(self, data=None):
        data = data or self.data
        if 5 >= len(data):
            raise InvalidEnsemble("index 5 out of range")
        return int(data[5])

    def getHeaderLength(self, data=None):
        data = data or self.data
        return 2 * self.getNumberOfDataTypes(data) + 6

    def getNumberOfBytesInEnsemble(self, data=None):
        data = data or self.data
        return getShort(2, data)

    def getOffsetForDataType(self, i):
        """
         * @param i The data type number this can range form 1-6. The exact
                    upper *          limit is returned
         * @return The offset for data type #i. Adding '1' to this offset
                   number gives the absolute byte number in the ensemble
                   where data type #i begins.
        """
        ndt = self.getNumberOfDataTypes()
        if i <= 0 or i > ndt:
            raise ValueError("Invalid i=%d value not in [1..%d]" % (i, ndt))
        return self.getShort(6 + (i - 1) * 2)

    #######################
    # Fixed Leader Info
    #######################

    def getOffsetForFixedLeader(self):
        return int(self.getOffsetForDataType(DATATYPE_FIXED_LEADER))

    def getNumberOfBeams(self):
        return int(self.data[self.getOffsetForFixedLeader() + 8]) & 0xFF

    def getNumberOfCells(self):
        return int(self.data[self.getOffsetForFixedLeader() + 9])

    def getPingsPerEnsemble(self):
        return self.getShort(self.getOffsetForFixedLeader() + 10)

    def getDepthCellLength(self):
        return self.getShort(self.getOffsetForFixedLeader() + 12)

    def getErrorVelocityMaximum(self):
        return self.getShort(self.getOffsetForFixedLeader() + 20)

    def getBinOneDistance(self):
        return self.getShort(self.getOffsetForFixedLeader() + 32)

    #######################
    # Variable Leader Info
    #######################

    def getOffsetForVariableLeader(self):
        return int(self.getOffsetForDataType(DATATYPE_VARIABLE_LEADER))

    def getEnsembleNumber(self):
        """
        @retval sequential number of the ensemble to which the data in the
                output buffer apply taking into account the MSB
        """
        ens_number = self.getShort(self.getOffsetForVariableLeader() + 2)
        msb = int(self.data[self.getOffsetForVariableLeader() + 11])

        number = 65536 * msb + ens_number

        return number

    def getTime(self):
        """
        @retval datetime object representing the time from the WorkHorse ADCP's
                real-time clock (RTC) that the current data ensemble began.
        """
        century = int(self.data[self.getOffsetForVariableLeader() + 57])
        year2 = int(self.data[self.getOffsetForVariableLeader() + 58])
        year = 100 * century + year2
        month = int(self.data[self.getOffsetForVariableLeader() + 59])
        day = int(self.data[self.getOffsetForVariableLeader() + 60])
        hour = int(self.data[self.getOffsetForVariableLeader() + 61])
        min = int(self.data[self.getOffsetForVariableLeader() + 62])
        sec = int(self.data[self.getOffsetForVariableLeader() + 63])
        hun = int(self.data[self.getOffsetForVariableLeader() + 64])
        us = 10000 * hun

        ens_time = datetime.datetime(year, month, day, hour, min, sec, us)
        return ens_time

    def getSpeedOfSound(self):
        """
        @return speed of sound (m/s)
        """
        return self.getShort(self.getOffsetForVariableLeader() + 14)

    def getDepthOfTransducer(self):
        """
        @return depth in meters
        """
        return self.getShort(self.getOffsetForVariableLeader() + 16) * 0.1

    def getHeading(self):
        """
        @return heading in degrees (0 -360)
        """
        return self.getShort(self.getOffsetForVariableLeader() + 18) * 0.01

    def getPitch(self):
        """
        @return pitch in degrees (-20 - 20)
        """
        return self.getShort(self.getOffsetForVariableLeader() + 20) * 0.01

    def getRoll(self):
        """
        @return roll in degrees(-20 - 20)
        """
        return self.getShort(self.getOffsetForVariableLeader() + 22) * 0.01

    def getSalinity(self):
        """
        @return roll in degrees(-20 - 20)
        """
        return self.getShort(self.getOffsetForVariableLeader() + 24)

    def getTemperature(self):
        """
        @return temperature in celsius (-5 - 40 degrees)
        """
        return self.getShort(self.getOffsetForVariableLeader() + 26) * 0.01

    #######################
    # Data Info
    #######################

    def getVelocity(self, beam):
        """
         @param beam The beam number to return (values are 1-4)
         @return An array of velocities for the beam. (mm/s along beam axis).
                  None is returned if no velocity data was found
        """
        if beam < 1 or beam > 4:
            raise ValueError(
                    "Beam number must be between 1 and 4. You specified %s" %
                    beam)

        #
        # Find the index into the data for the start of the velocity record
        #
        idx = -1
        nTypes = self.getNumberOfDataTypes()
        for i in range(3, nTypes + 1):
            idxTest = self.getOffsetForDataType(i)
            id = self.getShort(idxTest)
            if id == ID_VELOCITY:
                idx = idxTest
                break

        velocities = None
        if idx > 0:
            nBeams = self.getNumberOfBeams()
            idx += 2 + ((beam - 1) * 2)  # Skip to start of velocity data
            velocities = []
            for i in range(self.getNumberOfCells()):
                a = self.data[idx]
                b = self.data[idx + 1]
                s = toSignedShort(a, b)
                velocities.append(s)
                idx += (nBeams * 2)

        return velocities

    def getCorrelationMagnitude(self, beam):
        """
        @param beam The beam number to return (values are 1-4)
        @return Magnitude of normalized echo autocorrelation at the lag used
                for estimating Doppler phase change.
                0 = bad; 255 = perfect (linear scale)
        """
        return self.getValues(beam, ID_CORRELATION_MAGNITUDE)

    def getEchoIntensity(self, beam):
        """
        @param beam The beam number to return (values are 1-4)
        @return echo intensity in dB
        """
        ei = self.getValues(beam, ID_ECHO_INTENSITY)
        out = None
        if ei is not None:
            out = [intens * 0.45 for intens in ei]

        return out

    def getPercentGood(self, beam):
        """
        @param beam The beam number to return (values are 1-4)
        @return Data-quality indicator that reports percentage (0 - 100) of
                good data collected for each depth cell of the velocity
                profile. The settings of the EX command determines how the
                Workhorse references percent-good data. Refer to Workhorse
                manual for moe details.
        """
        return self.getValues(beam, ID_PERCENT_GOOD)

    def getValues(self, beam, type):
        """
        @param beam THe beam number to return (values are 1-4)
        @return An array of values for the beam.
                 None is returned if nodata was found
        """
        if beam < 1 or beam > 4:
            raise ValueError(
                    "Beam number must be between 1 and 4. You specified %s" %
                    beam)

        #
        # Find the index into the data for the start of the record type you
        # want
        #
        idx = -1
        nTypes = self.getNumberOfDataTypes()
        for i in range(3, nTypes + 1):
            idxTest = self.getOffsetForDataType(i)
            id = self.getShort(idxTest)
            if id == type:
                idx = idxTest
                break

        values = None
        if idx > 0:
            nBeams = self.getNumberOfBeams()
            idx += 2 + (beam - 1)  # Skip to start of data record
            values = []
            for i in range(self.getNumberOfCells()):
#                values[i] = NumberUtil.toUnsignedInt(data[idx]);
                s = self.data[idx] & 0xff
                values.append(s)
                idx += nBeams

        return values


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print """
USAGE:
  pd0.py filename

Display info about the given ensemble.

Examples:
  pd0.py ensemble.bin
  pd0.py mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/resource/pd0_sample.bin
        """
        exit()

    filename = sys.argv[1]

    data_file = file(filename, 'r')
    data = data_file.read()

    pd0 = PD0DataStructure(data)

    print "%s" % pd0
