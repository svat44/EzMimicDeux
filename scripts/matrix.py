import sys, re, pandas as pd, itertools
sys.stdout.reconfigure(encoding='utf-8')
p="C:/Users/delib/.cache/kagglehub/datasets/williamkaiser/all-isef-projects/versions/30/isef-database.csv"
df=pd.read_csv(p); df['t']=(df.title.fillna('')+'. '+df.abstract.fillna('')).str.lower()
D={ # application domains (real-world settings)
 'hearing/noise':r'\bhearing\b|\bdeaf\b|\bnoise\b|\bsound level|\btinnitus',
 'eyesight/low-vision':r'\bblind\b|\bvisually impaired|\blow vision|\bcolou?r.?blind',
 'elder-care/falls':r'\belderly\b|\bolder adults?\b|\bseniors?\b|\bfalls?\b|\bdementia',
 'stroke/rehab/prosthetic':r'\bstroke\b|\brehabilit|\bprosthe|\bexoskeleton|\bparalys',
 'kitchen/food-prep':r'\bkitchen\b|\bcooking\b|\bcookware|\bfood safety|\bleftover|\bfood spoil',
 'drinking-water-home':r'\bdrinking water\b|\btap water\b|\bwell water\b|\bwater quality',
 'indoor-air/home':r'\bindoor air\b|\bindoor\b|\bhousehold\b|\bapartment',
 'clothing/laundry':r'\blaundry\b|\bclothes\b|\bclothing\b|\bgarment|\bfabric|\btextile',
 'sleep/bedroom':r'\bsleep\b|\bbedroom\b|\binsomnia\b|\bapnea',
 'children/toys/school':r'\bchildren\b|\bkids?\b|\btoddler|\binfant|\bbaby',
 'pets/livestock':r'\bdogs?\b|\bcats?\b|\bpets?\b|\blivestock|\bcattle|\bpoultry',
 'bees/pollinators':r'\bbees?\b|\bpollinat',
 'roads/pedestrians':r'\bpedestrian|\bcrosswalk|\bcyclist|\bbicycle|\broad safety',
 'disaster/flood/fire':r'\bflood|\bwildfire|\bearthquake|\bhurricane|\bdisaster|\bfire safety',
 'waste/recycling':r'\brecycl|\be-?waste\b|\bwaste sort|\blandfill|\bcompost',
 'small-farm/soil':r'\bsmallholder|\bsoil moisture|\bsoil nutrient|\birrigation|\bcrop yield',
 'medication/pharmacy':r'\bmedication\b|\bpills?\b|\btablet\b|\bdrug adherence|\binhaler|\binsulin',
 'dental/oral':r'\bdental\b|\bteeth\b|\btooth\b|\bcavit|\bplaque',
 'skin/sun':r'\bsunscreen|\bsunburn|\buv exposure|\bskin cancer|\bwound',
 'mental/stress':r'\banxiety\b|\bdepression\b|\bstress\b|\bmental health',
 'speech/communication':r'\bspeech\b|\bstutter|\baphasia|\bsign language|\bautism',
 'buildings/housing':r'\bbuilding\b|\bhousing\b|\broof\b|\binsulation|\bconcrete|\bwindow',
 'public-transit/vehicles':r'\bbus\b|\btrain\b|\bsubway|\bcar seat|\bvehicle cabin|\bdriver',
}
T={ # techniques / methods
 'acoustic/audio sensing':r'\bmicrophone|\bacoustic|\bsound (sensor|signal|wave)|\baudio\b|\bultrasonic',
 'thermal/IR imaging':r'\bthermal (camera|imag)|\binfrared camera|\bthermograph|\bpyrometer',
 'spectroscopy/colorimetry':r'\bspectromet|\bspectroscop|\bcolorimet|\bnear.infrared|\babsorbance',
 'impedance/electrical':r'\bimpedance|\bconductivity sensor|\bcapacitive|\bresistance measur',
 'vibration/accelerometer':r'\baccelerometer|\bvibration|\bgyroscope|\bimu\b',
 'radar/lidar':r'\bradar\b|\blidar\b|\btime.of.flight',
 'gas/chemical sensor':r'\bgas sensor|\bvoc\b|\bmq-?\d|\belectrochemical sensor|\bammonia sensor',
 'computer vision':r'\bcomputer vision|\bopencv|\bobject detection|\bimage classification|\bcnn\b|\bconvolutional',
 'ML/audio-signal':r'\bmachine learning|\bneural network|\bdeep learning|\brandom forest|\bsvm\b',
 'smartphone-as-instrument':r'\bsmartphone|\bandroid\b|\bios app|\bmobile app|\bphone camera',
 '3D printing/fabrication':r'\b3d.print|\blaser cut|\bcad\b',
 'citizen-science/crowd':r'\bcrowdsourc|\bcitizen science|\bcommunity data|\bsurvey',
 'simulation/modeling':r'\bsimulat|\bcomputational model|\bfinite element|\bmonte carlo',
 'microcontroller/IoT':r'\barduino|\braspberry pi|\besp32|\bmicrocontroller|\biot\b|\binternet of things',
 'long-term field logging':r'\bdata logger|\blong.term monitor|\bfield measurement|\bcontinuous monitor',
 'materials/chemistry':r'\bsynthes|\bnanoparticle|\bpolymer|\bhydrogel|\bcatalyst',
}
for k,v in {**D,**T}.items(): df[k]=df.t.str.contains(v,regex=True)
dm=pd.DataFrame({k:df[k] for k in D}); tm=pd.DataFrame({k:df[k] for k in T})
print("Domain totals:"); print(dm.sum().sort_values().to_string()); print("\nTechnique totals:"); print(tm.sum().sort_values().to_string())
rows=[]
for d in D:
    for t in T:
        n=int((df[d]&df[t]).sum()); rows.append((n,d,t,int(df[d].sum()),int(df[t].sum())))
mat=pd.DataFrame(rows,columns=['n','domain','tech','dtot','ttot'])
mat.to_csv('C:/UltraNiche/scripts/matrix.csv',index=False)
print("\nEMPTY or near-empty cells (n<=1) where both domain and technique are well represented:")
sel=mat[(mat.n<=1)&(mat.dtot>=80)&(mat.ttot>=100)].sort_values(['n','dtot'],ascending=[True,False])
print(sel.to_string(index=False))
