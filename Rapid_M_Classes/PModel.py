import pandas as pd
from sklearn import preprocessing
from sklearn.base import clone
from sklearn.feature_selection import RFE
from sklearn import metrics
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression, LassoCV, ElasticNetCV
from sklearn import linear_model
from Utility import *
from models.ModelPool import *


class PModel:
    CANDIDATE_MODELS = {
        'linear': LinearRegression(),
        'EN': ElasticNetCV(cv=3, max_iter=1000000),
        'lassoCV': LassoCV(cv=3, max_iter=1000000),
        'Bayesian': linear_model.BayesianRidge()
    }

    def __init__(self, p_info='', maxes={}):
        self.model = None
        self.TRAINED = False
        self.mse = -1.
        self.mae = -1.
        self.r2 = -1.
        self.output_loc = ''
        self.modelPool = ModelPool()
        self.maxes = maxes
        if p_info is not '':
            # read from a file
            self.loadFromInfo(p_info)

    def setMaxes(self, maxes):
        self.maxes = maxes

    def loadFromInfo(self, info):
        # TODO: change
        self.model = self.modelPool.getModel(info['model_type'], info['file'])
        self.TRAINED = True
        self.polyFeature = info['poly']
        self.model_type = info['model_type']
        self.features = info['feature']

    def setDF(self, dataFrame, feature):
        self.df = dataFrame
        self.features = feature

    def train(self):
        x = self.__scaleInput(self.df[self.features])
        y = self.df['SLOWDOWN']
        x_train, self.x_test, y_train, self.y_test = train_test_split(
            x, y, test_size=0.3, random_state=0)
        RAPID_info("TRAINED", x_train.shape[0])
        # select the model and features
        self.getModel(x_train, y_train, self.x_test, self.y_test)
        self.TRAINED = True

    def getModel(self, x_train, y_train, x_test, y_test):
        # first pass: select model
        model, isPoly, training_time = self.modelPool.selectModel(
            x_train, x_test, y_train, y_test)
        print("selected Model:", model.name, "ispoly:", isPoly)
        # second pass: select feature
        model, min_features = self.modelPool.selectFeature(
            self.df[self.features],
            self.df['SLOWDOWN'],
            x_train,
            x_test,
            y_train,
            y_test,
            model.name,
            isPoly,
            speedup=False)
        RAPID_info("SELECTED_FEATURES", min_features)
        # third phase: finalize model
        final_model = self.modelPool.getModel(model.name)
        x = x_train[min_features]
        x_test = x_test[min_features]
        self.x_test = x_test
        if isPoly:
            x = PolynomialFeatures(degree=2).fit_transform(x)
            x_test = PolynomialFeatures(degree=2).fit_transform(x_test)
        elapsed_time = final_model.fit(x, y_train)
        r2, mse, diff = final_model.validate(x_test, y_test)
        training_time['final'] = {
            'time': elapsed_time,
            'r2': r2,
            'mse': mse,
            'diff': diff
        }
        self.model = final_model
        self.polyFeature = isPoly
        self.features = min_features
        self.modelType = final_model.name

    def getModel_deprecated(self, x_train, y_train, x_test, y_test):
        # use the validate process to pick the most important 10 linear features
        # scale the data
        min_max_scaler = preprocessing.MinMaxScaler(feature_range=(0, 1))
        scalar = min_max_scaler.fit(x_train)
        x_train_scaled = scalar.transform(x_train)
        # iterate through all models
        selected_features = []
        selected_poly = False
        min_mse = 99999
        selected_model_name = ''
        for model_name, model in PModel.CANDIDATE_MODELS.items():
            rfe = RFE(model, 5)
            fit = rfe.fit(x_train_scaled, y_train)
            # get the feature names:
            feature_names = list(
                filter(lambda f: fit.ranking_[self.features.index(f)] == 1,
                       self.features))
            selected_x_train = x_train[feature_names]
            selected_x_train_poly = PolynomialFeatures(
                degree=2).fit_transform(selected_x_train)
            selected_x_test_poly = PolynomialFeatures(degree=2).fit_transform(
                self.x_test[feature_names])
            # train 1st order
            linear_model = clone(model)
            linear_model.fit(selected_x_train, y_train)
            diff, mse = self.validate(self.x_test[feature_names], linear_model)
            if mse < min_mse:
                selected_features = feature_names
                selected_poly = False
                selected_model_name = model_name
                min_mse = mse
                self.model = linear_model
            # train the 2nd order
            high_model = clone(model)
            high_model.fit(selected_x_train_poly, y_train)
            diff, mse = self.validate(selected_x_test_poly, high_model)
            if mse < min_mse:
                selected_poly = True
                min_mse = mse
                self.model = high_model

        # set all members
        self.polyFeature = selected_poly
        self.features = selected_features
        self.modelType = selected_model_name
        if selected_poly:
            self.x_test_selected = selected_x_test_poly
        else:
            self.x_test_selected = self.x_test[selected_features]

    def validate(self, x=None, model=None):
        if x is None:
            x = self.x_test if not self.polyFeature else PolynomialFeatures(
                degree=2).fit_transform(self.x_test)
        if model is None:
            model = self.model
        self.y_pred = model.predict(x)
        self.mse = np.sqrt(metrics.mean_squared_error(self.y_test,
                                                      self.y_pred))
        self.mae = metrics.mean_absolute_error(self.y_test, self.y_pred)
        self.r2 = r2_score(self.y_test, self.y_pred)
        # relative error
        self.diffs = list(abs(self.y_test - self.y_pred) / self.y_test)
        self.diff = sum(self.diffs) / len(self.diffs)
        return self.diff, self.mse

    def loadFromFile(self, model_file):
        self.model = pickle.load(open(model_file, 'rb'))
        self.TRAINED = True

    def __scaleInput(self, df):
        result_df = pd.DataFrame()
        for col in df.columns:
            result_df[col] = df[col] / self.maxes[col]
        return result_df

    def formulate_env(self, env):
        ''' given a df (env), filtered out the unwanted feature and get poly '''
        input = env[self.features]
        if self.polyFeature:
            input = PolynomialFeatures(degree=2).fit_transform(
                self.__scaleInput(input))
        return input

    def predict(self, system_profile):
        ''' the input is a df with all features '''
        pred_slowdown = self.model.predict(self.formulate_env(system_profile))
        return pred_slowdown

    def write_to_file(self, output_prefix):
        # save the model to disk
        self.model.save(output_prefix)
        self.output_loc = output_prefix

    def dump_into_app(self, app, name):
        app.model_params[name] = dict()
        app.model_params[name]["file"] = self.output_loc
        app.model_params[name]["mse"] = self.mse
        app.model_params[name]["mae"] = self.mae
        app.model_params[name]["diff"] = self.diff
        app.model_params[name]["r2"] = self.r2
        app.model_params[name]["feature"] = self.features
        app.model_params[name]["poly"] = self.polyFeature
        app.model_params[name]["model_type"] = self.modelType

    def drawPrediction(self, output):
        predictions = self.y_pred
        observations = self.y_test
        normed_pred = (predictions - min(observations)) / (max(observations) -
                                                           min(observations))
        normed_obs = (observations - min(observations)) / (max(observations) -
                                                           min(observations))
        # plot the base line
        x = [0, 1]
        y = [0, 1]
        plt.plot(x, y, 'r-')
        plt.plot(normed_obs, normed_pred, 'x', color='black')
        plt.xlim(0, 1)
        plt.ylim(0, 1)
        plt.xlabel('SlowDown Observation')
        plt.ylabel('Prediction')
        plt.savefig(output)

    def printPrediction(self, outfile):
        result = pd.DataFrame({'GT': self.y_test, 'Pred': self.y_pred})
        overall = pd.concat([self.x_test, result], axis=1)
        overall.to_csv(outfile)
