import os
import ast
import csv
import glob
import json
import pickle
import shutil
import uuid

import chardet
# import logging
import mimetypes
from .utils import *
import pandas as pd
import numpy as np
import seaborn as sns
from app.models import *
from sklearn import metrics
from json import JSONEncoder
import category_encoders as ce
import matplotlib.pyplot as plt
from django.conf import settings
from django.contrib import messages
from django.utils.text import get_valid_filename
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from django.core.files.storage import FileSystemStorage
from django.contrib.auth import authenticate, login, logout, decorators
from pandas.api.types import is_numeric_dtype, is_float_dtype, is_string_dtype
from django.shortcuts import render, HttpResponse, redirect, get_object_or_404

# logger = logging.getLogger(__name__)

# all_ml_models = ['Logistic Regression', 'Decision Tree Classifier', 'KNeighbors Classifier', 'Random Forest Classifier', 'GaussianNB Classifier', 'SGD Classifier', 'Linear Regression']
# automl_model_type = ['(AutoML) Regression', '(AutoML) Classification']
# numerical_model_name_list = ['Linear Regression']
media_path = settings.MEDIA_ROOT

plt.switch_backend('agg')


class NumpyArrayEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return JSONEncoder.default(self, obj)


def check_dir_exists(path):
    """
    :param path: /path/to/dir
    :return: if dir not present, it creates a dir
    """
    if not os.path.isdir(path):
        os.mkdir(path)


def home(request):
    return render(request, 'home.html')


def continue_as_guest(request):
    request.session['guest_session_id'] = str(uuid.uuid4())
    return redirect('/upload/')


def sign_up(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        # ============== VALIDATIONS ============== #

        # USERNAME
        if User.objects.filter(username=username).exists():
            messages.warning(request, 'Username already present, please choose different username')
            return redirect('/signup/')

        if len(username) > 10:
            messages.warning(request, "Username must be below 10 characters")
            return redirect('/signup/')

        if not username.isalnum():
            messages.warning(request, "Username must be Alphanumeric only")
            return redirect('/signup/')

        if User.objects.filter(email=email).exists():
            messages.warning(request, "Email already present")
            return redirect('/signup/')

        user = User.objects.create_user(username, email, password)
        user.save()

        custom_user = Profile(user=user)
        custom_user.save()
        user = authenticate(username=username, password=password)
        login(request, user)
        messages.success(request, 'Account created, Successfully Logged in')
        return redirect('/upload/')

    return render(request, 'signup.html')


def login_page(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Successfully Logged in')
            return redirect('/upload/')
        else:
            messages.error(request, 'Invalid Credentials')
            return redirect('/signin/')
    return render(request, 'login.html')


def logout_page(request):
    logout(request)
    messages.success(request, "Successfully logged out")
    return redirect('/signin/')


def download_file(request, filename):
    # Define Django project base directory
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # path = os.path.join(media_path, 'sample_csv', list(request.POST.keys())[-1])
    # Define text file name
    # filename = 'test.txt'
    # Define the full file path
    filepath = BASE_DIR + '/downloadapp/Files/' + filename
    # Open the file for reading content
    path = open(filepath, 'r')
    # Set the mime type
    mime_type, _ = mimetypes.guess_type(filepath)
    # Set the return value of the HttpResponse
    response = HttpResponse(path, content_type=mime_type)
    # Set the HTTP header for sending to browser
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    # Return the response value
    return response


# @decorators.login_required
def upload(request):
    if 'guest_session_id' not in request.session and not request.user.is_authenticated:
        return redirect('/signin/')

    elif request.method == 'POST':
        user = request.session['guest_session_id'] if request.session['guest_session_id'] else str(request.user.id)
        check_dir_exists(media_path + os.sep + user)
        check_dir_exists(media_path + os.sep + user + os.sep + 'documents')
        check_dir_exists(media_path + os.sep + user + os.sep + 'documents' + os.sep + 'input_files')

        if 'custom_file' in request.POST:
            if os.path.exists(os.path.join(media_path + os.sep + user + os.sep + 'documents', 'oh_encoder.json')):
                os.remove(os.path.join(media_path + os.sep + user + os.sep + 'documents', 'oh_encoder.json'))

            myFile = request.FILES.get('myFile')
            if myFile:
                if os.path.splitext(myFile.name)[-1] == ".csv":
                    fs = FileSystemStorage(location=os.path.join(media_path, user, 'documents' + os.sep + 'input_files' + os.sep))
                    myFile.name = get_valid_filename(myFile.name)
                    fs.save(myFile.name, myFile)
                    # uploaded_file_url = fs.url(filename)
                    messages.success(request, 'File Uploaded')

                    return redirect('/eda/')
                else:
                    messages.error(request, 'Please select valid file with extension .csv')
                    return redirect('/upload/')
            else:
                messages.error(request, 'Please upload csv file, then click on Upload')
                return redirect('/upload/')

        elif '_download' in list(request.POST.keys())[-1]:
            name = list(request.POST.keys())[-1]
            filename = name.split("_download")[0]
            filepath = os.path.join(media_path, 'sample_csv', filename)
            path = open(filepath, 'r')
            mime_type, _ = mimetypes.guess_type(filepath)
            response = HttpResponse(path, content_type=mime_type)
            response['Content-Disposition'] = "attachment; filename=%s" % filename
            return response
        else:
            shutil.copy(os.path.join(media_path, 'sample_csv', list(request.POST.keys())[-1]), os.path.join(media_path, user, 'documents', 'input_files'))
            return redirect('/eda/')

    return render(request, 'upload.html')


def divide_columns_into_df(df):
    num_columns = len(df.columns)
    if num_columns < 8:
        return [df]
    num_df = 2  # You can change this to divide into more dataframes if needed

    # Calculate the number of columns in each dataframe
    columns_per_df = num_columns // num_df
    remainder = num_columns % num_df

    dfs = []  # List to store the divided dataframes

    start_col = 0
    for i in range(num_df):
        # Calculate the end column index for the current dataframe
        end_col = start_col + columns_per_df
        if i < remainder:
            end_col += 1  # Distribute any remaining columns

        # Slice the dataframe to get the current subset of columns
        subset_df = df.iloc[:, start_col:end_col]

        # Append the subset dataframe to the list
        dfs.append(subset_df)

        # Update the start column index for the next iteration
        start_col = end_col

    return dfs

# @decorators.login_required
def eda(request):
    if 'guest_session_id' not in request.session and not request.user.is_authenticated:
        return redirect('/signin/')

    user = request.session['guest_session_id'] if request.session['guest_session_id'] else request.user.id

    if user is not None:
        file_path = os.path.join(media_path, str(user), 'documents', 'input_files')
        list_of_files = glob.glob(file_path + os.sep + '*')

        if not list_of_files:
            return redirect('/upload/')

        file_name = max(list_of_files, key=os.path.getmtime)

        with open(file_name, 'rb') as rawdata:
            result = chardet.detect(rawdata.read(10000))

        with open(file_name, newline='') as csvfile:
            dialect = csv.Sniffer().sniff(csvfile.read())
            if dialect.delimiter == ',':
                df = pd.read_csv(file_name, encoding=result['encoding'])  # Import the csv with a comma as the separator
            elif dialect.delimiter == ';':
                df = pd.read_csv(file_name, sep=';', encoding=result['encoding'])  # Import the csv with a semicolon as the separator
        # df = pd.read_csv(file_name, encoding=result['encoding'])
        df_html = df.sample(10)
        df_html = divide_columns_into_df(df_html)
        df_html = [i.to_html(classes="table table-bordered table-striped table-hover custom-table", index=False) for i in df_html]
        df_n_rows = df.shape[0]
        df_n_cols = df.shape[1]
        df_cols = [column for column in df.columns]
        df_describe = df.describe()
        df_describe = divide_columns_into_df(df_describe)
        # df_describe_html = [i.to_html(classes="custom-table") for i in df_describe]
        df_describe_html = [i.to_html(classes="table table-bordered table-striped table-hover custom-table") for i in df_describe]
        # all_categorical = [col for col in df.columns if df[col].nunique() < df.shape[0] // 5]
        # print("all_categorical", all_categorical)
        # object_categorical = [col for col in df.columns if
        #                       df[col].dtype == 'O' and df[col].nunique() < df.shape[0] // 5]

        all_categorical = [col for col in df.columns if df[col].nunique() < 15]
        # object_categorical = [col for col in df.columns if df[col].dtype == 'O' and df[col].nunique() < 15]

        folder = media_path + os.sep + str(user) + os.sep + 'graphs'
        check_dir_exists(folder)

        # png_files_path = []
        # a4_dims = (11.7, 8.27)
        # for i in all_categorical:
        #     plt.subplots(figsize=a4_dims)
        #     ax = sns.countplot(x=df[i], data=df)
        #     if df[i].nunique() > 5:
        #         ax.set_xticklabels(ax.get_xticklabels(), rotation=25)
        #     for p in ax.patches:
        #         ax.annotate('{:.1f}'.format(p.get_height()), (p.get_x(), p.get_height() + 5))
        #     plt.axis()
        #
        #     png_file_name = folder + os.sep + i + ".png"
        #     plt.savefig(png_file_name)
        #     plt.close()
        #     png_files_path.append(str(user) + os.sep + 'graphs' + os.sep + i + '.png')

        sns.set(style="whitegrid")

        # Define the folder to save the PNG files
        # output_folder = os.path.join(str(user), 'graphs')

        # Create the output folder if it doesn't exist
        # os.makedirs(output_folder, exist_ok=True)
        png_files_path = []
        a4_dims = (11.7, 8.27)

        for i in all_categorical:
            # Create a new figure with specified dimensions
            plt.subplots(figsize=a4_dims)

            # Create the count plot
            ax = sns.countplot(x=df[i], data=df, palette="Set2")

            # Rotate x-axis labels for better readability if there are many unique values
            if df[i].nunique() > 5:
                ax.set_xticklabels(ax.get_xticklabels(), rotation=25)

            # Annotate bars with count values above them
            for p in ax.patches:
                ax.annotate('{:.1f}'.format(p.get_height()), (p.get_x(), p.get_height() + 5))

            # Remove unnecessary plot axes
            # plt.axis('off')

            # Define the PNG file name
            png_file_name = os.path.join(folder, f"{i}.png")

            # Save the plot as a PNG file
            plt.savefig(png_file_name, bbox_inches='tight', pad_inches=0.1, dpi=300)

            # Close the current plot to release resources
            plt.close()

            # Append the PNG file path to the list
            png_files_path.append(os.path.abspath(png_file_name))

        try:
            data_corr = df.corr()

            # Create the heatmap
            f, ax = plt.subplots(figsize=a4_dims)
            sns.heatmap(data_corr, cmap='Blues', annot=True, fmt=".2f", cbar=True, linewidths=.5)

            # Customize the plot title and labels
            plt.title("Correlation Matrix", weight='bold', fontsize=15)

            # Save the correlation plot
            correlation_name = os.path.join(folder, 'correlation.png')
            plt.savefig(correlation_name, bbox_inches='tight', dpi=300)

            # Append the PNG file path to the list
            png_files_path.append(os.path.abspath(correlation_name))
        except Exception as err:
            print(f"[ERROR PLOTTING]: Unable to plot the heatmap due to: {str(err)}")

        if request.method == 'POST':
            return redirect('/data_preprocessing/')

        context = {'df_html': df_html, 'df_n_rows': df_n_rows, 'df_n_cols': df_n_cols, 'df_cols': df_cols, 'df_describe_html': df_describe_html, 'png_files_path': png_files_path, }
        return render(request, "eda.html", context)
    else:
        return redirect('/signin/')


# @decorators.login_required
def data_preprocessing(request):
    if 'guest_session_id' not in request.session and not request.user.is_authenticated:
        return redirect('/signin/')

    user = request.session['guest_session_id'] if request.session['guest_session_id'] else request.user.id
    # user = request.user.id
    docs_path = os.path.join(media_path, str(user), 'documents')
    file_path = os.path.join(docs_path, 'input_files')
    list_of_files = glob.glob(file_path + os.sep + '*')

    if not list_of_files:
        return redirect('/upload/')

    file_name = max(list_of_files, key=os.path.getmtime)  # TODO : NEED TO FIX

    with open(file_name, 'rb') as rawdata:
        result = chardet.detect(rawdata.read(10000))

    with open(file_name, newline='') as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read())
        if dialect.delimiter == ',':
            df_preprocessing = pd.read_csv(file_name, encoding=result['encoding'])  # Import the csv with a comma as the separator
        elif dialect.delimiter == ';':
            df_preprocessing = pd.read_csv(file_name, sep=';', encoding=result['encoding'])  # Import the csv with a semicolon as the separator

    # df_preprocessing = pd.read_csv(file_name, encoding=result['encoding'])

    df_col_numbers = df_preprocessing.shape[1]
    df_col_names = [column for column in df_preprocessing.columns]
    categorical_col_names = [col for col in df_preprocessing.columns if df_preprocessing[col].dtype == 'O' and df_preprocessing[col].nunique() < 15]
    df_null = df_preprocessing.isnull().values.any()
    df_null_columns = None
    all_null_columns = None
    string_cols = None
    list_to_handle_nan_values = ['mean', 'median', 'bfill', 'ffill', 0, 'delete records']
    list_to_handle_nan_str_values = ['bfill', 'ffill', 0, 'delete records']

    if df_null:
        df_null_columns, string_cols = [], []
        all_null_columns = df_preprocessing.columns[df_preprocessing.isna().any()].tolist()

        for i in all_null_columns:
            if is_string_dtype(df_preprocessing[i]):
                string_cols.append(i)
            else:
                df_null_columns.append(i)

    if request.method == 'POST':
        dependent_variable = request.POST['dep_var_name']
        slider_value = request.POST['slider_value']
        test_size_ratio = (100 - int(slider_value)) / 100
        # print(df_preprocessing.shape)

        if df_null:
            for i in all_null_columns:
                way = request.POST.get(i)
                if way == '0':
                    df_preprocessing[i] = df_preprocessing[i].fillna(0)
                elif way == 'bfill' or way == 'ffill':
                    df_preprocessing[i] = df_preprocessing[i].fillna(method=way)
                elif way == 'delete records':
                    df_preprocessing.dropna(subset=[i], inplace=True)
                elif way == 'mean':
                    df_preprocessing[i] = df_preprocessing[i].fillna((df_preprocessing[i].mean()))
                elif way == 'median':
                    df_preprocessing[i] = df_preprocessing[i].fillna((df_preprocessing[i].median()))

        selected_check_list = request.POST.getlist('checkbox_name')
        # selected_check_list = [i.strip() for i in selected_check_list]
        # print("----------")
        # print(selected_check_list)
        # print(type(selected_check_list))
        # print("----------")
        oh_encoder = ce.OrdinalEncoder(cols=categorical_col_names)
        df_preprocessing = oh_encoder.fit_transform(df_preprocessing)

        oh_encoder_params = oh_encoder.get_params()

        oh_encoder_dict = {}
        for i in oh_encoder_params['mapping']:
            temp_dict = i['mapping'].to_dict()
            temp_dict_in_str = json.dumps(temp_dict)
            temp_dict_lowercase = json.loads(temp_dict_in_str.lower())
            oh_encoder_dict[i['col']] = temp_dict_lowercase

        with open(docs_path + os.sep + "oh_encoder.json", "w") as outfile:
            json.dump(oh_encoder_dict, outfile)

        if dependent_variable not in selected_check_list and df_col_numbers - len(selected_check_list) > 1:
            df_preprocessing = df_preprocessing.drop(selected_check_list, axis=1)
            df_preprocessing.to_csv(media_path + os.sep + str(user) + os.sep + 'documents' + os.sep + 'df_preprocessed.csv')
            d = {'dependent_variable': dependent_variable, 'dependent_variable_type': str(df_preprocessing.dtypes[dependent_variable]), 'test_size_ratio': test_size_ratio}

            with open(media_path + os.sep + str(user) + os.sep + 'documents' + os.sep + "df_preprocessed.json", "w") as outfile:
                json.dump(d, outfile)

            return redirect('/model_selection/')
        elif df_col_numbers - len(selected_check_list) <= 1:
            messages.error(request, 'You cannot delete all the columns')
        else:
            messages.error(request, 'You cannot delete prediction column')

    context = {'df_null': df_null, 'nan_columns': df_null_columns, 'string_cols': string_cols, 'list_handle_nan_values': list_to_handle_nan_values, 'list_handle_nan_str_values': list_to_handle_nan_str_values, 'df_cols': df_col_names, }
    return render(request, 'data_preprocessing.html', context)


# @decorators.login_required
def model_selection(request):
    all_ml_models = ['(AutoML) Regression', 'Linear Regression', '(AutoML) Classification', 'Logistic Regression', 'Decision Tree Classifier', 'KNeighbors Classifier', 'Random Forest Classifier', 'GaussianNB Classifier', 'SGD Classifier']
    # automl_model_type = []
    # numerical_model_name_list = []
    # user = str(request.user.id)
    if 'guest_session_id' not in request.session and not request.user.is_authenticated:
        return redirect('/signin/')

    user = request.session['guest_session_id'] if request.session['guest_session_id'] else str(request.user.id)
    # if request.is_ajax():
    #     print('AJAX REQUEST')
    #     data = request.GET.get('data')
    classifier = False

    docs_path = media_path + os.sep + user + os.sep + 'documents'
    if not os.path.isfile(docs_path + os.sep + 'df_preprocessed.csv'):
        return redirect('/upload/')
    df_model = pd.read_csv(docs_path + os.sep + 'df_preprocessed.csv')
    df_model.drop(columns=df_model.columns[0], axis=1, inplace=True)
    file = open(docs_path + os.sep + 'df_preprocessed.json')
    json_file = json.load(file)
    dependent_variable = json_file['dependent_variable']
    dependent_variable_type = json_file['dependent_variable_type']
    test_size_ratio = json_file['test_size_ratio']

    # TODO : Display model based on dep var type

    X = df_model.drop([dependent_variable], axis=1)
    y = df_model[dependent_variable]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size_ratio, random_state=77, shuffle=True)
    p_X_train = X_train.copy()
    p_X_test = X_test.copy()

    if request.method == 'POST':
        sc_X = StandardScaler()
        model_name = request.POST.get('model_name')
        chosen_model_name = model_name
        evaluation_button = request.POST.get('evaluation')

        if evaluation_button is None:
            model_details = {}
            if model_name in ['(AutoML) Regression', '(AutoML) Classification']:
                model_name = model_name.split(" ")[-1]
                if model_name == 'Classification':
                    X_train = sc_X.fit_transform(X_train)
                    X_test = sc_X.transform(X_test)
                    classifier = True

                automl_model_name, model = get_automl_model(model_name.lower(), X_train, y_train)
                # used_model.append([user, automl_model_name])
                model_details['model_name'] = automl_model_name

            else:
                if model_name == 'Linear Regression':
                    model = get_linear_regression_model(X_train, y_train)
                else:
                    p_X_train = X_train.copy()
                    p_X_test = X_test.copy()
                    X_train = sc_X.fit_transform(X_train)
                    X_test = sc_X.transform(X_test)
                    if model_name == 'Logistic Regression':
                        model = get_logistic_regression_model(X_train, y_train)
                    elif model_name == 'Decision Tree Classifier':
                        model = get_decision_tree_classifier_model(X_train, y_train)
                    elif model_name == 'Random Forest Classifier':
                        model = get_random_forest_classifier_model(X_train, y_train)
                    elif model_name == 'GaussianNB':
                        model = get_gaussian_nb_model(X_train, y_train)
                    elif model_name == 'SGDClassifier':
                        model = get_sgd_classifier_model(X_train, y_train)
                    else:
                        model = get_kneighbors_classifier_model(X_train, y_train)
                    classifier = True

                # used_model.append([user, model_name])
                model_details['model_name'] = model_name

            model_details['model_type'] = model_name
            model_details['predictions'] = model.predict(X_test)
            # predictions.append([user, model.predict(X_test)])
            # filtered_predictions = [i for i in predictions if i[0] == user]

            # print("----------------------------------------")
            # model_details['model'] = model
            # print(model)
            # all_model.append([user, model])

            # print("----------------------------------------")
            if classifier:
                X_train = p_X_train
                X_test = p_X_test

            actual_pred_df = X_test.copy()
            actual_pred_df['Actual output'] = y_test
            actual_pred_df['Predicted output'] = model_details['predictions']
            actual_pred_df = actual_pred_df.to_html(classes="table table-striped table-hover", index=False)

            with open(media_path + os.sep + str(user) + os.sep + 'documents' + os.sep + 'model', 'wb') as files:
                pickle.dump(model, files)

            with open(media_path + os.sep + str(user) + os.sep + 'documents' + os.sep + "model_details.json", "w") as outfile:
                json.dump(model_details, outfile, cls=NumpyArrayEncoder)

            all_ml_models.remove(chosen_model_name)
            all_ml_models.insert(0, chosen_model_name)

            messages.success(request, f'Model "{str(model_name)}" has been trained successfully!')

            context = {'actual_pred_df': actual_pred_df, 'model_name_list': all_ml_models}

            return render(request, 'model_selection.html', context)
        else:

            # TODO: check model details json, model pickle file and load it in next function
            # model_details = {'X': X, 'y': y, 'X_train': X_train, 'y_train': y_train, 'X_test': X_test, 'y_test': y_test}

            X.to_csv(docs_path + os.sep + 'X.csv')
            y.to_csv(docs_path + os.sep + 'y.csv')
            X_train.to_csv(docs_path + os.sep + 'X_train.csv')
            y_train.to_csv(docs_path + os.sep + 'y_train.csv')
            X_test.to_csv(docs_path + os.sep + 'X_test.csv')
            y_test.to_csv(docs_path + os.sep + 'y_test.csv')

            # print("used_model", used_model)
            # global model_value
            # used_model_name = [i for i in used_model if i[0] == user]
            # filtered_predictions = [i for i in predictions if i[0] == user]
            # filtered_selected_model = [i for i in selected_model_type if i[0] == user]
            # filtered_model = [i for i in all_model if i[0] == user]
            #
            # def model_value():
            #     return [used_model_name[-1][-1], filtered_model[-1][-1], X_train, X_test, y_train, y_test, filtered_predictions[-1][-1], df_model, X, y, filtered_selected_model[-1][-1]]

            return redirect('/model_evaluation/')

    context = {'model_name_list': all_ml_models}
    return render(request, 'model_selection.html', context)  # except:  #     return redirect('/eda/')


# @decorators.login_required
def model_evaluation(request):
    if 'guest_session_id' not in request.session and not request.user.is_authenticated:
        return redirect('/signin/')

    user = request.session['guest_session_id'] if request.session['guest_session_id'] else str(request.user.id)
    # user = str(request.user.id)
    docs_path = media_path + os.sep + user + os.sep + 'documents'
    if not os.path.isfile(docs_path + os.sep + 'model_details.json'):
        return redirect('/upload/')
    file = open(docs_path + os.sep + 'model_details.json')
    json_file = json.load(file)
    model_name = json_file['model_name']
    y_test = pd.read_csv(docs_path + os.sep + 'y_test.csv')
    y_test.drop(columns=y_test.columns[0], axis=1, inplace=True)
    y_pred = np.asarray(json_file['predictions'])
    model_eva_type = json_file['model_type']

    if model_eva_type in ['Regression', 'Linear Regression']:
        folder_ = media_path + os.sep + user + os.sep + 'regression_graphs'
        check_dir_exists(folder_)
        png_file_name_ = folder_ + os.sep + "true_vs_predictions.png"
        mae = metrics.mean_absolute_error(y_test, y_pred)
        mse = metrics.mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(metrics.mean_squared_error(y_test, y_pred))
        # model_score = '%.2f' % (model.score(X_test, y_test) * 100) + ' %'
        # my_data = [['Model', model_name], ['Mean Absolute Error', mae], ['Mean Squared Error', mse],
        #            ['Root Mean Squared Error', rmse], ['Model Score', model_score]]

        my_data = [['Model', model_name], ['Mean Absolute Error', mae], ['Mean Squared Error', mse], ['Root Mean Squared Error', rmse]]

        # plt.scatter(y_test, y_pred, c='crimson')  # plt.yscale('log')  # plt.xscale('log')  #  # p1 = max(max(y_pred), max(y_test))  # p2 = min(min(y_pred), min(y_test))  # plt.plot([p1, p2], [p1, p2], 'b-')  # plt.xlabel('True Values')  # plt.ylabel('Predictions')  # plt.axis('equal')  # plt.savefig(png_file_name_)  # plt.close()

    else:
        # print(model_name)
        # cm = confusion_matrix(y_test, y_pred)
        # print("TN", cm[0][0], "FP", cm[0][1])
        # print("FN", cm[1][0], "TP", cm[1][1])
        # class_report = metrics.classification_report(y_test, y_pred)
        # print("class_report: ", class_report)

        # if _check_targets(y_test, y_pred)[0] == 'multiclass':
        #     average = 'multiclass'
        # else:
        #     average = 'binary'

        # accuracy = '%.2f' % (metrics.accuracy_score(y_test, y_pred) * 100) + ' %'
        # recall = '%.2f' % (metrics.recall_score(y_test, y_pred, average=average) * 100) + ' %'
        # f1 = '%.2f' % (metrics.f1_score(y_test, y_pred, average=average) * 100) + ' %'
        # precision = '%.2f' % (metrics.precision_score(y_test, y_pred, average=average) * 100) + ' %'

        try:
            accuracy = '%.2f' % (metrics.accuracy_score(y_test, y_pred) * 100) + ' %'
            recall = '%.2f' % (metrics.recall_score(y_test, y_pred) * 100) + ' %'
            f1 = '%.2f' % (metrics.f1_score(y_test, y_pred) * 100) + ' %'
            precision = '%.2f' % (metrics.precision_score(y_test, y_pred) * 100) + ' %'

        except:
            messages.info(request, 'For Regression problem, use only Regression model')
            return redirect('/model_selection/')
            # return render(request, 'model_evaluation.html')

        my_data = [['Model', model_name], ['Accuracy Score', accuracy], ['Recall Score', recall], ['F1 score', f1], ['Precision', precision]]

        png_file_name_ = None

    df_ev = pd.DataFrame(my_data, columns=['Metrics', 'Values'])
    df_to_html = df_ev.to_html(classes="table table-striped table-hover", index=False)

    context = {'model_name': model_name, 'df': df_to_html, 'fig': png_file_name_, }
    return render(request, 'model_evaluation.html', context)


# @decorators.login_required
def save_model(request):
    if 'guest_session_id' in request.session and not request.user.is_authenticated:
        messages.error(request, 'Create an account to save the model.')
        return redirect('/model_evaluation/')
    elif 'guest_session_id' not in request.session and not request.user.is_authenticated:
        return redirect('/signin/')

    user_id = request.user.id
    user = User.objects.get(id=user_id)
    docs_path = media_path + os.sep + str(user_id) + os.sep + 'documents'
    graphs_path = media_path + os.sep + str(user_id) + os.sep + 'graphs'
    if user:
        if not os.path.isfile(docs_path + os.sep + 'model_details.json'):
            return redirect('/upload/')
        file = open(docs_path + os.sep + 'model_details.json')
        json_file = json.load(file)
        # model_attributes = model_value()
        with open(docs_path + os.sep + 'model', 'rb') as f:
            model = pickle.load(f)
        model_name = json_file['model_name']
        used_model_type = json_file['model_type']
        file.close()
        X = pd.read_csv(docs_path + os.sep + 'X.csv')
        X.drop(columns=X.columns[0], axis=1, inplace=True)
        y = pd.read_csv(docs_path + os.sep + 'y.csv')
        y.drop(columns=y.columns[0], axis=1, inplace=True)

        X_cols = [column for column in X.columns]
        if request.method == 'POST':
            project_name = request.POST.get('project_name')
            pickle_file = pickle.dumps(model)

            if os.path.exists(os.path.join(docs_path, 'oh_encoder.json')):
                oh_encoder = json.load(open(os.path.join(docs_path, 'oh_encoder.json')))
            else:
                oh_encoder = None

            # ============ Saving document path with user id ============ #
            file_path = os.path.join(media_path, str(user_id), 'documents', 'input_files')
            list_of_files = glob.glob(file_path + os.sep + '*')
            file_name = max(list_of_files, key=os.path.getmtime)
            doc_id = Document(user_id=user.id, document=file_name)
            doc_id.save()

            # ============ filtering docs with user id and uploaded doc name ============ #
            doc_id = Document.objects.filter(user_id=user.id, document=doc_id)
            last_doc_id = doc_id[0].id
            # last_doc_id = doc_id[len(doc_id)-1].id

            # ============ creating an instance for trained model to be saved ============ #
            doc_instance = Document.objects.get(id=last_doc_id)

            X_json = X.to_json(orient='records')
            data = TrainedModels(user_id=user.id, document=doc_instance, project_name=project_name, model_file=pickle_file, column_names=X_cols, model_name=model_name, model_type=used_model_type, oh_encoders=oh_encoder, independent_variable=X_json)
            data.save()

            # ============ Clearing memory - Comment to keep the files ============
            # os.remove(os.path.join(docs_path, 'oh_encoder.json'))
            shutil.rmtree(docs_path)
            shutil.rmtree(graphs_path)

            # check_dir_exists(docs_path)
            # check_dir_exists(graphs_path)
            # check_dir_exists(docs_path + os.sep + 'input_files')

            messages.success(request, 'Your Project has been saved successfully !')

            return redirect('/profile_data/')
        return render(request, 'save_model.html')
    else:
        return redirect("/signin/")


@decorators.login_required
def profile_data(request):
    user = str(request.user.id)
    docs_name_list = []
    projects_name_list = []
    model_id = []
    if user:
        document = Document.objects.filter(user_id=user)
        if document:
            for doc in document:
                doc_name = str(doc).split("/")[-1]
                model_data = TrainedModels.objects.filter(document_id=doc.id).values()
                if model_data:
                    for md in model_data:
                        project_name = str(md['project_name'])
                        docs_name_list.append(doc_name)
                        projects_name_list.append(project_name)
                        # print(md['id'])
                        model_id.append(md['id'])

            if request.method == 'POST':
                button_id = request.POST.get('test_model_button')
                return redirect(f'/model_testing/{int(button_id)}')

            context = {'document_project_name': zip(docs_name_list, projects_name_list, model_id), }
        else:
            context = {'document_project_name': None, }
        return render(request, 'profile_data.html', context)

    else:
        return redirect('/signin/')


@decorators.login_required
def model_testing(request, button_id):
    user = request.user
    user_id = user.id
    if user_id:
        # get_doc_id = Document.objects.filter(user_id=user).values()
        # print('get_doc_id', get_doc_id)
        # model_data = TrainedModels.objects.filter(document_id=get_doc_id[int(button_id)]['id']).values()  # TODO  : NEED to fix this
        model_data = TrainedModels.objects.filter(user=user_id, id=button_id).values()  # TODO  : NEED to fix this
        # print('model_data', model_data[0])
        df_test = None
        project_name = model_data[0]['project_name']
        model_name = model_data[0]['model_name']
        col_names = ast.literal_eval(model_data[0]['column_names'])
        predict = ["" for i in range(len(col_names))]
        if request.method == 'POST':
            sc_X = StandardScaler()
            model_file = model_data[0]['model_file']
            saved_model_type = model_data[0]['model_type']
            one_hot_decoder = model_data[0]['oh_encoders']
            X = ast.literal_eval(model_data[0]['independent_variable'])
            predict = request.POST.getlist('inputs')
            to_be_predicted = []
            for column, value in zip(col_names, predict):
                if one_hot_decoder and column in one_hot_decoder.keys():
                    val = one_hot_decoder[column][value.lower()]
                    try:
                        to_be_predicted.append(int(val))
                    except:
                        to_be_predicted.append(float(val))
                else:
                    try:
                        to_be_predicted.append(int(value))
                    except:
                        to_be_predicted.append(float(value))

            model_file = pickle.loads(model_file)
            to_be_predicted = [to_be_predicted]
            if saved_model_type not in ['Regression', 'Linear Regression']:
                X = pd.DataFrame(X)
                sc_X.fit(X)
                to_be_predicted = pd.DataFrame(to_be_predicted, columns=col_names)
                to_be_predicted = sc_X.transform(to_be_predicted)

            custom_predictions = model_file.predict(to_be_predicted)
            custom_predictions = str(custom_predictions[0])
            test_data = [['Prediction', custom_predictions]]
            df_test = pd.DataFrame(test_data)
            df_test = df_test.to_html(classes="table table-striped table-hover", index=False, header=False)
        context = {'model_name': model_name, 'predictions': df_test, 'col': zip(col_names, predict), 'project_name': project_name}
        return render(request, 'model_testing.html', context)
    else:
        return redirect('/signin/')
