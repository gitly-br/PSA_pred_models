def generate_slices(time_interval, start, end):
    """
    Generate time-based slices within a specified interval.

    Parameters:
    ----------
    time_interval : int
        The interval size to divide the range.
    start : int
        The starting point of the range.
    end : int
        The endpoint of the range.

    Returns:
    -------
    dict
        A dictionary where keys are interval names (e.g., "0_24") and values are
        slice objects for each interval.
    """
    slices = {}
    for i in range(start, end, time_interval):
        slices[f"{i}_{i+time_interval}"] = slice(i, i+time_interval)
    return slices

def generate_default_config_dict(df):
    """
    Generate a default configuration dictionary for aggregation of each column
    in a dataframe.

    Parameters:
    ----------
    df : pd.DataFrame
        The DataFrame for which the configuration dictionary is generated.

    Returns:
    -------
    dict
        A dictionary with column names as keys and default configuration tuples
        as values (interval size and aggregation functions).
    """
    config_dict = {}
    for col in df.columns:
        config_dict[col] = (24, ("mean",))
    return config_dict

def create_agg_dict(config_dict, start=0, end=24):
    """
    Create an aggregation dictionary based on a configuration dictionary.

    This dictionary can then be used as input to the df.agg method.

    Usage example:

    df_agg = df.groupby(pd.Grouper(key='dt', freq='D')).agg(
                                                  **create_agg_dict(agg_config)
                                                  ).reset_index()

    Parameters:
    ----------
    config_dict : dict
        A dictionary where keys are column names and values are tuples
        containing the interval size and list of aggregation functions.
    start : int, optional
        The starting point of the time range (default is 0).
    end : int, optional
        The endpoint of the time range (default is 24).

    Returns:
    -------
    dict
        An aggregation dictionary where keys are descriptive names for each aggregation,
        and values are tuples of (column name, aggregation lambda).
    """
    agg_dict = {}
    for col, config in config_dict.items():
        time_interval, agg_list = config
        for interval_name, interval_slice in generate_slices(time_interval, start, end).items():
            if "mean" in agg_list:
                agg_dict[f"{col}_{interval_name}_mean"] = (col, lambda x, s=interval_slice: x[s].mean())
            if "median" in agg_list:
                agg_dict[f"{col}_{interval_name}_median"] = (col, lambda x, s=interval_slice: x[s].median())
            if "sum" in agg_list:
                agg_dict[f"{col}_{interval_name}_sum"] = (col, lambda x, s=interval_slice: x[s].sum())
            if "max" in agg_list:
                agg_dict[f"{col}_{interval_name}_max"] = (col, lambda x, s=interval_slice: x[s].max())
            if "min" in agg_list:
                agg_dict[f"{col}_{interval_name}_min"] = (col, lambda x, s=interval_slice: x[s].min())
            if "delta" in agg_list:
                agg_dict[f"{col}_{interval_name}_delta"] = (col, lambda x, s=interval_slice: x[s].max() - x[s].min())
            if "mode" in agg_list:
                agg_dict[f"{col}_{interval_name}_mode"] = (col, lambda x, s=interval_slice: x[s].mode())
            if "random_sample" in agg_list:
                agg_dict[f"{col}_{interval_name}_random_sample"] = (col, lambda x, s=interval_slice: x[s].sample(1))
    return agg_dict