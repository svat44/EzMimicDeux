import pandas as pd, re, sys
sys.stdout.reconfigure(encoding="utf-8")
p="C:/Users/delib/.cache/kagglehub/datasets/williamkaiser/all-isef-projects/versions/30/isef-database.csv"
df=pd.read_csv(p); df['text']=(df.title.fillna('')+'. '+df.abstract.fillna('')).str.lower()
terms=[l.strip() for l in open(sys.argv[1]) if l.strip()]
show=int(sys.argv[2]) if len(sys.argv)>2 else 4
for t in terms:
    m=df[df.text.str.contains(t,regex=True)]
    print(f"\n## {t}  -> {len(m)}")
    for _,r in m.head(show).iterrows(): print(f"   [{r.year}] {r.title[:110]}")
