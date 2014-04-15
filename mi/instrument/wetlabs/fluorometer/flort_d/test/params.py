from mi.instrument.wetlabs.fluorometer.flort_d.driver import Parameter

PARAMS = {
    #
    # ConfigurationData
    #

    Parameter.Analog_scaling_value : int,
    Parameter.Measurements_per_reported_value : int,
    Parameter.Measurement_1_dark_count_value : int,
    Parameter.Measurement_1_slope_value : float,
    Parameter.Measurement_2_dark_count_value : int,
    Parameter.Measurement_2_slope_value : float,
    Parameter.Measurement_3_dark_count_value : int,
    Parameter.Measurement_3_slope_value : float,
    Parameter.Measurements_per_packet_value : int,
    Parameter.Baud_rate_value : int,
    Parameter.Packets_per_set_value : int,
    Parameter.Predefined_output_sequence_value : int,
    Parameter.Recording_mode_value : bool,
    Parameter.Manual_mode_value : bool,
    Parameter.Sampling_interval_value : str,
    Parameter.Date_value : str,
    Parameter.Time_value : str,
    Parameter.Manual_start_time_value : str,

    #
    # Hardware Data
    #

    Parameter.Serial_number_value : str,
    Parameter.Firmware_version_value : str,
    Parameter.Internal_memory_value : int
}
