
from mi.instrument.seabird.sbe54tps.ooicore.driver import NEWLINE

SAMPLE_GETSD =  "S>getsd" + NEWLINE + \
                "getsd" + NEWLINE + \
                "<StatusData DeviceType='SBE54' SerialNumber='05400012'>" + NEWLINE + \
                "<DateTime>2012-11-06T10:55:44</DateTime>" + NEWLINE + \
                "<EventSummary numEvents='573'/>" + NEWLINE + \
                "<Power>" + NEWLINE + \
                "<MainSupplyVoltage>23.3</MainSupplyVoltage>" + NEWLINE + \
                "</Power>" + NEWLINE + \
                "<MemorySummary>" + NEWLINE + \
                "<Samples>22618</Samples>" + NEWLINE + \
                "<Bytes>341504</Bytes>" + NEWLINE + \
                "<BytesFree>133876224</BytesFree>" + NEWLINE + \
                "</MemorySummary>" + NEWLINE + \
                "</StatusData>"

SAMPLE_GETCD =  "S>getcd" + NEWLINE +\
                "getcd" + NEWLINE +\
                "<ConfigurationData DeviceType='SBE54' SerialNumber='05400012'>" + NEWLINE +\
                "<CalibrationCoefficients>" + NEWLINE +\
                "<AcqOscCalDate>2012-02-20</AcqOscCalDate>" + NEWLINE +\
                "<FRA0>5.999926E+06</FRA0>" + NEWLINE +\
                "<FRA1>5.792290E-03</FRA1>" + NEWLINE +\
                "<FRA2>-1.195664E-07</FRA2>" + NEWLINE +\
                "<FRA3>7.018589E-13</FRA3>" + NEWLINE +\
                "<PressureSerialNum>121451</PressureSerialNum>" + NEWLINE +\
                "<PressureCalDate>2011-06-01</PressureCalDate>" + NEWLINE +\
                "<pu0>5.820407E+00</pu0>" + NEWLINE +\
                "<py1>-3.845374E+03</py1>" + NEWLINE +\
                "<py2>-1.078882E+04</py2>" + NEWLINE +\
                "<py3>0.000000E+00</py3>" + NEWLINE +\
                "<pc1>-2.700543E+04</pc1>" + NEWLINE +\
                "<pc2>-1.738438E+03</pc2>" + NEWLINE +\
                "<pc3>7.629962E+04</pc3>" + NEWLINE +\
                "<pd1>3.739600E-02</pd1>" + NEWLINE +\
                "<pd2>0.000000E+00</pd2>" + NEWLINE +\
                "<pt1>3.027306E+01</pt1>" + NEWLINE +\
                "<pt2>2.231025E-01</pt2>" + NEWLINE +\
                "<pt3>5.398972E+01</pt3>" + NEWLINE +\
                "<pt4>1.455506E+02</pt4>" + NEWLINE +\
                "<poffset>0.000000E+00</poffset>" + NEWLINE +\
                "<prange>6.000000E+03</prange>" + NEWLINE +\
                "</CalibrationCoefficients>" + NEWLINE +\
                "<Settings" + NEWLINE +\
                "batteryType='0'" + NEWLINE +\
                "baudRate='9600'" + NEWLINE +\
                "enableAlerts='0'" + NEWLINE +\
                "uploadType='0'" + NEWLINE +\
                "samplePeriod='15'" + NEWLINE +\
                "/>" + NEWLINE +\
                "</ConfigurationData>"

SAMPLE_GETEC =  "S>getec" + NEWLINE +\
                "getec" + NEWLINE +\
                "<EventSummary numEvents='573' maxStack='354'/>" + NEWLINE +\
                "<EventList DeviceType='SBE54' SerialNumber='05400012'>" + NEWLINE +\
                "<Event type='PowerOnReset' count='25'/>" + NEWLINE +\
                "<Event type='PowerFailReset' count='25'/>" + NEWLINE +\
                "<Event type='SerialByteErr' count='9'/>" + NEWLINE +\
                "<Event type='CMDBuffOflow' count='1'/>" + NEWLINE +\
                "<Event type='SerialRxOflow' count='255'/>" + NEWLINE +\
                "<Event type='LowBattery' count='255'/>" + NEWLINE +\
                "<Event type='SignalErr' count='1'/>" + NEWLINE +\
                "<Event type='Error10' count='1'/>" + NEWLINE +\
                "<Event type='Error12' count='1'/>" + NEWLINE +\
                "</EventList>"

SAMPLE_GETHD =  "S>gethd" + NEWLINE +\
                "gethd" + NEWLINE +\
                "<HardwareData DeviceType='SBE54' SerialNumber='05400012'>" + NEWLINE +\
                "<Manufacturer>Sea-Bird Electronics, Inc</Manufacturer>" + NEWLINE +\
                "<FirmwareVersion>SBE54 V1.3-6MHZ</FirmwareVersion>" + NEWLINE +\
                "<FirmwareDate>Mar 22 2007</FirmwareDate>" + NEWLINE +\
                "<HardwareVersion>41477A.1</HardwareVersion>" + NEWLINE +\
                "<HardwareVersion>41478A.1T</HardwareVersion>" + NEWLINE +\
                "<PCBSerialNum>NOT SET</PCBSerialNum>" + NEWLINE +\
                "<PCBSerialNum>NOT SET</PCBSerialNum>" + NEWLINE +\
                "<PCBType>1</PCBType>" + NEWLINE +\
                "<MfgDate>Jun 27 2007</MfgDate>" + NEWLINE +\
                "</HardwareData>"

SAMPLE_SAMPLE = "<Sample Num='5947' Type='Pressure'>" + NEWLINE +\
                "<Time>2012-11-07T12:21:25</Time>" + NEWLINE +\
                "<PressurePSI>13.9669</PressurePSI>" + NEWLINE +\
                "<PTemp>18.9047</PTemp>" + NEWLINE +\
                "</Sample>"

SAMPLE_TEST_REF_OSC = "S>TestRefOsc" + NEWLINE +\
                      "TestRefOsc" + NEWLINE +\
                      "<SetTimeout>120000</SetTimeout>" + NEWLINE +\
                      "<SetTimeoutMax>OFF</SetTimeoutMax>" + NEWLINE +\
                      "<SetTimeoutICD>120000</SetTimeoutICD>" + NEWLINE +\
                      "<!--Ref osc warmup next 120 seconds-->" + NEWLINE +\
                      "<!--Warmup complete, starting measurement at 0.1Hz-->" + NEWLINE +\
                      "<SetTimeout>15000</SetTimeout>" + NEWLINE +\
                      "<SetTimeoutICD>15000</SetTimeoutICD>" + NEWLINE +\
                      "<ReferenceOscTest DeviceType='SBE54' SerialNumber='05400012'>" + NEWLINE +\
                      "5999996.190 18486  0.076" + NEWLINE +\
                      "5999996.040 18468  0.095" + NEWLINE +\
                      "5999996.140 18450  0.072" + NEWLINE +\
                      "5999996.040 18432  0.082" + NEWLINE +\
                      "5999995.955 18414  0.090" + NEWLINE +\
                      "5999995.940 18396  0.086" + NEWLINE +\
                      "5999995.940 18378  0.080" + NEWLINE +\
                      "5999995.940 18360  0.074" + NEWLINE +\
                      "5999995.840 18343  0.084" + NEWLINE +\
                      "5999995.740 18326  0.095" + NEWLINE +\
                      "5999995.840 18309  0.072" + NEWLINE +\
                      "5999995.640 18293  0.100" + NEWLINE +\
                      "5999995.740 18277  0.078" + NEWLINE +\
                      "5999995.640 18261  0.089" + NEWLINE +\
                      "5999995.640 18245  0.083" + NEWLINE +\
                      "5999995.640 18230  0.078" + NEWLINE +\
                      "5999995.540 18215  0.089" + NEWLINE +\
                      "5999995.540 18200  0.084" + NEWLINE +\
                      "5999995.540 18185  0.078" + NEWLINE +\
                      "5999995.440 18170  0.090" + NEWLINE +\
                      "5999995.454 18156  0.082" + NEWLINE +\
                      "5999995.340 18142  0.096" + NEWLINE +\
                      "5999995.440 18128  0.075" + NEWLINE +\
                      "5999995.340 18114  0.086" + NEWLINE +\
                      "5999995.340 18101  0.082" + NEWLINE +\
                      "5999995.240 18088  0.094" + NEWLINE +\
                      "5999995.240 18075  0.089" + NEWLINE +\
                      "5999995.240 18062  0.084" + NEWLINE +\
                      "5999995.240 18049  0.080" + NEWLINE +\
                      "5999995.140 18037  0.092" + NEWLINE +\
                      "5999995.140 18025  0.088" + NEWLINE +\
                      "5999995.140 18013  0.083" + NEWLINE +\
                      "</ReferenceOscTest>" + NEWLINE



SAMPLE_samplerefosc = "S>samplerefosc" + NEWLINE +\
                      "samplerefosc" + NEWLINE +\
                      "<SetTimeout>125000</SetTimeout>" + NEWLINE +\
                      "<SetTimeoutMax>150000</SetTimeoutMax>" + NEWLINE +\
                      "<SetTimeoutICD>125000</SetTimeoutICD>" + NEWLINE +\
                      "<!--Ref osc warmup next 120 seconds-->" + NEWLINE +\
                      "<!--Warmup complete, starting measurement at 0.1Hz-->" + NEWLINE +\
                      "<Sample Num='336160' Type='Pressure'>" + NEWLINE +\
                      "<Time>2012-11-19T10:21:22</Time>" + NEWLINE +\
                      "<PressurePSI>13.6135</PressurePSI>" + NEWLINE +\
                      "<PTemp>18.7733</PTemp>" + NEWLINE +\
                      "</Sample>" + NEWLINE