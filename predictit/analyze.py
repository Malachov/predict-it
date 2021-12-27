"""This is module for data analysis. It create plots of data, it's distribution,
it's details, autocorrelation function etc.
"""

from __future__ import annotations
from typing import NamedTuple, Any
from typing_extensions import Literal

import numpy as np
import pandas as pd

import mylogging

from . import misc
from .models import models_keys

# Lazy imports

# import mydatapreprocessing

# import matplotlib.pyplot as plt
# import seaborn as sns
# from statsmodels.graphics.tsaplots import plot_acf
# from statsmodels.graphics.tsaplots import plot_pacf
# from statsmodels.tsa.stattools import adfuller
# from pandas.plotting import register_matplotlib_converters
# from statsmodels.tsa.seasonal import seasonal_decompose


def analyze_column(data: np.ndarray | pd.DataFrame, lags: int = 5, window: int = 5) -> None:
    """Function one-dimensional data (predicted column), that plot data, it's distribution, some details like minimum,
    maximum, std, mean etc. It also create autocorrelation and partial autocorrelation (good for ARIMA models) and
    plot rolling mean and rolling std. It also tell if data are probably stationary or not.

    Args:
        data (np.ndarray | pd.DataFrame): Time series data.
        lags (int, optional): Lags used for autocorrelation. Defaults to 5.
        window (int, optional): Window for rolling average and rolling std. Defaults to 5.

    """
    if not misc.GLOBAL_VARS.PLOTS_CONFIGURED:
        misc.setup_plots()

    import matplotlib.pyplot as plt
    import seaborn as sns
    from statsmodels.graphics.tsaplots import plot_acf
    from statsmodels.graphics.tsaplots import plot_pacf
    from statsmodels.tsa.stattools import adfuller

    import mydatapreprocessing

    data = np.array(data)

    if data.ndim != 1 and 1 not in data.shape:
        raise ValueError(
            mylogging.return_str(
                "Select column you want to analyze",
                caption="analyze_data function only for one-dimensional data!",
            )
        )

    data = data.ravel()

    print(
        f"Length: {len(data)}\n"
        f"Minimum: {np.nanmin(data)}\n"
        f"Maximum: {np.nanmax(data)}\n"
        f"Mean: {np.nanmean(data)}\n"
        f"Std: {np.nanstd(data)}\n"
        f"First few values: {data[-5:]}\n"
        f"Middle values: {data[int(-len(data)/2): int(-len(data)/2) + 5]}\n"
        f"Last few values: {data[-5:]}\n"
        f"Number of nan (not a number) values: {np.count_nonzero(np.isnan(data))}\n"
    )

    # Data and it's distribution

    plt.figure(figsize=(10, 5))
    plt.subplot(1, 2, 1)
    plt.plot(data)
    plt.xlabel("t")
    plt.ylabel("f(x)")

    plt.subplot(1, 2, 2)
    sns.histplot(data, bins=100, kde=True, color="skyblue")
    plt.xlabel("f(x)")
    plt.ylabel("Distribution")

    plt.tight_layout()
    plt.suptitle("Data and it's distribution", fontsize=20)
    plt.subplots_adjust(top=0.88)
    plt.draw()

    fig, (ax, ax2) = plt.subplots(ncols=2, figsize=(10, 5))
    fig.suptitle("Repeating patterns - autocorrelation")

    try:

        plot_acf(data, lags=lags, ax=ax)
        ax.set_xlabel("Lag")
        plot_pacf(data, lags=lags, ax=ax2)
        ax2.set_xlabel("Lag")
        plt.draw()

    except Exception:
        mylogging.traceback(
            "Error in analyze_column function - in autocorrelation function: Maybe more lags, than values"
        )

    # Moving average
    rolling_mean = np.sum(mydatapreprocessing.misc.rolling_windows(data, window), 1)
    rolling_std = np.std(mydatapreprocessing.misc.rolling_windows(data, window), 1)

    plt.figure(figsize=(10, 5))
    plt.subplot(1, 2, 1)
    plt.plot(rolling_mean)
    plt.xlabel("t")
    plt.ylabel("Rolling average x")

    plt.subplot(1, 2, 2)
    plt.plot(rolling_std)
    plt.xlabel("f(x)")
    plt.ylabel("Rolling standard deviation x")

    plt.tight_layout()
    plt.suptitle("Rolling average and rolling standard deviation", fontsize=20)
    plt.subplots_adjust(top=0.88)
    plt.draw()

    # Dick Fuller test for stationarity
    pvalue = adfuller(data)[1]
    cutoff = 0.05
    if pvalue < cutoff:
        print(f"\np-value = {pvalue} : Analyzed column is probably stationary.\n")
    else:
        print(f"\np-value = {pvalue} : Analyzed column is probably not stationary.\n")


def analyze_data(data: pd.DataFrame | np.ndarray, pairplot: bool = False):
    """Analyze n-dimensional data. Describe data types, nan values, minimums etc...
    Plot correlation graph.

    Args:
        data (pd.DataFrame | np.ndarray): Time series data.
        pairplot (bool, optional): Whether to plot correlation matrix. Computation can be very slow. Defaults to False.
    """
    if not misc.GLOBAL_VARS.PLOTS_CONFIGURED:
        misc.setup_plots()

    import matplotlib.pyplot as plt
    import seaborn as sns

    data = pd.DataFrame(data)

    print("\n Data description \n", data.describe(include="all"))
    print("\n Data tail \n", data.tail())
    print("\n Nan values in columns \n\n", str(data.isna().sum()))

    # Pairplot unfortunately very slow
    if pairplot:
        sns.pairplot(data, diag_kind="kde")
    else:
        plt.figure(figsize=(6, 5))
        plt.subplot(1, 1, 1)
        corr = data.corr()

        ax = sns.heatmap(
            corr,
            vmin=-1,
            vmax=1,
            center=0,
            cmap=sns.diverging_palette(20, 220, n=200),
            square=True,
        )
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, horizontalalignment="right")

        plt.draw()


def decompose(data: np.ndarray, period: int = 365, model: Literal["additive", "multiplicative"] = "additive"):
    """Plot decomposition graph. Analyze if data are seasonal.

    Args:
        data (np.ndarray): Time series data
        period (int, optional): Seasonal interval. Defaults to 365.
        model (Literal["additive", "multiplicative"], optional): 'additive' or 'multiplicative'. Defaults to 'additive'.
    """
    if not misc.GLOBAL_VARS.PLOTS_CONFIGURED:
        misc.setup_plots()

    import matplotlib.pyplot as plt
    from statsmodels.tsa.seasonal import seasonal_decompose

    try:
        decomposition = seasonal_decompose(data, model=model, period=period)

        plt.figure(figsize=(15, 8))
        plt.subplot(4, 1, 1)
        plt.plot(decomposition.observed)
        plt.xlabel("Date")
        plt.ylabel("Real values")

        plt.subplot(4, 1, 2)
        plt.plot(decomposition.trend)
        plt.xlabel("Date")
        plt.ylabel("Trend")

        plt.subplot(4, 1, 3)
        plt.plot(decomposition.seasonal)
        plt.xlabel("Date")
        plt.ylabel("Seasonality")

        plt.subplot(4, 1, 4)
        plt.plot(decomposition.resid)
        plt.xlabel("Date")
        plt.ylabel("Residuals")

        plt.suptitle("Seasonal decomposition", fontsize=20)
        plt.subplots_adjust(top=0.88)

        plt.draw()

    except ValueError:
        mylogging.traceback("Number of samples is probably too low to compute.")


class _analyze_results_result(NamedTuple):
    """Models with best optimized average results, best optimized form models,
    best model name and best optimized for all models together.

    Attributes:
        best_results_errors(np.ndarray): Results if using just best optimized values.
        best_models_optimized_values_dict (dict): List of best optimized value for each model.
        optimized_values_results_df (pd.DataFrame): Average results based on optimization variable.
        best_model_name (str): Best model when used best optimized value.
        best_optimized_value: (Any): Optimazed value of used config parameter that has lowest
            total error in all models together."""

    best_results_errors: np.ndarray
    best_models_optimized_values_dict: dict[models_keys, Any]
    optimized_values_results_df: pd.DataFrame
    best_model_name: str
    best_optimized_value: Any


def analyze_results(
    results: np.ndarray,
    config_values_columns: list[str],
    models_columns: list[str] | tuple[str, ...] | set[str],
    error_criterion: str = "",
) -> _analyze_results_result:
    """Multiple predictions for various optimized config variable values are made, then errors (difference from true
    values) are evaluated. Outputs are averaged errors through datasets, what model is the best,
    what are the best optimized values for particular model, or what is best optimized value for all models.

    Args:
        results (np.ndarray): Results in shape (dataset, optimized, models). First index is just averaged.
            optimized and models are analyzed.
        config_values_columns (list[str]): List of model names and its best configured values (dim 2).
        models_columns (list): Names of used models.
        error_criterion(string, optional): If config values evaluated.
            Used as column name. Defaults to ""

    Returns:
        analyze_results_result: Result of analysis.

    Example:
        >>> arr = np.array(range(27)).reshape(3, 3, 3)
        ...
        >>> arr
        array([[[ 0,  1,  2],
                [ 3,  4,  5],
                [ 6,  7,  8]],
        <BLANKLINE>
               [[ 9, 10, 11],
                [12, 13, 14],
                [15, 16, 17]],
        <BLANKLINE>
               [[18, 19, 20],
                [21, 22, 23],
                [24, 25, 26]]])
        >>> analysis = analyze_results(
        ...     arr,
        ...     config_values_columns=["Config 1", "Config 2", "Config 3"],
        ...     models_columns=["Model 1", "Model 2", "Model 3"],
        ... )

        One dimension is reduced just by averaging, because average performance across datasets is evaluated.
        Than for optimized value, just the best value is used.

        >>> analysis.best_results_errors
        array([ 9., 10., 11.])
        >>> analysis.best_models_optimized_values_dict
        {'Model 1': 'Config 1', 'Model 2': 'Config 1', 'Model 3': 'Config 1'}
        >>> analysis.optimized_values_results_df
                   error
        Config 1   10.0
        Config 2   13.0
        Config 3   16.0
        >>> analysis.best_model_name
        'Model 1'
        >>> analysis.best_optimized_value
        'Config 1'
    """
    # Analyze models - choose just the best optimized value
    best_results_errors = np.nanmin(results, axis=0)  # Results if only best optimized are used
    best_optimized_indexes_errors = np.nanargmin(results, axis=0)  # Indexes of best optimized

    best_models_optimized_values_dict = {
        model: config_values_columns[best_index]
        for model, best_index in zip(models_columns, best_optimized_indexes_errors)
    }

    # Find best models if using just best optimized values

    best_model_index = int(np.nanargmin(best_results_errors))
    best_model_name = list(models_columns)[best_model_index]

    # Analyze optimized variables - keep all results for defined optimized values
    if results.shape[0] == 1:
        best_optimized_value = "Not optimized"
        optimized_values_results_df = pd.DataFrame()
    else:
        all_models_errors_average = np.nanmean(results, axis=1)
        best_optimized_index = np.nanargmin(all_models_errors_average)
        best_optimized_value = config_values_columns[best_optimized_index]

        optimized_values_results_df = pd.DataFrame(
            all_models_errors_average,
            columns=[error_criterion + "error"],
            index=config_values_columns,
        )

    return _analyze_results_result(
        best_results_errors,
        best_models_optimized_values_dict,
        optimized_values_results_df,
        best_model_name,
        best_optimized_value,
    )
