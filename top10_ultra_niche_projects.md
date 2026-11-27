# Top 10 ultra-niche research projects (gap analysis of ISEF 2014–2024)

## How this was done (and its limits)

- **Dataset:** `williamkaiser/all-isef-projects`, 14,911 projects, 2014–2024. 11,767 have usable abstracts. Only titles and abstracts are in the data, not posters or papers.
- **I did not hand-read all 14,911 abstracts.** I processed all of them programmatically: TF-IDF topic clustering (120 clusters), keyword-density probes on about 80 themes, and nearest-neighbour similarity of about 20 candidate ideas against every abstract. I then read the closest ISEF neighbours of each finalist in full. Scripts are in `C:\UltraNiche\scripts\`.
- **Result of the density check:** every finalist's closest ISEF match scored cosine similarity 0.13–0.21, which is very low. The crowded areas are water filters, solar, ML classifiers for cancer, drones, bioplastics and "device for the visually impaired". The sparse areas are measuring and verifying the consumer devices and home environments people already depend on.
- **Literature checks** were web searches read at abstract and press level, not full papers. Treat "no study found" as "I did not find one", not as proof none exists. One search (home leftover-cooling safety) was blocked by the tool, so that idea was dropped unevaluated.
- **Common thread of the ten:** each audits or validates something people already trust (a device, a home, a sensor) using a rig built at home for under about US$150. None needs wet-lab biology or hazardous material.

---

## 1. Skin-tone phantom test bench for over-the-counter "wellness" pulse oximeters
- **Gap:** FDA's January 2025 draft guidance on skin-pigmentation bias covers medical-use oximeters. It explicitly excludes general-wellness devices, which are the ones sold in pharmacies. An independent study of 34 oximeters found only 1 passed the anticipated criteria. It used human desaturation cohorts, which are expensive and not repeatable at home.
- **ISEF neighbours:** 10 projects mention oximetry and they are all *using* one as a sensor (for example the 2024 fall-detector, the 2021 snow-shovel glove). None audits oximeter accuracy. 8 abstracts mention skin tone, all about melanoma classifiers.
- **Project:** Build a pulsatile optical phantom set (silicone layers pigmented to match Monk Skin Tone swatches, spectrophotometer-verified, with a variable-absorbance "blood" channel). Run 10–20 consumer oximeters across the tone range and report each device's bias as a function of tone and simulated SpO2. Publish the phantom recipe so any school can repeat the audit.
- **Home-demonstrable:** Yes. No human subjects. Devices cost $15–30 each.
- **Honest risk:** A phantom cannot give true clinical accuracy. Validate it by checking that it reproduces the *direction and rough size* of bias already published in human studies, and claim only relative bias.

## 2. Open-source 3D-printed ear simulator that turns any earbud's volume into real eardrum dose
- **Gap:** Phone health apps estimate listening exposure from output level and assumed earbud response. Published work notes that the sound reaching the eardrum depends on the earbud's frequency response and fit, and Apple itself says its estimates vary. I found no published error figure for consumer earbuds.
- **ISEF neighbours:** 2020 "Ear Canal Shape and Its Impact on Sound Transmission" (3D-printed ears, speaker, one probe). 2021 "Over-the-Head Listening Devices and NIHL" (a model ear, a decibel meter). Neither tested real earbuds, neither converted a measurement into a daily dose, and neither compared against a standard coupler.
- **Project:** Print an ear-canal coupler with a calibrated MEMS microphone. Measure the frequency response of 30–50 earbuds. Compute a per-model correction from "phone volume" to dB(A) at the eardrum and the resulting WHO-style daily dose. Release the table as an open dataset and a small app.
- **Fairness requirement:** Check the printed coupler once against a real IEC-style coupler at a university or audiology clinic.
- **Fit:** Direct relevance to Galaxy Buds-type devices (inference on my part, not a Samsung claim).

## 3. Indoor wet-bulb sensor network and "should I use a fan?" guidance for older adults' homes
- **Gap:** The recent heat research is chamber trials with small groups: fans do not lower core temperature at >33–35 °C in dry heat, and indoor temperatures stay high overnight. I found no study using low-cost sensors to measure indoor wet-bulb in real older adults' homes.
- **ISEF neighbours:** Essentially none. Only one 2022 abstract mentions heat index at all, and it is a handheld weather gadget. The rest of the wet-bulb or heat-wave hits are plant science.
- **Project:** A $12-per-node temperature and humidity logger (SHT4x plus microcontroller). Deploy in 15–30 volunteer homes during heat events. Fit an indoor-versus-outdoor lag and humidity model. Output a simple colour-coded indoor risk indicator and fan or no-fan advice tied to published thresholds.
- **Real-world impact:** Indoor heat deaths among older adults.
- **Honest risk:** Homes of volunteers involve human-subjects and privacy review. Start with your own and relatives' homes plus public weather data.

## 4. "Thermal exposure in the wild" for emergency medications (auto-injectors, inhalers, insulin pens)
- **Gap:** Heat degrades epinephrine, and the label is 20–25 °C. Evidence is lab or small-pilot, and the systematic review called for more real-world temperature data. Nobody has a large dataset of where people actually keep these devices and what temperatures result.
- **ISEF neighbours:** 8 auto-injector projects, all about locators, QR bracelets, trainer devices or nasal delivery (2017 Epi-Phone, 2017–18 "Anaphylactic Shocker"). One inhaler project (a nebulizer). None measured storage temperature.
- **Project:** Pocket-sized loggers placed in cars, backpacks, purses and glove boxes, with a trainer or dummy device so no real medication is involved. Crowdsource across climates, compute a "label-excursion hours" score per storage location, and publish evidence-based storage advice.
- **Safety:** No drug, no human test, no medical claims.

## 5. Smoke-alarm audibility atlas: frequency-resolved closed-door and wall transmission
- **Gap:** Research shows a 520 Hz square wave wakes hearing-impaired adults and children far better than the standard ~3.1 kHz tone, and CPSC measured weak alarm levels through closed doors. I found no study reporting door and wall transmission loss for 520 Hz versus 3.1 kHz.
- **ISEF neighbours:** Only the 2019 "Tru-Alert" (steam/nuisance-alarm reduction with a humidity sensor). Nothing on whether the alarm reaches a sleeper.
- **Project:** Measure transmission loss of real doors and walls in many homes with a calibrated source and phone microphone at both alarm types. Combine with published waking thresholds to predict whether a given bedroom gets enough alarm level. Ship a free "bedroom audibility check" protocol.
- **Safety:** No fire, no sleeping subjects. Claim only what the published waking data supports.

## 6. Airborne microfibre emissions by dryer type (vented, condenser, heat-pump), with a repeatable test protocol
- **Gap:** Airborne emissions are measured on very few dryer models, heat-pump and condenser units are barely covered, and a 2025 study calls for standardised test methods.
- **ISEF neighbours:** 2021 "A Comparison of Domestic Dryer Contributions…" captured fibres in a water bucket from the vent. 2023 MiPlaFi 2.0 is a washing-machine filter. Neither measured size-resolved airborne release or compared dryer types.
- **Project:** Low-cost optical particle counters plus a sealed capture duct on household dryers (borrowed from friends and family), with a documented, repeatable protocol and fabric loads.
- **Lower novelty than the top five**, but a clear measurement-standards gap.

## 7. Phone-based thickened-liquid consistency checker for dysphagia care
- **Gap:** The IDDSI syringe flow test is described as fiddly in care homes, and it is sensitive to temperature, bubbles and syringe tolerance. Caregiver errors in thickness are linked to choking events. I found no validated smartphone approach.
- **ISEF neighbours:** Essentially none (the hits for "thickened" are cardiology and shear-thickening armour).
- **Project:** Video of a standard syringe drain, with automatic timing, bubble and temperature compensation, and a pass/fail category. Validate against a borrowed rotational viscometer using xanthan-thickened kitchen liquids. No human swallowing, no patients.

## 8. Kitchen microplastic source audit using smartphone Nile-red fluorescence
- **Gap:** A 2023 study put chopping-board microplastics in the tens of millions of particles a year, and a smartphone Nile-red method exists in a thesis, but I found no cross-validated, low-cost audit across many kitchen items.
- **ISEF neighbours:** Many microplastic projects exist but are about water filters or beaches. The nearest abstract is about synthesising Nile red dye.
- **Project:** Blue-LED and filter rig plus phone camera. Rank cutting boards, scouring pads, kettles, tea bags and bottles by release.
- **Fairness requirement:** Validate a subset with FTIR at a partner university.

## 9. Cooking-aerosol-aware correction for low-cost PM2.5 sensors
- **Gap:** Low-cost sensors are known to read 50–200% of true PM2.5 for frying and grilling and to over-read at high humidity. I found no study of how kitchen steam and cooking aerosol interact in one correction.
- **ISEF neighbours:** Generic IoT air-quality monitors (2014, 2022). None looked at cooking or humidity.
- **Project:** Co-locate several cheap sensors with a filter-based reference, run standardised cooking tasks, and fit a humidity-plus-source model.
- **Needs a reference:** Borrow a reference monitor or run gravimetric filters.

## 10. Privacy-preserving crosswalk-timing audit against observed slow walkers
- **Gap:** Large studies show older adults average about 0.77 m/s, which is below the 1.2 m/s signal assumption, but they use short walking tests. Observed-crossing studies use older manual video methods.
- **ISEF neighbour:** 2020 "Tomorrow's Crosswalk" warns pedestrians of speeding cars. It does not audit crossing time.
- **Project:** On-device computer vision that records only speeds and signal phases (no faces or video stored) across neighbourhood crossings, producing a public timing audit.
- **Ethics:** Public-space video needs a clear privacy design and permission.

---

## Close runners-up
- Eye-drop bottle squeeze-force and dose accuracy for arthritic users (literature already fairly strong).
- Bedroom CO₂ with closed doors (Danish field studies and a 2025 IoT study already exist).
- Open-source bathroom slip tester (a 2022 low-cost tester exists, but nothing validated for bathrooms).
- Smartphone UV imaging for sunscreen coverage (coverage gaps are known, thickness cannot be measured).

## Suggested next step
For Samsung Solve for Tomorrow, my picks are **#2 (earbud dose)** and **#1 (oximeter phantom)**. They have the cleanest "no one has done this" story, tie closely to wearables, and are demonstrable at a kitchen table. #3 has the strongest real-world impact but needs the most human-subjects care.

---

## Revision after review: audits vs real gaps

Feedback: #1 and #2 as written are measurement audits and calibration tables, not inventions. That is right. Re-screened, most of the ten are audits. Only the versions below have an invention core, meaning a new mechanism that fixes the underlying problem and can be benchmarked.

| Original | Invention version | Literature check |
|---|---|---|
| #1 oximeter audit | Geometry-aware, multi-wavelength SpO2 estimator that compensates for skin pigmentation, tested on the phantom bench | Multi-wavelength and regression corrections exist but lack validation across skin tones. A Monte Carlo study says path-length differences mean a single melanin correction is not enough. Treat as unsolved, but a crowded academic area. |
| #5 smoke-alarm atlas | Closed-loop alarm that plays a test sweep, listens at the bedside, computes the real transmission loss and adapts or flags the room | I found only speaker self-tests (Nest, a 2016 patent) and CPSC audibility measurements. No bedside-verified adaptive alarm found. |
| #2 earbud table | Microphone-free in-ear dose estimate from the driver's electrical impedance | Described in patents, with no peer-reviewed accuracy figures found. Real if you build and validate it openly. Patents mean novelty must be claimed carefully. |
| #6 dryer audit | Lint-filter redesign that optimises capture against airflow resistance | Commercial filters capture 35–80%, and a capture versus resistance trade-off is documented. A design-optimisation project. |
| #7 thickened-liquid checker | (Downgraded) | Phone-vibration viscometry already exists (Vi-Liquid, MobiCom 2021). Only the dysphagia-specific temperature and bubble handling remains. |

#3, #4, #8, #9 and #10 stay datasets or audits unless a method component is added.

Caveat: the checks were standard web searches, not patent or Scholar prior-art searches. Run a full prior-art search on the finalists before committing.

---

## Second pass: real-gap shortlist (invention cores only)

Method: instead of ranking by ISEF sparsity alone, I looked for problems that recent reviews, benchmarks or standards bodies describe as open, checked that ISEF has essentially nothing on them, and kept only projects where you build a new method or device and benchmark it. Checks were standard web searches, not patent or Scholar prior-art searches.

| Rank | Project | Named gap in the literature | ISEF coverage | Home-demonstrable |
|---|---|---|---|---|
| 1 | **1-hour safety screen for used lithium cells** (predict 28-day self-discharge and internal-short risk from a short constant-voltage and rest test) | A 2025 review says rapid screening is temperature- and protocol-sensitive. A 2025 thermal-safety review says capacity-screened cells can still be unstable. Standard open-circuit-voltage detection takes 7–28 days. INL's constant-voltage method was validated only on single cells, and I found no cost or throughput figures for a cheap rig. | About 0 (no second-life or short-detection projects) | Yes, with supervision. Voltage-limited measurement only. Reference = 28-day voltage decay. No abuse testing. |
| 2 | **Closed-loop smoke alarm** (listens at the bedside, measures real transmission loss, adapts or flags) | Only speaker self-tests found (Nest, a 2016 patent). CPSC shows about 20 dBA loss per floor and weak closed-door levels. No pillow-verified adaptive alarm found. | 1 nuisance-alarm project | Yes. Microcontroller, mic, speaker. No fire, no sleepers needed. |
| 3 | **Under-$100 cotton/polyester blend quantifier** (multispectral chip, calibrated on thrift garments) | A 2025 study says NIR blend quantification still needs refinement. Automated textile sorting is not established. The AS7265x-class chip has not been tested for this. NIST now has a public NIR reference dataset to validate against. | About 0 | Yes. Needs labelled garments and a coarse-band feasibility test, so a negative result is still publishable. |
| 4 | **Skin-tone-invariant, path-length-aware oximeter** + phantom bench | Multi-wavelength and regression corrections exist but are unvalidated across skin tones. Simulation says one melanin term is insufficient. | About 0 on correction | Yes (phantom). Crowded academically. |
| 5 | **Heat-aware fan governor** (cuts or warns when a fan would add heat strain) | A 2025 MJA paper gives simple cutoffs (39/38/37 °C by age and medication, humidity-dependent). I found no controller or prototype. | About 0 | Yes. Sensor plus smart-plug logic, tested against logged indoor conditions. A translation project more than a discovery. |
| 6 | **Microphone-free earbud dose** (driver impedance) | In patents, no peer-reviewed accuracy. | Ear-model projects only | Yes, with wired earbuds and an audio interface. |
| 7 | **Dryer lint filter with capture vs airflow optimised** | Capture of 35–80% for commercial filters, with a documented resistance trade-off. | 2 dryer or filter projects | Yes. |
| 8 | **Kinetics-matched thermal-dose indicator for emergency medicines** | Vendor indicators exist for vaccines and pens. I found no epinephrine-specific consumer version. Vendor claims only. | About 0 | Partly. Chemistry and logger only, no drug. |
| 9 | **Hidden-leak acoustic detection for slab and multifamily plumbing** | Fixture-sound matching and clamp-on classifiers exist. I found nothing on slab or multifamily. | About 0 | Hard without building access. |

**Real gap but not suitable for home:** wearable core-temperature estimation for older adults. A 2026 benchmark shows no method wins consistently and older adults are missing from the evidence, but it needs human subjects.

**My recommendation:** #1 or #2. They have the strongest "named gap, nothing in ISEF, new method you can benchmark" case. #2 is the safest to build. #1 has the larger impact (e-waste, off-grid storage, battery fires) and needs adult supervision and a fireproof container.
