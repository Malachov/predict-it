#!/usr/bin/python

#%%
""" This is main module for making predictions.

It contain functions - predict() - More return types - Depends on config
                     - predict_multiple() - Predict multiple columns at once
                     - compare_models() - Test on data that was not in test set and compare models errors

    Examples:

        >>> import predictit
        >>> import numpy as np

        >>> predictions = predictit.main.predict(np.random.randn(1, 100), predicts=3, plotit=1)

Do not edit this file if you are user, it's not necassary! Only call function from here. The only file to edit is configuration.py. If you are developer, edit as you need.

There are working examples in main readme and also in test_it module. Particular modules functionality is vissible in visual.py in tests.
"""
import sys
from pathlib import Path, PurePath
import numpy as np
from tabulate import tabulate
import time
import pandas as pd
import argparse
import warnings
import inspect
import os
import multiprocessing

# Get module path and insert in sys path for working even if opened from other cwd (current working directory)
this_path = Path(os.path.abspath(inspect.getframeinfo(inspect.currentframe()).filename)).parents[1]
this_path_string = this_path.as_posix()

sys.path.insert(0, this_path_string)

import predictit
import predictit.configuration
from predictit.configuration import config
from predictit.misc import traceback_warning, user_message

config.this_path = this_path


if __name__ == "__main__":

    # All the config is in configuration.py" - rest only for people that know what are they doing
    # Add settings from command line if used
    parser = argparse.ArgumentParser(description='Prediction framework setting via command line parser!')
    parser.add_argument("--use_config_preset", type=str, choices=[None, 'fast'], help="Edit some selected config, other remains the same, check config_presets.py file.")
    parser.add_argument("--used_function", type=str, choices=['predict', 'predict_multiple_columns', 'compare_models', 'validate_predictions'],
                        help=("Which function in main.py use. Predict predict just one defined column, predict_multiple_columns predict more columns at once, "
                              "compare_models compare models on defined test data, validate_predictions test models on data not used for training"))
    parser.add_argument("--data", type=str, help="Path (local or web) to data. Supported formats - [.csv, .txt, .xlsx, .parquet]. Numpy Array and dataframe "
                                                 "allowed, but i don't know how to pass via CLI...")
    parser.add_argument("--predicts", type=int, help="Number of predicted values - 7 by default")
    parser.add_argument("--predicted_column", type=eval, help="""Name of predicted column or it's index - int "1" or string as "'Name'" """)
    parser.add_argument("--predicted_columns", type=list, help="For predict_multiple_columns function only! List of names of predicted column or it's indexes")
    parser.add_argument("--freq", type=str, help="Interval for predictions 'M' - months, 'D' - Days, 'H' - Hours")
    parser.add_argument("--freqs", type=list, help="For predict_multiple_columns function only! List of intervals of predictions 'M' - months, 'D' - Days, 'H' - Hours")
    parser.add_argument("--plotit", type=bool, help="If 1, plot interactive graph")
    parser.add_argument("--datetime_index", type=int, help="Index of dataframe or it's name. Can be empty, then index 0 or new if no date column.")
    parser.add_argument("--return_type", type=str, choices=['best', 'all_dataframe', 'detailed_dictionary', 'models_error_criterion', 'all_dataframe', 'detailed_dictionary'],
                        help=("'best' return array of predictions, 'all_dataframe' return dataframe of all models results. 'detailed_dictionary' is used for GUI and return"
                              "results as best result, all results, string div with plot and more. 'models_error_criterion' returns MAPE, RMSE (based on config) or dynamic "
                              "warping criterion of all models in array."))
    parser.add_argument("--datalength", type=int, help="The length of the data used for prediction")
    parser.add_argument("--debug", type=bool, help="Debug - print all results and all the errors on the way")
    parser.add_argument("--analyzeit", type=bool, help="Analyze input data - Statistical distribution, autocorrelation, seasonal decomposition etc.")
    parser.add_argument("--optimizeit", type=bool, help="Find optimal parameters of models")
    parser.add_argument("--repeatit", type=int, help="How many times is computation repeated")
    parser.add_argument("--other_columns", type=bool, help="If 0, only predicted column will be used for making predictions.")
    parser.add_argument("--default_other_columns_length", type=bool, help="Length of other columns in input vectors")
    parser.add_argument("--lengths", type=bool, help="Compute on various length of data (1, 1/2, 1/4...). Automatically choose the best length. If 0, use only full length.")
    parser.add_argument("--remove_outliers", type=bool, help=("Remove extraordinary values. Value is threshold for ignored values. Value means how many times standard "
                                                              "deviation from the average threshold is far"))
    parser.add_argument("--standardizeit", type=str, choices=[None, 'standardize', '-11', '01', 'robust'], help="Data standardization, so all columns have similiar scopes")
    parser.add_argument("--error_criterion", type=str, choices=['mape', 'rmse'], help="Error criterion used for model")
    parser.add_argument("--print_number_of_models", type=int, help="How many models will be displayed in final plot. 0 if only the best one.")

    # Non empty command line args
    parser_args_dict = {k: v for k, v in parser.parse_known_args()[0].__dict__.items() if v is not None}

    # Edit config default values with command line arguments values if exist
    config.update(parser_args_dict)


def predict(**function_kwargs):

    """Make predictions mostly on time-series data. Data input and other config options can be set up in configuration.py or overwritenn on the fly. Setup can be also done
    as function input arguments or as command line arguments (it will overwrite config values).

    For all posible arguments run `predictit.configuration.print_config()`

    There are working examples in main readme and also in test_it module.

    Args example:
        data (np.ndarray, pd.DataFrame): Time series. Can be 2-D - more columns.
            !!! In Numpy array use data series as rows, but in dataframe use cols !!!. If you use CSV, leave it empty. Defaults to [].
        predicted_column (int, str, optional): Index of predicted column or it's name (dataframe).
            If list with more values only the first one will be evaluated (use predict_multiple_columns function if you need that. Defaults to None.
        predicts (int, optional): Number of predicted values. Defaults to None.

        **kwargs (dict): There is much more parameters of predict function. Check configuration.py or run predictit.configuration.print_config() for parameters details.

    Returns:
        Depend on 'return_type' config value - return best prediction {np.ndarray}, all models results {np.ndarray}, detailed results{dict}
            or interactive plot or print tables of results

    """

    py_version = sys.version_info
    if py_version.major < 3 or py_version.minor < 6:
        raise RuntimeError(user_message("Python version >=3.6 necessary. Python 2 not supported."))

    # Some global config variables will be updated. But after finishing function, original global config have to be returned
    config_freezed = config.freeze()

    # Define whether to print warnings or not or stop on warnings as on error
    predictit.misc.set_warnings(config.debug, config.ignored_warnings)

    _GUI = predictit.misc._GUI

    # Add everything printed + warnings to variable to be able to print in GUI
    if _GUI or config.debug == -1:
        import io

        stdout = sys.stdout
        sys.stdout = io.StringIO()

    # Dont want to define in gui condition, so if not gui, do nothing
    if _GUI:
        def update_gui(content, id):
            try:
                predictit.gui_start.edit_gui_py(content, id)
            except Exception:
                pass
    else:
        def update_gui(content, id):
            pass

    if config.use_config_preset and config.use_config_preset != 'none':
        updated_config = config.presets[config.use_config_preset]
        config.update(updated_config)

    # Edit config.py default values with arguments values if exist
    config.update(function_kwargs)

    # Do not repeat actually mean evaluate once
    if not config.repeatit:
        config.repeatit = 1

    # Find difference between original config and set values and if there are any differences, raise error
    config_errors = set({key: value for key, value in config.__dict__.items() if not key.startswith('__') and not callable(key)}.keys()) - set(predictit.configuration.orig_config)
    if config_errors:
        raise KeyError(user_message(f"Some config values: {config_errors} was named incorrectly. Check config.py for more informations"))

    # Definition of the table for spent time on code parts
    time_parts_table = []

    def update_time_table(time_last):
        time_parts_table.append([progress_phase, round((time.time() - time_last), 3)])
        return time.time()
    time_point = time_begin = time.time()

    #######################################
    ############## LOAD DATA ####### ANCHOR Data
    #######################################

    progress_phase = "Data loading and preprocessing"
    update_gui(progress_phase, 'progress_phase')

    if isinstance(config.data, (str, PurePath)):
        config.data = predictit.data_preprocessing.load_data(config)

    #############################################
    ############ DATA consolidation ###### ANCHOR Data consolidation
    #############################################

    if config.data is None:
        raise TypeError(user_message("Data not loaded. Check config.py and use 'data_source' - csv and path or assign data to 'data'"))

    if not config.predicted_column:
        config.predicted_column = 0

    data_for_predictions_orig, data_for_predictions_df, predicted_column_name = predictit.data_preprocessing.data_consolidation(config.data, config)

    # In data consolidation predicted column was replaced on index 0 as first column
    predicted_column_index = 0

    if config.mode == 'validate':
        config.repeatit = 1
        data_for_predictions_orig, test = predictit.data_preprocessing.split(data_for_predictions_orig, predicts=config.predicts)
        data_for_predictions_df, _ = predictit.data_preprocessing.split(data_for_predictions_df, predicts=config.predicts)

    ########################################
    ############# Data analyze ###### Analyze original data
    ########################################

    multicolumn = 0 if data_for_predictions_orig.shape[1] == 1 else 1
    column_for_predictions_series = data_for_predictions_df.iloc[:, 0]
    models_number = len(config.used_models)
    used_models_assigned = {i: j for (i, j) in predictit.models.models_assignment.items() if i in config.used_models}

    results = []
    used_input_types = []

    for i in config.used_models:
        used_input_types.append(config.models_input[i])
    used_input_types = set(used_input_types)

    if config.analyzeit == 1 or config.analyzeit == 3:
        print("Analyze of unprocessed data")
        try:
            predictit.analyze.analyze_data(data_for_predictions_orig[:, 0].ravel(), column_for_predictions_series, window=30)
            predictit.analyze.analyze_correlation(data_for_predictions_df)
            predictit.analyze.decompose(data_for_predictions_orig[:, 0], **config.analyze_seasonal_decompose)
        except Exception:
            traceback_warning("Analyze failed")

    if config.multiprocessing == 'process':
        processes = []
        pipes = []
        # queues_dict = used_models_assigned.copy()
        # for i in queues_dict:
        #     queues_dict[i] = multiprocessing.Pipe()  # TODO duplex=False

    if config.multiprocessing == 'pool':
        pool = multiprocessing.Pool()

        # It is not possible easy share data in multiprocessing, so results are resulted via callback function
        def return_result(result):
            results.append(result)

    ### Optimization loop

    if config.optimization:
        option_optimization_list = config.optimization_values
    else:
        option_optimization_list = ['Not optimized']
        config.optimization_variable = None

    option_optimization_number = len(option_optimization_list)

    # Empty boxes for results definition
    # The final result is - [repeated, model, data, results]
    test_results_matrix = np.zeros((config.repeatit, models_number, option_optimization_number, config.predicts))
    evaluated_matrix = np.zeros((config.repeatit, models_number, option_optimization_number))
    reality_results_matrix = np.zeros((models_number, option_optimization_number, config.predicts))
    test_results_matrix.fill(np.nan)
    evaluated_matrix.fill(np.nan)
    reality_results_matrix.fill(np.nan)

    time_point = update_time_table(time_point)
    progress_phase = "Predict"
    update_gui(progress_phase, 'progress_phase')

    #######################################
    ############# Main loop ######## ANCHOR Main loop
    #######################################

    for optimization_index, optimization_value in enumerate(option_optimization_list):

        if config.optimization_variable:
            config.optimization_variable = optimization_value

        # Some config values are derived from other values. If it has been changed, it has to be updated.
        if not config.input_types:
            config.update_references_input_types()
        if config.optimizeit and not config.models_parameters_limits:
            config.update_references_optimize()


        #############################################
        ############ DATA preprocessing ###### ANCHOR Data preprocessing
        #############################################

        data_for_predictions = data_for_predictions_orig.copy()

        data_for_predictions, last_undiff_value, final_scaler = predictit.data_preprocessing.preprocess_data(
            data_for_predictions, multicolumn=multicolumn,
            remove_outliers=config.remove_outliers, smoothit=config.smoothit,
            correlation_threshold=config.correlation_threshold, data_transform=config.data_transform,
            standardizeit=config.standardizeit)

        column_for_predictions = data_for_predictions[:, predicted_column_index]

        data_shape = np.shape(data_for_predictions)
        data_length = len(column_for_predictions)

        data_std = np.std(column_for_predictions[-30:])
        data_mean = np.mean(column_for_predictions[-30:])
        data_abs_max = max(abs(column_for_predictions.min()), abs(column_for_predictions.max()))

        multicolumn = 0 if data_shape[1] == 1 else 1

        if (config.analyzeit == 2 or config.analyzeit == 3) and optimization_index == len(option_optimization_list) - 1:

            print("\n\n Analyze of preprocessed data \n")
            try:
                predictit.analyze.analyze_data(column_for_predictions, pd.Series(column_for_predictions), window=30)
            except Exception:
                traceback_warning("Analyze failed")

        min_data_length = 3 * config.predicts + config.default_n_steps_in

        if data_length < min_data_length:
            config.repeatit = 1
            min_data_length = 3 * config.predicts + config.repeatit * config.predicts + config.default_n_steps_in

        assert (min_data_length < data_length), user_message('Set up less predicted values in settings or add more data', caption="To few data")

        if config.mode == 'validate':
            models_test_outputs = [test]

        else:
            models_test_outputs = np.zeros((config.repeatit, config.predicts))

            if config.evaluate_type == 'original':
                for i in range(config.repeatit):
                    models_test_outputs[i] = data_for_predictions_orig[-config.predicts - i: - i, 0] if i > 0 else data_for_predictions_orig[-config.predicts - i:, 0]

            if config.evaluate_type == 'preprocessed':
                for i in range(config.repeatit):
                    models_test_outputs[i] = data_for_predictions[-config.predicts - i: - i, 0] if i > 0 else data_for_predictions[-config.predicts - i:, 0]

            models_test_outputs = models_test_outputs[::-1]

        for input_type in used_input_types:
            try:
                model_train_input, model_predict_input, model_test_inputs = predictit.define_inputs.create_inputs(input_type, data_for_predictions, config, predicted_column_index=predicted_column_index)
            except Exception:
                traceback_warning(f"Error in creating input type: {input_type} with option optimization: {optimization_value}")
                continue

            config_multiprocessed = config.freeze()
            del config_multiprocessed['data']

            for iterated_model_index, (iterated_model_name, iterated_model) in enumerate(used_models_assigned.items()):
                if config.models_input[iterated_model_name] == input_type:

                    predict_parameters = {
                        'config': config_multiprocessed, 'iterated_model_train': iterated_model.train, 'iterated_model_predict': iterated_model.predict, 'iterated_model_name': iterated_model_name,
                        'iterated_model_index': iterated_model_index, 'optimization_index': optimization_index, 'optimization_value': optimization_value,
                        'option_optimization_list': option_optimization_list, 'model_train_input': model_train_input, 'model_predict_input': model_predict_input,
                        'model_test_inputs': model_test_inputs, 'data_abs_max': data_abs_max, 'data_mean': data_mean, 'data_std': data_std,
                        'last_undiff_value': last_undiff_value, 'models_test_outputs': models_test_outputs, 'final_scaler': final_scaler
                    }

                    if config.models_input[iterated_model_name] in ['one_step', 'one_step_constant']:
                        if multicolumn and config.predicts > 1:

                            predictit.misc.user_warning(f"""Warning in model {iterated_model_name} \n\nOne-step prediction on multivariate data (more columns).
                                             Use batch (y lengt equals to predict) or do use some one column data input in config models_input or predict just one value.""")
                            continue

                    if config.multiprocessing == 'process':
                        pipes.append(multiprocessing.Pipe())
                        p = multiprocessing.Process(target=predictit.main_loop.train_and_predict, kwargs={**predict_parameters, **{'pipe': pipes[-1][1]}})

                        processes.append(p)
                        p.start()

                    elif config.multiprocessing == 'pool':

                        pool.apply_async(predictit.main_loop.train_and_predict, (), predict_parameters, callback=return_result)

                    else:
                        results.append(predictit.main_loop.train_and_predict(**predict_parameters))

    if config.multiprocessing:
        if config.multiprocessing == 'process':
            for i in pipes:
                try:
                    results.append(i[0].recv())
                except Exception:
                    pass

        if config.multiprocessing == 'pool':
            pool.close()
            pool.join()

    for i in results:
        try:
            if 'results' and 'evaluated_matrix' in i:
                reality_results_matrix[i['index'][0], i['index'][1], :] = i['results']
                evaluated_matrix[:, i['index'][0], i['index'][1]] = i['evaluated_matrix']
        except Exception:
            pass

    # TODO Do repeate average and more from evaluate in multiprocessing loop and then use sorting as
    # a = {k: v for k, v in sorted(x.items(), key=lambda item: item[1]['a'])} then use just slicing for plot and print results

    #############################################
    ############# Evaluate models ######## ANCHOR Evaluate
    #############################################

    # Criterion is the best of average from repetitions
    time_point = update_time_table(time_point)
    progress_phase = "Evaluation"
    update_gui(progress_phase, 'progress_phase')

    repeated_average = np.mean(evaluated_matrix, axis=0)

    model_results = []

    for i in repeated_average:
        model_results.append(np.nan if np.isnan(i).all() else np.nanmin(i))

    sorted_results = np.argsort(model_results)

    predicted_models_for_table = {}
    predicted_models_for_plot = {}

    for i, j in enumerate(sorted_results):
        this_model = list(used_models_assigned.keys())[j]

        if i == 0:
            best_model_name = this_model

        if config.print_number_of_models == -1 or i < config.print_number_of_models:
            predicted_models_for_table[this_model] = {
                'order': i + 1, 'error_criterion': model_results[j], 'predictions': reality_results_matrix[j, np.argmin(repeated_average[j])],
                'best_config_optimized_value': config.optimization_values[np.argmin(repeated_average[j])]}

        if config.plot_number_of_models == -1 or i < config.plot_number_of_models:
            predicted_models_for_plot[this_model] = {
                'order': i + 1, 'error_criterion': model_results[j], 'predictions': reality_results_matrix[j, np.argmin(repeated_average[j])],
                'best_config_optimized_value': config.optimization_values[np.argmin(repeated_average[j])]}

    best_model_predicts = predicted_models_for_table[best_model_name]['predictions'] if best_model_name in predicted_models_for_table else "Best model had an error"

    complete_dataframe = column_for_predictions_series[-config.plot_history_length:].to_frame()

    if config.confidence_interval:
        try:
            lower_bound, upper_bound = predictit.misc.confidence_interval(column_for_predictions_series.values, predicts=config.predicts, confidence=config.confidence_interval)
            complete_dataframe['Lower bound'] = complete_dataframe['Upper bound'] = None
            bounds = True
        except Exception:
            bounds = False
            traceback_warning("Error in compute confidence interval")

    else:
        bounds = False

    last_date = column_for_predictions_series.index[-1]

    if isinstance(last_date, (pd.core.indexes.datetimes.DatetimeIndex, pd._libs.tslibs.timestamps.Timestamp)):
        date_index = pd.date_range(start=last_date, periods=config.predicts + 1, freq=column_for_predictions_series.index.freq)[1:]
        date_index = pd.to_datetime(date_index)

    else:
        date_index = list(range(last_date + 1, last_date + config.predicts + 1))

    results_dataframe = pd.DataFrame(data={'Lower bound': lower_bound, 'Upper bound': upper_bound}, index=date_index) if bounds else pd.DataFrame(index=date_index)

    for i, j in predicted_models_for_plot.items():
        if 'predictions' in j:
            results_dataframe[f"{j['order']} - {i}"] = j['predictions']
            complete_dataframe[f"{j['order']} - {i}"] = None
            if j['order'] == 1:
                best_model_name_plot = f"{j['order']} - {i}"

    results_all_dataframe = pd.DataFrame(index=date_index)

    for res in results:
        if config.optimization:
            results_all_dataframe[f"{res['name']} - {res['optimization_value']}"] = res.get('results')
        else:
            results_all_dataframe[f"{res['name']}"] = res.get('results')

    if config.mode == 'validate':
        best_model_name_plot = 'Test'
        results_dataframe['Test'] = test

    last_value = float(column_for_predictions_series.iloc[-1])

    complete_dataframe = pd.concat([complete_dataframe, results_dataframe], sort=False)
    complete_dataframe.iloc[-config.predicts - 1] = last_value

    #######################################
    ############# Plot ############# ANCHOR Plot
    #######################################

    time_point = update_time_table(time_point)
    progress_phase = "plot"
    update_gui(progress_phase, 'progress_phase')

    if config.plotit:

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)

            plot_return = 'div' if _GUI else ''
            div = predictit.plots.plot(
                complete_dataframe, plot_type=config.plot_type, show=config.show_plot, save=config.save_plot,
                save_path=config.save_plot_path, plot_return=plot_return, best_model_name=best_model_name_plot,
                predicted_column_name=predicted_column_name)

            if config.plot_all_optimized_models:
                predictit.plots.plot(
                    results_all_dataframe, plot_type=config.plot_type, show=config.show_plot, save=config.save_plot,
                    save_path=config.save_plot_path, best_model_name=best_model_name_plot)

    time_point = update_time_table(time_point)
    progress_phase = "Completed"
    update_gui(progress_phase, 'progress_phase')


    ####################################
    ############# Results ####### ANCHOR Results
    ####################################

    # Table of results
    models_table = []
    # Fill the table
    for i, j in predicted_models_for_table.items():
        models_table.append([i, round(j['error_criterion'], 3)])

    models_table = pd.DataFrame(models_table, columns=['Model', f"Average {config.error_criterion} error"])

    time_parts_table.append(['Complete time', round((time.time() - time_begin), 3)])

    detailed_table = []
    for i in results:
        try:
            detailed_table.append([i['name'], round(i['model_error'], 3), round(i['model_time'], 3), i['optimization_value']])
        except Exception:
            detailed_table.append([i['name'], np.inf, np.nan, 'Model crashed'])

    if config.optimizeit:
        try:
            detailed_table.append('Optimization time', [i.get('optimization_time') for i in results])
        except Exception:
            pass

    time_parts_table = pd.DataFrame(time_parts_table, columns=["Part", "Time"])
    detailed_table = pd.DataFrame(detailed_table, columns=['Name', f"Average {config.error_criterion} error", 'Time', 'Config optimization'])

    if config.sort_detailed_results_by == 'name':
        detailed_table.sort_values('Name', inplace=True)

    elif config.sort_detailed_results_by == 'error':
        detailed_table.sort_values(f"Average {config.error_criterion} error", inplace=True)

    if config.printit:
        if config.print_result:
            print((f"\n Best model is {best_model_name} \n\t with results {best_model_predicts} \n\t with model error {config.error_criterion} = "
                   f"{predicted_models_for_table[best_model_name]['error_criterion']}"))

        if config.print_table == 1:
            print(f'\n {tabulate(models_table.values, headers=models_table.columns, tablefmt="pretty")} \n')

        ### Print detailed resuts ###
        if config.print_table == 2:
            print(f'\n {tabulate(detailed_table.values, headers=detailed_table.columns, tablefmt="pretty")} \n')

        if config.print_time_table:
            print(f'\n {tabulate(time_parts_table.values, headers=time_parts_table.columns, tablefmt="pretty")} \n')

    # Return stdout and stop collect warnings and printed output
    if _GUI:
        output = sys.stdout.getvalue()
        sys.stdout = stdout

        print(output)

    return_type = config.return_type

    # Return original config values before predict function
    config.update(config_freezed)

    ################################
    ########### Return ###### ANCHOR Return
    ################################

    if not return_type or return_type == 'best':
        return best_model_predicts

    elif return_type == 'all_dataframe':
        return results_dataframe

    elif return_type == 'detailed_dictionary':
        detailed_dictionary = {
            'predicted_models': predicted_models_for_table,
            'best': best_model_predicts,
            'all_dataframe': results_dataframe,
            'complete_dataframe': complete_dataframe
        }

        if _GUI:
            detailed_dictionary.update({
                'plot': div,
                'output': output,

                'time_table': str(tabulate(time_parts_table.values, headers=time_parts_table.columns, tablefmt="html")),
                'models_table': str(tabulate(models_table.values, headers=models_table.columns, tablefmt="html")),
            })

        else:
            detailed_dictionary.update({
                'time_table': time_parts_table,
                'models_table': models_table,
            })

        return detailed_dictionary

    elif return_type == 'models_error_criterion':
        return repeated_average

    elif return_type == 'visual_check':
        return {'data_for_predictions (X, y)': data_for_predictions, 'model_train_input': model_train_input,
                'model_predict_input': model_predict_input, 'model_test_inputs': model_test_inputs, 'models_test_outputs': models_test_outputs}


def predict_multiple_columns(**function_kwargs):
    """Predict multiple colums and multiple frequencions at once. Use predict function.

    Args:
        data (np.ndarray, pd.DataFrame): Time series. Can be 2-D - more columns.
            !!! In Numpy array use data series as rows, but in dataframe use cols !!!. Defaults to [].
        predicted_columns (list, optional): List of indexes of predicted columns or it's names (dataframe). Defaults to None.
        freqs (str. 'H' or 'D' or 'M', optional): If date index available, resample data and predict in defined time frequency. Defaults to [].
        database_deploy (bool, optional): Whether deploy results to database !!!
            For every database it's necessary to adjust the database function. Defaults to 0.

    Returns:
        np.ndarray: All the predicted results.
    """

    config_freezed = config.freeze()

    config.update(function_kwargs)

    freqs = config.freqs if config.freqs else [None]
    predicted_columns = config.predicted_columns if config.predicted_columns else [None]

    if config.data is None or isinstance(config.data, (str, PurePath)):
        config.data = predictit.data_preprocessing.load_data(config)

    if predicted_columns in ['*', ['*']]:
        if isinstance(config.data, pd.DataFrame):
            predicted_columns = list(config.data.select_dtypes(['number']).columns)
        if isinstance(config.data, np.ndarray):
            predicted_columns = list(range(config.data.shape[1]))

    predictions = {}

    for fi, f in enumerate(freqs):

        for ci, c in enumerate(predicted_columns):

            try:
                predictions[f"Column: {c} - Freq: {f}"] = predict(predicted_column=c, freq=f)

            except Exception:
                traceback_warning(f"Error in making predictions on column {c} and freq {f}")


        # if config.database_deploy:
        #     try:
        #         predictit.database.database_deploy(config.server, config.database, last_date, predictions[0], predictions[1], freq=f)
        #     except Exception:
        #         traceback_warning(f"Error in database deploying on freq {f}")

    # Return original config values before predict function
    config.update(config_freezed)

    return predictions


def compare_models(**function_kwargs):
    """Function that helps to choose apropriate models. It evaluate it on test data and then return results.
    After you know what models are the best, you can use only them in functions predict() or predict_multiple_columns.
    You can define your own test data and find best modules for your process.

    Args:
        data_all (dict): Dictionary of data names and data values (np.array). You can use data from test_data module, generate_test_data script (e.g. gen_sin()).
        **kwargs (dict): All parameters of predict function. Check config.py for parameters details.
    """

    config_freezed = config.freeze()

    # Edit config.py default values with arguments values if exist
    config.update(function_kwargs)

    # Edit config.py default values with arguments values if exist
    config.update({'return_type': 'models_error_criterion', 'mode': 'validate', 'confidence_interval': 0, 'optimizeit': 0})

    # If no data_all inserted, default will be used
    if not config.data_all:
        config.data_all = {'sin': (predictit.test_data.generate_test_data.gen_sin(), 0),
                           'Sign': (predictit.test_data.generate_test_data.gen_sign(), 0),
                           'Random data': (predictit.test_data.generate_test_data.gen_random(), 0)}
        predictit.misc.user_warning("Test data was used. Setup 'data_all' in config...")

    results = {}
    unstardized_results = {}

    data_dict = config.data_all
    same_data = False

    if isinstance(data_dict, (list, tuple, np.ndarray)):
        same_data = True
        data_dict = {f"Data {i}": (j, config.predicted_column) for i, j in enumerate(data_dict)}

    for i, j in data_dict.items():

        config.data = j[0]
        if not same_data:
            config.predicted_column = j[1]

        try:
            result = predict()
            results[i] = (result - np.nanmin(result)) / (np.nanmax(result) - np.nanmin(result))
            unstardized_results[i] = result

        except Exception:
            traceback_warning(f"Comparison for data {i} didn't finished.")
            results[i] = np.nan

    results_array = np.stack(list(results.values()), axis=0)
    unstardized_results_array = np.stack(list(unstardized_results.values()), axis=0)

    # results_array[np.isnan(results_array)] = np.inf

    all_data_average = np.nanmean(results_array, axis=0)
    unstardized_all_data_average = np.nanmean(unstardized_results_array, axis=0)

    models_best_results = []
    unstardized_models_best_results = []

    for i in all_data_average:
        models_best_results.append(np.nan if np.isnan(i).all() else np.nanmin(i))
    models_best_results = np.array(models_best_results)

    for i in unstardized_all_data_average:
        unstardized_models_best_results.append(np.nan if np.isnan(i).all() else np.nanmin(i))
    unstardized_models_best_results = np.array(unstardized_models_best_results)

    best_compared_model = int(np.nanargmin(models_best_results))
    best_compared_model_name = list(config.used_models)[best_compared_model]

    print("\n\nTable of complete results. Percentual standardized error is between 0 and 1. If 0, model was the best on all defined data, 1 means it was the worst.")
    models_table = []

    # Fill the table
    for i, j in enumerate(config.used_models):
        models_table.append([j, models_best_results[i], unstardized_models_best_results[i]])

    models_table = pd.DataFrame(models_table, columns=['Model', 'Percentual standardized error', 'Error average'])

    print(f'\n {tabulate(models_table.values, headers=models_table.columns, tablefmt="pretty")} \n')

    print(f"\n\nBest model is {best_compared_model_name}")

    compared_result = {'Models table': models_table, 'Best model': best_compared_model_name}

    # If config value optimization
    if all_data_average.shape[1] == 1:
        print("No config variable optimization was applied")
        compared_result['Best optimized value'] = 'Not optimized'
    else:
        all_lengths_average = np.nanmean(all_data_average, axis=0)
        best_all_lengths_index = np.nanargmin(all_lengths_average)
        print(f"\n\nBest optimized value is {best_all_lengths_index}")
        compared_result['Best optimized value'] = best_all_lengths_index

    # Return original config values before predict function
    config.update(config_freezed)

    return compared_result


if __name__ == "__main__" and config.used_function:
    if config.used_function == 'predict':
        prediction_results = predict()

    elif config.used_function == 'predict_multiple':
        prediction_results = predict_multiple_columns()

    elif config.used_function == 'compare_models':
        compare_models()

# %%
