# ASSUMPTIONS (not verified): cell 2.5 Ah; OCV slope 5-10 mV per 1% SOC in mid-range; OCV temp coeff 0.1-0.5 mV/K
Ah=2.5
for slope in [5e-3, 10e-3]:          # V per 1% SOC
    dQdV = (0.01*Ah)/slope            # Ah per V
    print(f"slope {slope*1e3:.0f} mV/%SOC -> dQ/dV = {dQdV*1e3:.2f} mAh per mV = {dQdV*1e-3*1e3:.2f} uAh per uV")
    for I in [4e-6, 40e-6, 130e-6]:
        for t in [1, 2]:
            dV = I*t/dQdV
            print(f"   leak {I*1e6:6.1f} uA over {t} h -> OCV falls {dV*1e6:8.2f} uV")
    print(f"   hold-voltage error of 10 uV -> charge to move = {10e-6*dQdV*1e3*1e3:.1f} uAh (= {10e-6*dQdV*1e6/4:.1f} h of a 4 uA leak)")
print()
for tc in [0.1e-3, 0.5e-3]:
    print(f"temp coeff {tc*1e3:.1f} mV/K: 10 mK drift -> {tc*0.01*1e6:.1f} uV ;  1 mK -> {tc*0.001*1e6:.2f} uV")
