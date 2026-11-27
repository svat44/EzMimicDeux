import sys, pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
p="C:/Users/delib/.cache/kagglehub/datasets/williamkaiser/all-isef-projects/versions/30/isef-database.csv"
df=pd.read_csv(p)
for t in sys.argv[1:]:
    m=df[df.title.str.contains(t,regex=False,na=False)]
    for _,r in m.iterrows():
        print(f"\n[{r.year}] {r.title} | {r.category} | awards: {str(r.awards)[:80]}\n{str(r.abstract)[:1100]}")
