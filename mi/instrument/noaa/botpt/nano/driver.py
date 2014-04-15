"""
@package mi.instrument.noaa.nano.ooicore.driver
@file marine-integrations/mi/instrument/noaa/nano/ooicore/driver.py
@author David Everett
@brief Driver for the ooicore
Release notes:

Driver for NANO TILT on the RSN-BOTPT instrument (v.6)

"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import re
import time

from mi.core.log import get_logger


log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.instrument.noaa.botpt.driver import BotptProtocol
from mi.instrument.noaa.botpt.driver import BotptStatusParticle
from mi.instrument.noaa.botpt.driver import NEWLINE
from mi.core.exceptions import InstrumentTimeoutException, InstrumentDataException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import SampleException

###
#    Driver Constant Definitions
###

NANO_STRING = 'NANO,'
NANO_COMMAND_STRING = '*0100'
NANO_DATA_ON = 'E4'  # turns on continuous data
NANO_DATA_OFF = 'E3'  # turns off continuous data
NANO_DUMP_SETTINGS = 'IF'  # outputs current settings
NANO_SET_TIME = 'TS'  # Tells the CPU to set the NANO time
NANO_SET_RATE = '*0100EW*0100TH='
NANO_RATE_RESPONSE = '*0001TH'

MIN_SAMPLE_RATE = 1
MAX_SAMPLE_RATE = 40
DEFAULT_SYNC_INTERVAL = 24 * 60 * 60


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS


class ExportedInstrumentCommand(BaseEnum):
    SET_TIME = "EXPORTED_INSTRUMENT_SET_TIME"
    SET_RATE = "EXPORTED_INSTRUMENT_SET_RATE"


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    DISCOVER = DriverEvent.DISCOVER
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    SET_TIME = ExportedInstrumentCommand.SET_TIME
    SET_RATE = ExportedInstrumentCommand.SET_RATE
    START_DIRECT = DriverEvent.START_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    SET_TIME = ProtocolEvent.SET_TIME


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    OUTPUT_RATE = 'output_rate_hz'
    SYNC_INTERVAL = 'time_sync_interval'


class ScheduledJob(BaseEnum):
    SET_TIME = 'scheduled_time_sync'


###############################################################################
# Command Response (not a particle but uses regex and chunker to parse command
# responses rather than the normal get_response() method)
###############################################################################

class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    DATA_ON = NANO_STRING + NANO_COMMAND_STRING + NANO_DATA_ON  # turns on continuous data
    DATA_OFF = NANO_STRING + NANO_COMMAND_STRING + NANO_DATA_OFF  # turns off continuous data
    DUMP_SETTINGS = NANO_STRING + NANO_COMMAND_STRING + NANO_DUMP_SETTINGS  # outputs current settings
    SET_TIME = NANO_STRING + NANO_SET_TIME  # requests the SBC to update the NANO time
    SET_RATE = NANO_STRING + NANO_SET_RATE  # sets the sample rate in Hz


###############################################################################
# Data Particles
###############################################################################

class DataParticleType(BaseEnum):
    NANO_PARSED = 'botpt_nano_sample'
    NANO_STATUS = 'botpt_nano_status'


class NANODataParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    TIME = "date_time_string"
    PPS_SYNC = "nano_pps_sync"
    PRESSURE = "pressure"
    TEMP = "temperature"


class NANODataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       NANO,V,2013/08/22 22:48:36.013,13.888533,26.147947328
    Format:
       IIII,YYYY/MM/DD hh:mm:ss,x.xxxx,y.yyyy,tt.tt,sn

        ID = IIII = NANO
        Year = YYYY
        Month = MM
        Day = DD
        Hour = hh
        Minutes = mm
        Seconds = ss
        NOTE: The above time expression is all grouped into one string.
        Pressure = x.xxxx (float PSI)
        Temp = tt.tt (float degrees C)
    """
    _data_particle_type = DataParticleType.NANO_PARSED

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'NANO,'  # pattern starts with NANO '
        pattern += r'(V|P),'  # 1 time-sync (PPS or lost)
        pattern += r'(.*),'  # 2 time
        pattern += r'(-*[.0-9]+),'  # 3 pressure (PSIA)
        pattern += r'(-*[.0-9]+)'  # 4 temperature (degrees)
        pattern += r'.*'
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(NANODataParticle.regex())

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = NANODataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            pps_sync = match.group(1)
            nano_time = match.group(2)
            timestamp = time.strptime(nano_time, "%Y/%m/%d %H:%M:%S.%f")
            fraction = float('.' + nano_time.split('.')[1])
            self.set_internal_timestamp(unix_time=time.mktime(timestamp) + fraction)
            pressure = float(match.group(3))
            temperature = float(match.group(4))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: NANODataParticleKey.SENSOR_ID,
             DataParticleKey.VALUE: 'NANO'},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.TIME,
             DataParticleKey.VALUE: nano_time},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.PRESSURE,
             DataParticleKey.VALUE: pressure},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.TEMP,
             DataParticleKey.VALUE: temperature},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.PPS_SYNC,
             DataParticleKey.VALUE: pps_sync},
        ]

        return result


class NANOStatusParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    MODEL_NUMBER = 'model_number'
    SERIAL_NUMBER = 'serial_number'
    FIRMWARE_REVISION = 'firmware_revision'
    FIRMWARE_DATE = 'firmware_date'
    PPS_STATUS = 'pps_status'
    AA = 'AA'
    AC = 'AC'
    AH = 'AH'
    AM = 'AM'
    AP = 'AP'
    AR = 'AR'
    BL = 'BL'
    BR1 = 'BR1'
    BR2 = 'BR2'
    BV = 'BV'
    BX = 'BX'
    C1 = 'C1'
    C2 = 'C2'
    C3 = 'C3'
    CF = 'CF'
    CM = 'CM'
    CS = 'CS'
    D1 = 'D1'
    D2 = 'D2'
    DH = 'DH'
    DL = 'DL'
    DM = 'DM'
    DO = 'DO'
    DP = 'DP'
    DZ = 'DZ'
    EM = 'EM'
    ET = 'ET'
    FD = 'FD'
    FM = 'FM'
    GD = 'GD'
    GE = 'GE'
    GF = 'GF'
    GP = 'GP'
    GT = 'GT'
    IA1 = 'IA1'
    IA2 = 'IA2'
    IB = 'IB'
    ID = 'ID'
    IE = 'IE'
    IK = 'IK'
    IM = 'IM'
    IS = 'IS'
    IY = 'IY'
    KH = 'KH'
    LH = 'LH'
    LL = 'LL'
    M1 = 'M1'
    M3 = 'M3'
    MA = 'MA'
    MD = 'MD'
    MU = 'MU'
    MX = 'MX'
    NO = 'NO'
    OI = 'OI'
    OP = 'OP'
    OR = 'OR'
    OY = 'OY'
    OZ = 'OZ'
    PA = 'PA'
    PC = 'PC'
    PF = 'PF'
    PI = 'PI'
    PL = 'PL'
    PM = 'PM'
    PO = 'PO'
    PR = 'PR'
    PS = 'PS'
    PT = 'PT'
    PX = 'PX'
    RE = 'RE'
    RS = 'RS'
    RU = 'RU'
    SD = 'SD'
    SE = 'SE'
    SI = 'SI'
    SK = 'SK'
    SL = 'SL'
    SM = 'SM'
    SP = 'SP'
    ST = 'ST'
    SU = 'SU'
    T1 = 'T1'
    T2 = 'T2'
    T3 = 'T3'
    T4 = 'T4'
    T5 = 'T5'
    TC = 'TC'
    TF = 'TF'
    TH = 'TH'
    TI = 'TI'
    TJ = 'TJ'
    TP = 'TP'
    TQ = 'TQ'
    TR = 'TR'
    TS = 'TS'
    TU = 'TU'
    U0 = 'U0'
    UE = 'UE'
    UF = 'UF'
    UL = 'UL'
    UM = 'UM'
    UN = 'UN'
    US = 'US'
    VP = 'VP'
    WI = 'WI'
    XC = 'XC'
    XD = 'XD'
    XM = 'XM'
    XN = 'XN'
    XS = 'XS'
    XX = 'XX'
    Y1 = 'Y1'
    Y2 = 'Y2'
    Y3 = 'Y3'
    ZE = 'ZE'
    ZI = 'ZI'
    ZL = 'ZL'
    ZM = 'ZM'
    ZS = 'ZS'
    ZV = 'ZV'


###############################################################################
# Status Particles
###############################################################################
class NANOStatusParticle(BotptStatusParticle):
    _data_particle_type = DataParticleType.NANO_STATUS
    _DEFAULT_ENCODER_KEY = int
    _encoders = {
        NANOStatusParticleKey.SENSOR_ID: unicode,
        NANOStatusParticleKey.MODEL_NUMBER: unicode,
        NANOStatusParticleKey.SERIAL_NUMBER: unicode,
        NANOStatusParticleKey.FIRMWARE_REVISION: unicode,
        NANOStatusParticleKey.FIRMWARE_DATE: unicode,
        NANOStatusParticleKey.AA: float,
        NANOStatusParticleKey.AC: float,
        NANOStatusParticleKey.AH: float,
        NANOStatusParticleKey.AR: float,
        NANOStatusParticleKey.BV: float,
        NANOStatusParticleKey.C1: float,
        NANOStatusParticleKey.C2: float,
        NANOStatusParticleKey.C3: float,
        NANOStatusParticleKey.CF: unicode,
        NANOStatusParticleKey.D1: float,
        NANOStatusParticleKey.D2: float,
        NANOStatusParticleKey.DH: float,
        NANOStatusParticleKey.DZ: float,
        NANOStatusParticleKey.FD: float,
        NANOStatusParticleKey.GP: unicode,
        NANOStatusParticleKey.LH: float,
        NANOStatusParticleKey.LL: float,
        NANOStatusParticleKey.M1: float,
        NANOStatusParticleKey.M3: float,
        NANOStatusParticleKey.MA: unicode,
        NANOStatusParticleKey.MU: unicode,
        NANOStatusParticleKey.OP: float,
        NANOStatusParticleKey.OR: float,
        NANOStatusParticleKey.OY: float,
        NANOStatusParticleKey.PA: float,
        NANOStatusParticleKey.PC: float,
        NANOStatusParticleKey.PF: float,
        NANOStatusParticleKey.PL: float,
        NANOStatusParticleKey.PM: float,
        NANOStatusParticleKey.PT: unicode,
        NANOStatusParticleKey.SI: unicode,
        NANOStatusParticleKey.SM: unicode,
        NANOStatusParticleKey.T1: float,
        NANOStatusParticleKey.T2: float,
        NANOStatusParticleKey.T3: float,
        NANOStatusParticleKey.T4: float,
        NANOStatusParticleKey.T5: float,
        NANOStatusParticleKey.TC: float,
        NANOStatusParticleKey.TF: float,
        NANOStatusParticleKey.TH: unicode,
        NANOStatusParticleKey.U0: float,
        NANOStatusParticleKey.UF: float,
        NANOStatusParticleKey.UL: unicode,
        NANOStatusParticleKey.UM: unicode,
        NANOStatusParticleKey.WI: unicode,
        NANOStatusParticleKey.XD: unicode,
        NANOStatusParticleKey.Y1: float,
        NANOStatusParticleKey.Y2: float,
        NANOStatusParticleKey.Y3: float,
        NANOStatusParticleKey.ZV: float,
    }

    @staticmethod
    def regex():
        """
        Example of output from DUMP-SETTINGS command:
        
        NANO,*______________________________________________________________
        NANO,*PAROSCIENTIFIC SMT SYSTEM INFORMATION
        NANO,*Model Number: 42.4K-265               
        NANO,*Serial Number: 120785
        NANO,*Firmware Revision: R5.20
        NANO,*Firmware Release Date: 03-25-13
        NANO,*PPS status: V : PPS signal NOT detected.
        NANO,*--------------------------------------------------------------
        NANO,*AA:7.161800     AC:7.290000     AH:160.0000     AM:0            
        NANO,*AP:0            AR:160.0000     BL:0            BR1:115200      
        NANO,*BR2:115200      BV:10.9         BX:112          C1:-9747.897    
        NANO,*C2:288.5739     C3:27200.78     CF:BA0F         CM:4            
        NANO,*CS:7412         D1:.0572567     D2:.0000000     DH:2000.000     
        NANO,*DL:0            DM:0            DO:0            DP:6            
        NANO,*DZ:.0000000     EM:0            ET:0            FD:.153479      
        NANO,*FM:0            GD:0            GE:2            GF:0            
        NANO,*GP::            GT:1            IA1:8           IA2:12          
        NANO,*IB:0            ID:1            IE:0            IK:46           
        NANO,*IM:0            IS:5            IY:0            KH:0            
        NANO,*LH:2250.000     LL:.0000000     M1:13.880032    M3:14.090198    
        NANO,*MA:             MD:0            MU:             MX:0            
        NANO,*NO:0            OI:0            OP:2100.000     OR:1.00         
        NANO,*OY:1.000000     OZ:0            PA:.0000000     PC:.0000000     
        NANO,*PF:2000.000     PI:25           PL:2400.000     PM:1.000000     
        NANO,*PO:0            PR:238          PS:0            PT:N            
        NANO,*PX:3            RE:0            RS:5            RU:0            
        NANO,*SD:12           SE:0            SI:OFF          SK:0            
        NANO,*SL:0            SM:OFF          SP:0            ST:10           
        NANO,*SU:0            T1:30.00412     T2:1.251426     T3:50.64434     
        NANO,*T4:134.5816     T5:.0000000     TC:.6781681     TF:.00          
        NANO,*TH:1,P4;>OK     TI:25           TJ:2            TP:0            
        NANO,*TQ:1            TR:952          TS:1            TU:0            
        NANO,*U0:5.839037     UE:0            UF:1.000000     
        NANO,*UL:                             UM:user         UN:1            
        NANO,*US:0            VP:4            WI:Def=15:00-061311             
        NANO,*XC:8            XD:A            XM:1            XN:0            
        NANO,*XS:0011         XX:1            Y1:-3818.141    Y2:-10271.53    
        NANO,*Y3:.0000000     ZE:0            ZI:0            ZL:0            
        NANO,*ZM:0            ZS:0            ZV:.0000000     
        """
        return r'(NANO,\*_.*?ZV:\s*\S*.*?)' + NEWLINE

    @staticmethod
    def regex_compiled():
        return re.compile(NANOStatusParticle.regex(), re.DOTALL)

    @classmethod
    def _regex_multiline(cls):
        return {
            NANOStatusParticleKey.SENSOR_ID: r'(NANO),',
            NANOStatusParticleKey.MODEL_NUMBER: r'Model Number: \S+',
            NANOStatusParticleKey.SERIAL_NUMBER: r'Serial Number: \S+',
            NANOStatusParticleKey.FIRMWARE_REVISION: r'Firmware Revision: \S+',
            NANOStatusParticleKey.FIRMWARE_DATE: r'Firmware Release Date: \S+',
            NANOStatusParticleKey.PPS_STATUS: r'PPS status: .+',
            NANOStatusParticleKey.AA: r'AA:(\S*)',
            NANOStatusParticleKey.AC: r'AC:(\S*)',
            NANOStatusParticleKey.AH: r'AH:(\S*)',
            NANOStatusParticleKey.AM: r'AM:(\S*)',
            NANOStatusParticleKey.AP: r'AP:(\S*)',
            NANOStatusParticleKey.AR: r'AR:(\S*)',
            NANOStatusParticleKey.BL: r'BL:(\S*)',
            NANOStatusParticleKey.BR1: r'BR1:(\S*)',
            NANOStatusParticleKey.BR2: r'BR2:(\S*)',
            NANOStatusParticleKey.BV: r'BV:(\S*)',
            NANOStatusParticleKey.BX: r'BX:(\S*)',
            NANOStatusParticleKey.C1: r'C1:(\S*)',
            NANOStatusParticleKey.C2: r'C2:(\S*)',
            NANOStatusParticleKey.C3: r'C3:(\S*)',
            NANOStatusParticleKey.CF: r'CF:(\S*)',
            NANOStatusParticleKey.CM: r'CM:(\S*)',
            NANOStatusParticleKey.CS: r'CS:(\S*)',
            NANOStatusParticleKey.D1: r'D1:(\S*)',
            NANOStatusParticleKey.D2: r'D2:(\S*)',
            NANOStatusParticleKey.DH: r'DH:(\S*)',
            NANOStatusParticleKey.DL: r'DL:(\S*)',
            NANOStatusParticleKey.DM: r'DM:(\S*)',
            NANOStatusParticleKey.DO: r'DO:(\S*)',
            NANOStatusParticleKey.DP: r'DP:(\S*)',
            NANOStatusParticleKey.DZ: r'DZ:(\S*)',
            NANOStatusParticleKey.EM: r'EM:(\S*)',
            NANOStatusParticleKey.ET: r'ET:(\S*)',
            NANOStatusParticleKey.FD: r'FD:(\S*)',
            NANOStatusParticleKey.FM: r'FM:(\S*)',
            NANOStatusParticleKey.GD: r'GD:(\S*)',
            NANOStatusParticleKey.GE: r'GE:(\S*)',
            NANOStatusParticleKey.GF: r'GF:(\S*)',
            NANOStatusParticleKey.GP: r'GP:(\S*)',
            NANOStatusParticleKey.GT: r'GT:(\S*)',
            NANOStatusParticleKey.IA1: r'IA1:(\S*)',
            NANOStatusParticleKey.IA2: r'IA2:(\S*)',
            NANOStatusParticleKey.IB: r'IB:(\S*)',
            NANOStatusParticleKey.ID: r'ID:(\S*)',
            NANOStatusParticleKey.IE: r'IE:(\S*)',
            NANOStatusParticleKey.IK: r'IK:(\S*)',
            NANOStatusParticleKey.IM: r'IM:(\S*)',
            NANOStatusParticleKey.IS: r'IS:(\S*)',
            NANOStatusParticleKey.IY: r'IY:(\S*)',
            NANOStatusParticleKey.KH: r'KH:(\S*)',
            NANOStatusParticleKey.LH: r'LH:(\S*)',
            NANOStatusParticleKey.LL: r'LL:(\S*)',
            NANOStatusParticleKey.M1: r'M1:(\S*)',
            NANOStatusParticleKey.M3: r'M3:(\S*)',
            NANOStatusParticleKey.MA: r'MA:(\S*)',
            NANOStatusParticleKey.MD: r'MD:(\S*)',
            NANOStatusParticleKey.MU: r'MU:(\S*)',
            NANOStatusParticleKey.MX: r'MX:(\S*)',
            NANOStatusParticleKey.NO: r'NO:(\S*)',
            NANOStatusParticleKey.OI: r'OI:(\S*)',
            NANOStatusParticleKey.OP: r'OP:(\S*)',
            NANOStatusParticleKey.OR: r'OR:(\S*)',
            NANOStatusParticleKey.OY: r'OY:(\S*)',
            NANOStatusParticleKey.OZ: r'OZ:(\S*)',
            NANOStatusParticleKey.PA: r'PA:(\S*)',
            NANOStatusParticleKey.PC: r'PC:(\S*)',
            NANOStatusParticleKey.PF: r'PF:(\S*)',
            NANOStatusParticleKey.PI: r'PI:(\S*)',
            NANOStatusParticleKey.PL: r'PL:(\S*)',
            NANOStatusParticleKey.PM: r'PM:(\S*)',
            NANOStatusParticleKey.PO: r'PO:(\S*)',
            NANOStatusParticleKey.PR: r'PR:(\S*)',
            NANOStatusParticleKey.PS: r'PS:(\S*)',
            NANOStatusParticleKey.PT: r'PT:(\S*)',
            NANOStatusParticleKey.PX: r'PX:(\S*)',
            NANOStatusParticleKey.RE: r'RE:(\S*)',
            NANOStatusParticleKey.RS: r'RS:(\S*)',
            NANOStatusParticleKey.RU: r'RU:(\S*)',
            NANOStatusParticleKey.SD: r'SD:(\S*)',
            NANOStatusParticleKey.SE: r'SE:(\S*)',
            NANOStatusParticleKey.SI: r'SI:(\S*)',
            NANOStatusParticleKey.SK: r'SK:(\S*)',
            NANOStatusParticleKey.SL: r'SL:(\S*)',
            NANOStatusParticleKey.SM: r'SM:(\S*)',
            NANOStatusParticleKey.SP: r'SP:(\S*)',
            NANOStatusParticleKey.ST: r'ST:(\S*)',
            NANOStatusParticleKey.SU: r'SU:(\S*)',
            NANOStatusParticleKey.T1: r'T1:(\S*)',
            NANOStatusParticleKey.T2: r'T2:(\S*)',
            NANOStatusParticleKey.T3: r'T3:(\S*)',
            NANOStatusParticleKey.T4: r'T4:(\S*)',
            NANOStatusParticleKey.T5: r'T5:(\S*)',
            NANOStatusParticleKey.TC: r'TC:(\S*)',
            NANOStatusParticleKey.TF: r'TF:(\S*)',
            NANOStatusParticleKey.TH: r'TH:(\S*)',
            NANOStatusParticleKey.TI: r'TI:(\S*)',
            NANOStatusParticleKey.TJ: r'TJ:(\S*)',
            NANOStatusParticleKey.TP: r'TP:(\S*)',
            NANOStatusParticleKey.TQ: r'TQ:(\S*)',
            NANOStatusParticleKey.TR: r'TR:(\S*)',
            NANOStatusParticleKey.TS: r'TS:(\S*)',
            NANOStatusParticleKey.TU: r'TU:(\S*)',
            NANOStatusParticleKey.U0: r'U0:(\S*)',
            NANOStatusParticleKey.UE: r'UE:(\S*)',
            NANOStatusParticleKey.UF: r'UF:(\S*)',
            NANOStatusParticleKey.UL: r'UL:(\S*)',
            NANOStatusParticleKey.UM: r'UM:(\S*)',
            NANOStatusParticleKey.UN: r'UN:(\S*)',
            NANOStatusParticleKey.US: r'US:(\S*)',
            NANOStatusParticleKey.VP: r'VP:(\S*)',
            NANOStatusParticleKey.WI: r'WI:(\S*)',
            NANOStatusParticleKey.XC: r'XC:(\S*)',
            NANOStatusParticleKey.XD: r'XD:(\S*)',
            NANOStatusParticleKey.XM: r'XM:(\S*)',
            NANOStatusParticleKey.XN: r'XN:(\S*)',
            NANOStatusParticleKey.XS: r'XS:(\S*)',
            NANOStatusParticleKey.XX: r'XX:(\S*)',
            NANOStatusParticleKey.Y1: r'Y1:(\S*)',
            NANOStatusParticleKey.Y2: r'Y2:(\S*)',
            NANOStatusParticleKey.Y3: r'Y3:(\S*)',
            NANOStatusParticleKey.ZE: r'ZE:(\S*)',
            NANOStatusParticleKey.ZI: r'ZI:(\S*)',
            NANOStatusParticleKey.ZL: r'ZL:(\S*)',
            NANOStatusParticleKey.ZM: r'ZM:(\S*)',
            NANOStatusParticleKey.ZS: r'ZS:(\S*)',
            NANOStatusParticleKey.ZV: r'ZV:(\S*)',
        }


###############################################################################
# Driver
###############################################################################

class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """

    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################
    # noinspection PyMethodMayBeStatic
    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(BaseEnum, NEWLINE, self._driver_event)


# noinspection PyMethodMayBeStatic,PyUnusedLocal
class Protocol(BotptProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        BotptProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        handlers = {
            ProtocolState.UNKNOWN: [
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.EXIT, self._handler_unknown_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.AUTOSAMPLE: [
                (ProtocolEvent.ENTER, self._handler_autosample_enter),
                (ProtocolEvent.EXIT, self._handler_autosample_exit),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status),
                (ProtocolEvent.SET_TIME, self._handler_command_autosample_set_time),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status),
                (ProtocolEvent.SET_TIME, self._handler_command_autosample_set_time),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_direct_access_exit),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
            ],
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCommand.DATA_ON, self._build_command)
        self._add_build_handler(InstrumentCommand.DATA_OFF, self._build_command)
        self._add_build_handler(InstrumentCommand.DUMP_SETTINGS, self._build_command)
        self._add_build_handler(InstrumentCommand.SET_TIME, self._build_command)
        self._add_build_handler(InstrumentCommand.SET_RATE, self._build_rate_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCommand.DATA_ON, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DATA_OFF, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DUMP_SETTINGS, self._parse_dump_settings_resp)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)
        self.initialize_scheduler()

        # set up the regexes now so we don't have to do it repeatedly
        self.data_regex = NANODataParticle.regex_compiled()
        self.status_01_regex = NANOStatusParticle.regex_compiled()
        self._last_data_timestamp = 0
        self._filter_string = NANO_STRING

        # We start up assuming the PPS is available, so as not to send an extra TIME_SYNC.
        self.has_pps = True

    def _config_scheduler(self):
        job_name = ScheduledJob.SET_TIME
        config = {
            DriverConfigKey.SCHEDULER: {
                job_name: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: self._param_dict.get(Parameter.SYNC_INTERVAL)
                    },
                }
            }
        }
        if self._scheduler is not None:
            try:
                self._remove_scheduler(ScheduledJob.SET_TIME)
            except KeyError:
                log.debug("_remove_scheduler could not find: %s", ScheduledJob.SET_TIME)

        self.set_init_params(config)
        self._add_scheduler_event(ScheduledJob.SET_TIME, ProtocolEvent.SET_TIME)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        matchers = []
        return_list = []

        matchers.append(NANODataParticle.regex_compiled())
        matchers.append(NANOStatusParticle.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="acquire status")
        self._cmd_dict.add(Capability.SET_TIME, display_name="set time from sbc")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        self._param_dict.add(Parameter.OUTPUT_RATE,
                             'TH:(\d+)',
                             lambda x: int(x.group(1)),
                             int,
                             type=ParameterDictType.INT,
                             display_name='NANO pressure sensor output rate (Hz)',
                             default_value=40)
        self._param_dict.add(Parameter.SYNC_INTERVAL,
                             'None - Not Applicable',
                             None,
                             int,
                             type=ParameterDictType.INT,
                             display_name='NANO time sync interval, in seconds',
                             default_value=DEFAULT_SYNC_INTERVAL)
        self._param_dict.set_value(Parameter.OUTPUT_RATE, 40)
        self._param_dict.set_value(Parameter.SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL)

    def _build_rate_command(self, cmd, *args, **kwargs):
        return '%s%d%s' % (cmd, self._param_dict.get(Parameter.OUTPUT_RATE), NEWLINE)

    def _got_chunk(self, chunk, timestamp):
        """
        Got a chunk, attempt to create a particle
        """
        log.debug("_got_chunk: %s", chunk)
        sync_lost = u'V'
        sample = self._extract_sample(NANODataParticle, NANODataParticle.regex_compiled(), chunk, timestamp)
        if sample:
            values = sample.get(DataParticleKey.VALUES, [])
            for v in values:
                if v.get(DataParticleKey.VALUE_ID) == NANODataParticleKey.PPS_SYNC:
                    pps_sync = v.get(DataParticleKey.VALUE)
                    # last particle was in sync, this one is out of sync.
                    if self.has_pps and pps_sync == sync_lost:
                        log.trace('_got_chunk detected PPS lost, setting has_pps to False')
                        self.has_pps = False
                    # last particle was out of sync, this one is in sync.  Request time update.
                    elif not self.has_pps and pps_sync != sync_lost:
                        log.trace('_got_chunk detected PPS regained, raising SET_TIME event')
                        self.has_pps = True
                        self._async_raise_fsm_event(ProtocolEvent.SET_TIME)
        else:
            sample = self._extract_sample(NANOStatusParticle, NANOStatusParticle.regex_compiled(), chunk, timestamp)
        if not sample:
            raise InstrumentProtocolException('unhandled chunk: %r', chunk)

    def _parse_data_on_off_resp(self, response, prompt):
        log.debug("_parse_data_on_off_resp: response: %r; prompt: %s", response, prompt)

    def _parse_dump_settings_resp(self, response, prompt):
        log.debug("_parse_dump_settings_resp: response: %r; prompt: %s", response, prompt)
        if self.get_current_state() == ProtocolState.UNKNOWN:
            self._param_dict.update(response)
        else:
            old_config = self._param_dict.get_config()
            self._param_dict.update(response)
            if old_config != self._param_dict.get_config():
                self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """
        # Attempt to find a line containing a NANO sample
        # If a sample is found, go to AUTOSAMPLE, otherwise COMMAND
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.IDLE
        result = None
        try:
            # clear out the buffers to ensure we are getting new data
            # this is necessary when discovering out of direct access.
            self._promptbuf = ''
            self._linebuf = ''
            response = self._get_response(timeout=2, response_regex=self.data_regex)
            log.debug('_handler_unknown_discover: response: [%r]', response)
            # autosample
            if response:
                next_state = ProtocolState.AUTOSAMPLE
                next_agent_state = ResourceAgentState.STREAMING
                result = ProtocolState.AUTOSAMPLE
        # timed out, assume command
        except InstrumentTimeoutException:
            pass

        # Verify scheduled job exists for daily time sync
        # If not, request an immediate sync, then schedule the next one
        scheduler_config = self._get_scheduler_config()
        log.debug('scheduler_config: %r', scheduler_config)
        if scheduler_config is None:
            self._handler_command_autosample_set_time()
            # setting the time starts autosampling.  If next_state is COMMAND, stop it.
            if next_state == ProtocolState.COMMAND:
                self._handler_autosample_stop_autosample()
            self._config_scheduler()
        # Acquire the configuration to populate the config dict
        self._handler_command_autosample_acquire_status()
        # Acquiring status stops autosample.  If we were in autosample, restart it.
        if next_state == ProtocolState.AUTOSAMPLE:
            self._handler_command_start_autosample()

        return next_state, next_agent_state

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_stop_autosample(self):
        """
        Turn the nano data off
        """
        return self._handler_command_generic(InstrumentCommand.DATA_OFF,
                                             ProtocolState.COMMAND,
                                             ResourceAgentState.COMMAND)

    def _handler_autosample_sync_lost(self):
        raise InstrumentDataException('BOTPT NANO PPS sync lost')

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        log.debug("_handler_command_get [%r] [%r]", args, kwargs)
        param_list = self._get_param_list(*args, **kwargs)
        result = self._get_param_result(param_list, None)
        next_state = None
        return next_state, result

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter.  NANO only has one parameter, Parameter.OUTPUT_RATE
        """
        log.debug("_handler_command_set")

        next_state = None
        result = None
        found = False
        rate_change = False
        sync_change = False

        input_params = args[0]
        log.debug('input_params: %r', input_params)

        for key, value in input_params.items():
            if not Parameter.has(key):
                raise InstrumentProtocolException('Invalid parameter supplied to set: %s' % key)

            try:
                value = int(value)
            except TypeError:
                raise InstrumentProtocolException('Invalid value [%s] for parameter %s' % (value, key))

            if key == Parameter.OUTPUT_RATE:
                if value < MIN_SAMPLE_RATE or value > MAX_SAMPLE_RATE:
                    raise InstrumentProtocolException('Invalid sample rate: %s' % value)
                rate_change = True
            if key == Parameter.SYNC_INTERVAL:
                sync_change = True
            # Did the value change?
            old_value = self._param_dict.get(key)
            if value == old_value:
                log.info('Parameter %s already %s, not changing', key, value)
            else:
                log.info('Setting parameter %s to %s', key, value)
                self._param_dict.set_value(key, value)
                found = True
        if found:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
            if rate_change:
                self._handler_command_generic(InstrumentCommand.SET_RATE,
                                              None, None,
                                              expected_prompt=NANO_RATE_RESPONSE)
            if sync_change:
                self._config_scheduler()

        return next_state, result

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Turn the nano data on
        """
        return self._handler_command_generic(InstrumentCommand.DATA_ON,
                                             ProtocolState.AUTOSAMPLE,
                                             ResourceAgentState.STREAMING,
                                             expected_prompt=NANO_STRING)

    ########################################################################
    # Handlers common to Command and Autosample States.
    ########################################################################

    def _handler_command_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        result = self._handler_command_generic(InstrumentCommand.DUMP_SETTINGS,
                                               None, None,
                                               response_regex=NANOStatusParticle.regex_compiled())
        # Acquiring status stops autosample.  If we're in autosample, restart it.
        if self._protocol_fsm.get_current_state() == ProtocolState.AUTOSAMPLE:
            self._handler_command_start_autosample()
        return result

    def _handler_command_autosample_set_time(self, *args, **kwargs):
        """
        Request the SBC to update the NANO time
        """
        next_state = None
        next_agent_state = None
        result = None
        log.debug("_handler_command_autosample_set_time")

        timeout = kwargs.get('timeout')
        self._handler_command_generic(InstrumentCommand.SET_TIME,
                                      None, None,
                                      expected_prompt='*0001GR')
        # setting the time starts autosampling!
        # stop if we're actually in the command state.
        if self.get_current_state() == ProtocolState.COMMAND:
            self._handler_autosample_stop_autosample()

        return next_state, (next_agent_state, result)