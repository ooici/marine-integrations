from mi.instrument.seabird.sbe54tps.ooicore.driver import Parameter

PARAMS = {
    #
    # Common fields in all commands
    #

    Parameter.DEVICE_TYPE : str,
    Parameter.SERIAL_NUMBER : str,

    #
    # StatusData
    #

    Parameter.TIME : str,
    Parameter.EVENT_COUNT : int,
    Parameter.MAIN_SUPPLY_VOLTAGE : float,
    Parameter.NUMBER_OF_SAMPLES : int,
    Parameter.BYTES_USED : int,
    Parameter.BYTES_FREE : int,

    #
    # ConfigurationData
    #

    Parameter.ACQ_OSC_CAL_DATE : float,
    Parameter.FRA0 : float,
    Parameter.FRA1 : float,
    Parameter.FRA2 : float,
    Parameter.FRA3 : float,
    Parameter.PRESSURE_SERIAL_NUM : str,
    Parameter.PRESSURE_CAL_DATE : float,
    Parameter.PU0 : float,
    Parameter.PY1 : float,
    Parameter.PY2 : float,
    Parameter.PY3 : float,
    Parameter.PC1 : float,
    Parameter.PC2 : float,
    Parameter.PC3 : float,
    Parameter.PD1 : float,
    Parameter.PD2 : float,
    Parameter.PT1 : float,
    Parameter.PT2 : float,
    Parameter.PT3 : float,
    Parameter.PT4 : float,
    Parameter.PRESSURE_OFFSET : float,
    Parameter.PRESSURE_RANGE : float,
    Parameter.BATTERY_TYPE : int,
    Parameter.BAUD_RATE : int,
    Parameter.ENABLE_ALERTS : bool,
    Parameter.UPLOAD_TYPE : int,
    Parameter.SAMPLE_PERIOD : int,

    #
    # Event Counter
    #

    Parameter.NUMBER_EVENTS : int,
    Parameter.MAX_STACK : int,
    Parameter.POWER_ON_RESET : int,
    Parameter.POWER_FAIL_RESET : int,
    Parameter.SERIAL_BYTE_ERROR : int,
    Parameter.COMMAND_BUFFER_OVERFLOW : int,
    Parameter.SERIAL_RECEIVE_OVERFLOW : int,
    Parameter.LOW_BATTERY : int,
    Parameter.SIGNAL_ERROR : int,
    Parameter.ERROR_10 : int,
    Parameter.ERROR_12 : int,

    #
    # Hardware Data
    #

    Parameter.MANUFACTURER : str,
    Parameter.FIRMWARE_VERSION : str,
    Parameter.FIRMWARE_DATE : float,
    Parameter.HARDWARE_VERSION : str,
    Parameter.PCB_SERIAL_NUMBER : str,
    Parameter.PCB_TYPE : str,
    Parameter.MANUFACTUR_DATE : float,
}
