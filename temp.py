import pandas as pd

data = pd.read_excel("Data required .project25.ods", engine="odf")
print(data.head())
print(data.columns)