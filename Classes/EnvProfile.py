# This is the parser for an App's profile

import pandas as pd
from functools import reduce
from Classes.RapidProfile import RapidProfile


class EnvProfile(RapidProfile):
    def __init__(self, df, host_name):
        RapidProfile.__init__(self, df)
        self.hostName = host_name
        self.partitionData()
        self.cleanData()
        self.cleanFeatures()

    def partitionData(self):
        ind_len = int(len(self.x) / 3)
        self.sys1DF = RapidProfile(self.dataFrame[self.x[0:ind_len]])
        self.sys2DF = RapidProfile(self.dataFrame[self.x[ind_len:2 * ind_len]])
        self.combinedDF = RapidProfile(self.dataFrame[self.x[2 * ind_len:]])

    def cleanFeatures(self):
        self.sys1DF.cleanLabelByExactName(
            list(map(lambda x: x + '-1', RapidProfile.EXCLUDED_FEATURES)))
        self.sys2DF.cleanLabelByExactName(
            list(map(lambda x: x + '-2', RapidProfile.EXCLUDED_FEATURES)))
        self.combinedDF.cleanLabelByExactName(
            list(map(lambda x: x + '-C', RapidProfile.EXCLUDED_FEATURES)))

    def cleanData(self):
        self.sys1DF.dataFrame['INST-1'] = self.sys1DF.dataFrame['ACYC-1'].div(
            self.sys1DF.dataFrame['INST-1'])
        self.sys2DF.dataFrame['INST-2'] = self.sys2DF.dataFrame['ACYC-2'].div(
            self.sys2DF.dataFrame['INST-2'])
        self.combinedDF.dataFrame['INST-C'] = self.combinedDF.dataFrame[
            'ACYC-C'].div(self.combinedDF.dataFrame['INST-C'])

    def scaleAll(self):
        self.sys1DF.scale()
        self.sys2DF.scale()
        self.combinedDF.scale()

    def getFeatures(self):
        return self.sys1DF.x + self.sys2DF.x

    def getYLabel(self):
        return self.combinedDF.x

    def getX(self):
        return pd.concat([
            self.sys1DF.dataFrame[self.sys1DF.x],
            self.sys2DF.dataFrame[self.sys2DF.x]
        ],
                         axis=1,
                         join="inner")

    def getY(self):
        return self.combinedDF.dataFrame[self.combinedDF.x]
