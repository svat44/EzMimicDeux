import sys, pandas as pd, numpy as np
sys.stdout.reconfigure(encoding='utf-8')
from sklearn.feature_extraction.text import TfidfVectorizer
p="C:/Users/delib/.cache/kagglehub/datasets/williamkaiser/all-isef-projects/versions/30/isef-database.csv"
df=pd.read_csv(p); df=df[df.abstract.notna()&(df.abstract.str.len()>200)].reset_index(drop=True)
df['text']=df.title+'. '+df.abstract
v=TfidfVectorizer(stop_words='english',min_df=3,ngram_range=(1,2),sublinear_tf=True)
X=v.fit_transform(df.text)
C={
 'earbud_dose':'earbud headphone sound pressure level eardrum ear simulator coupler frequency response listening exposure dose hearing damage calibration',
 'indoor_wetbulb':'indoor heat wave wet-bulb temperature humidity older adults apartment fan cooling heat illness sensor logger',
 'dryer_airborne':'tumble dryer microfiber airborne emission lint filter condenser heat pump particle counter microplastic fibers',
 'smoke_alarm_audibility':'smoke alarm audibility sleeping bedroom closed door attenuation 520 Hz low frequency waking children hearing loss',
 'oximeter_skin_bias':'pulse oximeter skin pigmentation bias melanin phantom SpO2 accuracy dark skin photoplethysmography wavelength',
 'leftover_cooling':'cooked food cooling rate home refrigerator container depth danger zone bacterial growth foodborne illness',
 'kitchen_microplastic':'microplastics released from cutting board kitchen utensils nonstick cookware tea bag food preparation Nile red fluorescence',
 'pill_splitting':'tablet pill splitting dose accuracy elderly medication cutting uneven weight',
 'eyedrop':'eye drop bottle drop volume dosing glaucoma patients squeeze force elderly',
 'epipen_heat':'epinephrine auto-injector heat exposure car temperature storage excursion degradation logger',
 'crosswalk':'pedestrian crossing signal timing walking speed older adults crosswalk video analysis',
 'helmet_fit':'bicycle helmet fit position child concussion strap',
 'cooking_pm':'cooking aerosol particulate low-cost sensor overestimate humidity calibration kitchen exposure',
 'oral_dosing':'liquid medicine dosing cup syringe measurement error parents children dose',
 'phone_flashlight_spectro':'smartphone camera lateral flow colorimetric reader lighting variation calibration card',
 'dental':'tooth brushing plaque toothbrush force bristle wear toothpaste abrasion enamel',
 'sunscreen_thickness':'sunscreen application thickness UV camera coverage missed spots skin',
 'baby_sleep':'infant safe sleep suffocation soft bedding mattress firmness sensor',
 'water_heater_scald':'hot water scald tap temperature children elderly legionella water heater setpoint',
 'cough_acoustic':'cough sound classification smartphone microphone respiratory disease screening',
}
for k,t in C.items():
    q=v.transform([t]); s=(X@q.T).toarray().ravel()
    idx=s.argsort()[::-1][:3]
    print(f"\n== {k}  maxsim={s[idx[0]]:.2f}")
    for i in idx: print(f"   {s[i]:.2f} [{df.year[i]}] {df.title[i][:105]}")
