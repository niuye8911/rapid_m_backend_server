# The base class for profiling data in RAPID_M

from functools import reduce
from pathlib import Path

import pandas as pd
from sklearn import preprocessing
from sklearn.externals import joblib


class RapidProfile:
    # pre_determined excluded system footprint that won't affect perf
    EXCLUDED_FEATURES = {
        "AFREQ",
        "ACYC",
        'C0res%',
        'C10res%',
        'C1res%',
        'C2res%',
        'C3res%',
        'C6res%',
        'C7res%',
        'C8res%',
        'C9res%',
        'Proc Energy (Joules)',
        'Configuration',
        'TIME(ticks)',
        'SLOWDOWN',
        # some features that can be calculated by others
        'PhysIPC',
        #'L2MISS',
        #'L3MISS',
        #'L3MPI',
        'INSTnom',  # this can be calculated by instnom /100 * 4
        'READ',
        'WRITE',
        'stresser',
        #'L2MPI'
    }

    SCALAR_PATH = './RapidScalar.pkl'

    def __init__(self, df):
        self.dataFrame = df
        # default x = first N-1 row
        self.x = df.columns.values.tolist()
        # default y = last column
        self.y = []

    def setXLabel(self, x):
        '''determine the X vector(features)'''
        self.x = x

    def setYLabel(self, y):
        '''determine the Y vector(observations)'''
        self.y = y

    def getXData(self):
        return self.dataFrame[self.x]

    def getYData(self):
        return self.dataFrame[self.y]

    def cleanLabelByExactName(self, excludes):
        '''
        @param excludes: a vector containing all unwanted feature string
        note that the 'x' has already been cleaned up by cleanData()
        '''
        match_func = lambda feature: reduce((lambda x, y: (y == feature) or x),
                                            excludes, False)
        self.x = list(filter(lambda feature: not match_func(feature), self.x))
        return

    def createScalar(self, writeout):
        ''' create a persistent scaler for all data '''
        data = self.dataFrame[self.x]
        min_max_scaler = preprocessing.MinMaxScaler(feature_range=(0, 1))
        self.scalar = min_max_scaler.fit(data)
        if writeout:
            joblib.dump(self.scalar, 'RapidScalar.pkl')

    def loadScalar(self, writeout):
        ''' load an existing scalar '''
        if not Path(RapidProfile.SCALAR_PATH).is_file():
            self.createScalar(writeout)
        self.scalar = joblib.load('RapidScalar.pkl')

    def scale(self, writeout=False):
        self.loadScalar(writeout)
        self.dataFrame[self.x] = pd.DataFrame(
            self.scalar.transform(self.dataFrame[self.x]))

    def scale_tmp(self, data):
        ''' temporarily scale the data and return '''
        min_max_scaler = preprocessing.MinMaxScaler(feature_range=(0, 1))
        scaler = min_max_scaler.fit(data)
        return scaler.transform(data)

    def cleanData(self, postfix=''):
        # !!!! REMEMBER TO UPDATE foramtEnv() in BucketSelector
        ''' clean the PCM data to correct form '''
        # re-calculate the numerical value
        new_frame = pd.DataFrame()
        for col in self.dataFrame.columns:
            # 1) INST
            if col == 'INST' + postfix:
                new_frame[col] = self.dataFrame['ACYC' + postfix].div(
                    self.dataFrame['INST' + postfix])
            # 2) INSTnom% and PhysIPC%
            elif col == 'INSTnom%' + postfix or col == 'PhysIPC%' + postfix:
                new_frame[col] = self.dataFrame[col].apply(lambda x: x / 100.0)
            else:
                new_frame[col] = self.dataFrame[col]
        # add the MEM
        new_frame['MEM' +
                  postfix] = self.dataFrame['READ' +
                                            postfix] + self.dataFrame['WRITE' +                                                          postfix]
        self.x.append('MEM' + postfix)
        self.dataFrame = new_frame
