V=3.9; Ah=2.5; H=720
print("Known external leak resistor -> current, and equivalent self-discharge at 2.5 Ah, 30 days")
for R in [10e6,3e6,1e6,300e3,100e3,30e3]:
    I=V/R
    pct=I*H/Ah/1000*100  # I in A -> Ah over 720h ; I*H = Ah
    print(f"  R={R/1e3:>8.0f} kOhm  I={I*1e6:8.2f} uA  ~{I*H/Ah*100:6.2f} %/month")
print()
print("Healthy-cell figure from search summary: ~4.2 uA (3.5 Ah cell) -> %/month:", 4.2e-6*H/3.5*100)
print()
print("Shunt resistor vs current resolution if ADC noise were X uV rms (assumption, check datasheet)")
for Rs in [100,1e3,10e3,100e3]:
    for vn in [1,5]:
        print(f"  Rs={Rs:>8.0f} ohm, noise {vn} uV -> {vn*1e-6/Rs*1e6:8.4f} uA rms;  1 mA full-scale drops {Rs*1e-3:.2f} V; 100 uA drops {Rs*1e-4:.3f} V")
print()
print("Charge moved in 1 h by a 4 uA leak:", 4e-6*3600, "C =", 4e-6*1/Ah*100, "% of 2.5 Ah cell")
