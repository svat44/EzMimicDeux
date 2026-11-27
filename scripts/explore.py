import sys, pandas as pd
p = sys.argv[1]
df = pd.read_csv(p)
print(df.shape)
print(df.year.value_counts().sort_index().to_string())
print(df.category.value_counts().to_string())
print(df.abstract.str.len().describe())
print(df.country.value_counts().head(10).to_string())
