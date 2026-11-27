# Design notes: what the physics says about a fast cell screen

Status: working notes, v1. Calculations are in `scripts\leak_table.py` and `scripts\ocv_sens.py`. **Every cell parameter below is an assumption I made, not a measured or sourced value.** I have not read the INL paper, so I don't know how it handles the issues in section 2. Items marked **[verify]** need a datasheet, a paper or a bench check.

## 1. Leak currents, in plain numbers

A cell held near 3.9 V with a known resistor across it leaks I = V/R. This gives a safe, known "fake short".

| External resistor | Leak current | About this much self-discharge (2.5 Ah, 30 days) |
|---|---|---|
| 10 MΩ | 0.39 µA | 0.01 % per month |
| 3 MΩ | 1.3 µA | 0.04 % |
| 1 MΩ | 3.9 µA | 0.11 % |
| 300 kΩ | 13 µA | 0.37 % |
| 100 kΩ | 39 µA | 1.1 % |
| 30 kΩ | 130 µA | 3.7 % |

A published 10-month study (found by search, not read) measured an average healthy-cell leak of about 4.2 µA on 3.5 Ah cells, roughly 0.09 % per month. That means **a 1 MΩ-equivalent leak is the same size as normal self-discharge**. Only leaks of roughly 100 kΩ-equivalent and below stand clearly apart from a healthy cell in absolute current.

**Reading the current is not the hard part.** With a 1 kΩ shunt and an ADC with 5 µV rms noise, current noise is about 5 nA. The hard part is next.

## 2. The real difficulty: microvolts

A cell is almost a perfect battery: tiny leak currents change its voltage by only microvolts, and it is sensitive to temperature.

Assumptions: 2.5 Ah cell, open-circuit voltage changes 5–10 mV per 1 % state of charge in mid-range, and its voltage drifts 0.1–0.5 mV per kelvin.

| Quantity | Result |
|---|---|
| Voltage fall from a healthy 4 µA leak in 1 h | about 0.8–1.6 µV |
| Voltage fall from a 40 µA leak in 1 h | about 8–16 µV |
| Voltage fall from a 130 µA leak in 1 h | about 26–52 µV |
| A 10 mK temperature drift | about 1–5 µV |
| A 10 µV error in a held voltage setpoint | moves 25–50 µAh, equal to about 6–12 h of a healthy 4 µA leak |

**What this means:**
- **Voltage-drift method** (watch open-circuit voltage fall over 1–2 h): signals are 1–100 µV. Needs a very stable ADC, thermally stable wiring and about 1 mK temperature stability.
- **Constant-voltage method** (hold the cell at a fixed voltage and read the current): a few-µV error in the setpoint swamps a healthy-cell leak for hours, so a precision, stable setpoint matters more than current resolution. **[verify]** how the INL paper sets and tracks that offset, because my estimate says a 1–1.5 h result at µA-level needs a very small, very stable offset.
- **So a cheap rig is likely to detect big leakers quickly (tens of µA and up) and healthy-vs-slightly-leaky only slowly or not at all.** That is an expectation from my arithmetic, not a result.

## 3. How this changes the project

The original question was "does a 1–2 hour screen predict 28-day decay?". The physics suggests a better, more answerable question:

> **What is the smallest leak a low-cost rig can detect, as a function of measurement time and temperature control, and does that match what salvaged cells actually need?**

This is a measurable relationship, so it fits a real hypothesis. Candidate hypotheses to choose from (the wording is yours):
- H-A: The minimum detectable leak current falls as measurement time rises, roughly as the voltage-noise floor divided by (time × a constant of the cell).
- H-B: Temperature drift is the dominant limit, and halving it halves the minimum detectable leak.
- H-C: Cells whose measured leak is high in 1–2 h are the same cells that leak most over 28 days (the original question), but only above a threshold set by H-A.

## 4. A cleaner three-stage design

**Stage 1: calibrate with known leaks (safe, fast).**
Use healthy cells, each with a known resistor in parallel (table above, resistors of 100 kΩ or more). The expected leak is known. Check that the rig measures I = V/R and find the detection limit. **No hazardous steps:** a 100 kΩ resistor draws under 40 µA.

**Stage 2: characterize the rig.**
Noise, drift, and detection limit versus measurement time (15 min, 1 h, 2 h) and with or without temperature control. Compare two methods on the same rig:
- Method A: voltage drift against a stable reference.
- Method B: constant-voltage hold current.

**Stage 3: apply to salvaged cells.**
Screen 30–40 salvaged cells, then log 28-day open-circuit voltage decay as the reference. Ask which cells the rig can and cannot separate, and report the false-negative rate.

Stages 1 and 2 give a clean, publishable result even if Stage 3 is unclear, and they are much safer than testing damaged cells.

## 5. Rig architecture to evaluate

**Common to both methods**
- 24-bit delta-sigma ADC, with the input kept differential. Candidates to check: ADS1256, ADS124S08, INA228-class parts **[verify datasheets]**.
- Precision low-drift voltage reference (examples to check: LTC6655, ADR4550, REF50xx families **[verify]**).
- Low-offset chopper op-amp for the hold loop (for example OPA2188-class **[verify]**).
- 4-wire (Kelvin) contacts to the cell so contact resistance does not matter, with cell holders that don't heat.
- Low-thermal-EMF connections: use the same metal (copper to copper), keep joints at equal temperature, and avoid dissimilar-metal junctions where possible. Thermal voltages on joints are themselves microvolt-sized.
- Insulated box with a large thermal mass, a calibrated thermistor in the box and one on the cell, logged all the time.
- PCB leakage: clean boards, guard rings around high-impedance nodes, dry air or silica gel. Surface leakage can mimic a micro-leak.
- Hardware safety: over-current, over-voltage and over-temperature cut-offs independent of firmware, and per-channel isolation.

**Method A, voltage drift:** high-resolution differential measurement of cell voltage against the reference, repeated and averaged. Simple hardware, but the hardest on temperature stability.

**Method B, constant-voltage hold:** reference → op-amp → cell through a sense resistor (1 kΩ to start, switchable for range), with the cell voltage sensed directly at the terminals. Better for ranking leakers, but it needs the stable setpoint described in section 2.

**Start with one channel. Don't scale until Stage 2 passes.**

## 6. Order of work

| Step | What | Done when |
|---|---|---|
| 0 | Supervising adult, safety setup, any hazard forms | Signed off |
| 1 | Read the INL paper and patent claims in full (US 10,036,779, Sazhin et al., JES 2017) | You can explain how it sets and tracks the offset |
| 2 | One-channel rig, test with a precision resistor in place of a cell | Reads V/R correctly, noise and drift logged |
| 3 | Stage 1: healthy cell plus known resistors | I vs 1/R plotted, detection limit stated |
| 4 | Stage 2: time and temperature sweep, Methods A and B | Detection-limit curve |
| 5 | Stage 3: 28-day reference on salvaged cells, then screens | Rank correlation and false-negative rate |
| 6 | Write-up, data and design release | Public release |

## 7. What I can help with now (without limits)

- Circuit schematics, op-amp loop stability and noise budget.
- Firmware for logging and filtering.
- Analysis code and plots (rank correlation, ROC, detection-limit fits).
- Drafting the hypothesis, methods and report.
- A parts list with checked datasheets once you choose a budget.

## 8. Key risks

| Risk | Why | Handling |
|---|---|---|
| My cell numbers are wrong | They are assumptions | Measure the real slope and temperature coefficient on your own cells early |
| Rig can't reach µV stability | Needs good reference, wiring and temperature | Stage 2 measures this directly; the result is itself the finding |
| Healthy vs slightly leaky can't be separated fast | Physics above | Report the detection limit honestly |
| Used-cell safety | Fire hazard | Resistor tests first; supervised; no damaged cells; no abuse tests |
| Prior art | INL method is patented | Cite it; position as a low-cost detection-limit study and open dataset |

## 9. Questions for you
1. What's your budget and what bench gear do you already have (multimeter? scope? anything better)? Can you borrow a precision meter or source-measure unit?
2. What electronics experience do you have? This sets how much of the analog design I explain and how much I draft.
3. Who is supervising?
