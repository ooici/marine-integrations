#from mi.instrument.wetlabs.fluorometer.flort-d.driver import Parameter

PARAMS = {
    #
    # ConfigurationData
    #

    Parameter.Analog_scaling_value : int,
    Parameter.Measurements_per_reported_value : int,
    Parameter.Measurement_1_dark_count : int,
    Parameter.Measurement_1_slope_value : float,
    Parameter.Measurement_2_dark_count : int,
    Parameter.Measurement_2_slope_value : float,
    Parameter.Measurement_3_dark_count : int,
    Parameter.Measurement_3_slope_value : float,
    Parameter.Measurements_per_packet : int,
    Parameter.Baud_rate : int,
    Parameter.Packets_per_set : int,
    Parameter.Predefined_output_sequence : int,
    Parameter.Recording_mode : bool,
    Parameter.Manual_mode : bool,
    Parameter.Sampling_interval : str,
    Parameter.Date : str,
    Parameter.Time : str,
    Parameter.Manual_start_time : str,

    #
    # Hardware Data
    #

    Parameter.Serial_number : str,
    Parameter.Firmware_version : str,
    Parameter.Internal_memory : int
}
