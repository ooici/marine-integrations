def crc3kerm(buf):
    crcta = [0, 4225, 8450, 12675, 16900, 21125, 25350, 29575, \
             33800, 38025, 42250, 46475, 50700, 54925, 59150, 63375]
    crctb = [0, 4489, 8978, 12955, 17956, 22445, 25910, 29887, \
             35912, 40385, 44890, 48851, 51820, 56293, 59774, 63735]
    crc = 0
    for i in range(0, len(buf)):
        c = crc ^ ord(buf[i])
        hi4 = (c & 240) >> 4
        lo4 = c & 15
        crc = (crc >> 8) ^ (crcta[hi4] ^ crctb[lo4])
    return crc


def chksumnmea(s):
    xor = 0;
    for i in range(0, len(s)):
        xor ^= ord(s[i]);
    return xor
