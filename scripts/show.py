import pandas as pd, re, sys
sys.stdout.reconfigure(encoding="utf-8")
p="C:/Users/delib/.cache/kagglehub/datasets/williamkaiser/all-isef-projects/versions/30/isef-database.csv"
df=pd.read_csv(p); df['text']=(df.title.fillna('')+'. '+df.abstract.fillna('')).str.lower()
for pat in sys.argv[2:]:
    m=df[df.text.str.contains(pat,regex=True)]
    print(f"\n######## {pat} ({len(m)})")
    for _,r in m.head(int(sys.argv[1])).iterrows():
        print(f"\n[{r.year}] {r.title}\n{str(r.abstract)[:900]}")
