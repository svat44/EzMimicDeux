import pandas as pd, numpy as np, re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
p="C:/Users/delib/.cache/kagglehub/datasets/williamkaiser/all-isef-projects/versions/30/isef-database.csv"
df=pd.read_csv(p); df=df[df.abstract.notna()&(df.abstract.str.len()>200)].reset_index(drop=True)
df['text']=df.title+'. '+df.abstract
v=TfidfVectorizer(stop_words='english',max_df=0.3,min_df=5,ngram_range=(1,2),sublinear_tf=True,max_features=60000)
X=v.fit_transform(df.text)
k=120
km=MiniBatchKMeans(k,random_state=0,n_init=3,batch_size=2048).fit(X)
df['cl']=km.labels_
terms=np.array(v.get_feature_names_out())
rows=[]
for c in range(k):
    idx=np.where(km.labels_==c)[0]
    cen=km.cluster_centers_[c]
    top=terms[cen.argsort()[::-1][:8]]
    rows.append((len(idx),c,', '.join(top)))
for n,c,t in sorted(rows):
    print(n,c,t)
df[['title','category','year','cl']].to_csv('C:/UltraNiche/scripts/clusters.csv',index=False)
