


from mi.instrument.seabird.sbe26plus.ooicore.driver import NEWLINE


SAMPLE_TIDE_DATA = "tide: start time = 05 Oct 2012 01:10:54, p = 14.5385, pt = 24.228, t = 23.8404" + NEWLINE

SAMPLE_DEVICE_STATUS =\
"SBE 26plus V 6.1e  SN 1329    05 Oct 2012  17:19:27" + NEWLINE +\
"user info=ooi" + NEWLINE +\
"quartz pressure sensor: serial number = 122094, range = 300 psia" + NEWLINE +\
"internal temperature sensor" + NEWLINE +\
"conductivity = NO" + NEWLINE +\
"iop =  7.4 ma  vmain = 16.2 V  vlith =  9.0 V" + NEWLINE +\
"last sample: p = 14.5361, t = 23.8155, s =  0.0000" + NEWLINE +\
"" + NEWLINE +\
"tide measurement: interval = 3.000 minutes, duration = 60 seconds" + NEWLINE +\
"measure waves every 6 tide samples" + NEWLINE +\
"512 wave samples/burst at 4.00 scans/sec, duration = 128 seconds" + NEWLINE +\
"logging start time = do not use start time" + NEWLINE +\
"logging stop time = do not use stop time" + NEWLINE +\
"" + NEWLINE +\
"tide samples/day = 480.000" + NEWLINE +\
"wave bursts/day = 80.000" + NEWLINE +\
"memory endurance = 258.0 days" + NEWLINE +\
"nominal alkaline battery endurance = 272.8 days" + NEWLINE +\
"total recorded tide measurements = 5982" + NEWLINE +\
"total recorded wave bursts = 4525" + NEWLINE +\
"tide measurements since last start = 11" + NEWLINE +\
"wave bursts since last start = 1" + NEWLINE +\
"" + NEWLINE +\
"transmit real-time tide data = YES" + NEWLINE +\
"transmit real-time wave burst data = YES" + NEWLINE +\
"transmit real-time wave statistics = YES" + NEWLINE +\
"real-time wave statistics settings:" + NEWLINE +\
"  number of wave samples per burst to use for wave statistics = 512" + NEWLINE +\
"  use measured temperature for density calculation" + NEWLINE +\
"  height of pressure sensor from bottom (meters) = 10.0" + NEWLINE +\
"  number of spectral estimates for each frequency band = 5" + NEWLINE +\
"  minimum allowable attenuation = 0.0025" + NEWLINE +\
"  minimum period (seconds) to use in auto-spectrum = 0.0e+00" + NEWLINE +\
"  maximum period (seconds) to use in auto-spectrum = 1.0e+06" + NEWLINE +\
"  hanning window cutoff = 0.10" + NEWLINE +\
"  show progress messages" + NEWLINE +\
"" + NEWLINE +\
"status = stopped by user" + NEWLINE +\
"logging = NO, send start command to begin logging" + NEWLINE

SAMPLE_DEVICE_CALIBRATION =\
"Pressure coefficients:  02-apr-13" + NEWLINE +\
"    U0 = 5.100000e+00" + NEWLINE +\
"    Y1 = -3.910859e+03" + NEWLINE +\
"    Y2 = -1.070825e+04" + NEWLINE +\
"    Y3 = 0.000000e+00" + NEWLINE +\
"    C1 = 6.072786e+02" + NEWLINE +\
"    C2 = 1.000000e+00" + NEWLINE +\
"    C3 = -1.024374e+03" + NEWLINE +\
"    D1 = 2.928000e-02" + NEWLINE +\
"    D2 = 0.000000e+00" + NEWLINE +\
"    T1 = 2.783369e+01" + NEWLINE +\
"    T2 = 6.072020e-01" + NEWLINE +\
"    T3 = 1.821885e+01" + NEWLINE +\
"    T4 = 2.790597e+01" + NEWLINE +\
"    M = 41943.0" + NEWLINE +\
"    B = 2796.2" + NEWLINE +\
"    OFFSET = -1.374000e-01" + NEWLINE +\
"Temperature coefficients:  02-apr-13" + NEWLINE +\
"    TA0 = 1.200000e-04" + NEWLINE +\
"    TA1 = 2.558000e-04" + NEWLINE +\
"    TA2 = -2.073449e-06" + NEWLINE +\
"    TA3 = 1.640089e-07" + NEWLINE +\
"Conductivity coefficients:  28-mar-12" + NEWLINE +\
"    CG = -1.025348e+01" + NEWLINE +\
"    CH = 1.557569e+00" + NEWLINE +\
"    CI = -1.737200e-03" + NEWLINE +\
"    CJ = 2.268000e-04" + NEWLINE +\
"    CTCOR = 3.250000e-06" + NEWLINE +\
"    CPCOR = -9.570000e-08" + NEWLINE +\
"    CSLOPE = 1.000000e+00" + NEWLINE

SAMPLE_WAVE_BURST =\
"wave: start time = 05 Oct 2012 01:10:54" + NEWLINE +\
"wave: ptfreq = 171791.359" + NEWLINE +\
"  14.5102" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5078" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5078" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5064" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5188" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5097" + NEWLINE + "  14.5134" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"wave: end burst" + NEWLINE

SAMPLE_STATISTICS =\
"deMeanTrend................" + NEWLINE +\
"depth =    0.000, temperature = 23.840, salinity = 35.000, density = 1023.690" + NEWLINE +\
"" + NEWLINE +\
"fill array..." + NEWLINE +\
"find minIndex." + NEWLINE +\
"hanning...................." + NEWLINE +\
"FFT................................................................................................" + NEWLINE +\
"normalize....." + NEWLINE +\
"band average......................................................." + NEWLINE +\
"Auto-Spectrum Statistics:" + NEWLINE +\
"   nAvgBand = 5" + NEWLINE +\
"   total variance = 1.0896e-05" + NEWLINE +\
"   total energy = 1.0939e-01" + NEWLINE +\
"   significant period = 5.3782e-01" + NEWLINE +\
"   significant wave height = 1.3204e-02" + NEWLINE +\
"" + NEWLINE +\
"calculate dispersion.................................................................................................................................................................................................................................................................................." + NEWLINE +\
"IFFT................................................................................................" + NEWLINE +\
"deHanning...................." + NEWLINE +\
"move data.." + NEWLINE +\
"zero crossing analysis............." + NEWLINE +\
"Time Series Statistics:" + NEWLINE +\
"   wave integration time = 128" + NEWLINE +\
"   number of waves = 0" + NEWLINE +\
"   total variance = 1.1595e-05" + NEWLINE +\
"   total energy = 1.1640e-01" + NEWLINE +\
"   average wave height = 0.0000e+00" + NEWLINE +\
"   average wave period = 0.0000e+00" + NEWLINE +\
"   maximum wave height = 1.0893e-02" + NEWLINE +\
"   significant wave height = 0.0000e+00" + NEWLINE +\
"   significant wave period = 0.0000e+00" + NEWLINE +\
"   H1/10 = 0.0000e+00" + NEWLINE +\
"   H1/100 = 0.0000e+00" + NEWLINE

SAMPLE_DS =\
"SBE 26plus" + NEWLINE +\
"S>ds" + NEWLINE +\
"ds" + NEWLINE + SAMPLE_DEVICE_STATUS +\
"S>" + NEWLINE

SAMPLE_DC =\
"S>dc" + NEWLINE +\
"dc" + NEWLINE + SAMPLE_DEVICE_CALIBRATION +\
"S>"
