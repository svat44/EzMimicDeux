# Plan: can cheap ultrasound sensing tell you when a plant needs water?

Status: draft v1. I read the full text of both key papers this time (Khait et al. 2023, Cell; Bonisoli, Pelicella & Arru 2024, Plant Signaling & Behavior). Items marked **[verify]** are things I could not confirm. Hardware and price details are not verified.

## 1. The idea in plain words
Plants under water stress make tiny clicks at pitches too high for humans to hear (about 20–150 kHz). A 2023 study showed this with tomato and tobacco. Nobody I found has shown whether a **cheap setup** can pick up those clicks reliably in an **ordinary room**, or whether the click pattern could tell you "water now". This project tests that, using potted plants and a dry-down experiment.

## 2. What the two papers actually established

**Khait et al. 2023 (Cell)** — research-grade setup
- Microphones: Avisoft CM16 condenser ultrasound mics (response roughly flat 10–120 kHz), digitised by an Avisoft UltraSoundGate 1216H at **500 kHz per channel**, 20 kHz high-pass filter.
- Room: a 50 × 100 × 150 cm **acoustic box** in a quiet basement, walls blocking at least 100 dB of outside sound in the relevant band.
- Two directional microphones aimed at each plant stem from **10 cm**. A sound only counted as a plant sound if **both** mics recorded it, which removed electrical noise from a single channel.
- Triggered recording: a 1.5 s clip saved whenever a sound exceeded 2 % of the mic's dynamic range.
- Drought: water withheld **4–6 days**; soil moisture checked with a hand-held meter.
- Results: drought-stressed tomato about **35 sounds per hour**, tobacco about 11; cut tomato about 25, cut tobacco about 15; **controls under 1 per hour**. Peak frequency around 50–58 kHz. Estimated emitted level about 65 dB SPL at 10 cm (the authors say this is a lower bound).
- Greenhouse: 23 tomato plants recorded for nine days without water. The click rate **rose over the first 4–5 days and then fell**, so it is not a simple "more clicks = drier" signal. A neural network separated drought sounds from greenhouse noise, and drought from control plants at roughly 84 %.
- Correction to something I said earlier: the "3–5 m" figure is a calculation of how far away **animals** such as moths could hear the clicks, not how far a microphone detected them.

**Bonisoli et al. 2024** — "low-cost"
- One commercial USB ultrasound mic (Dodotronic Ultramic 384K BLE, 384 kHz, 16-bit), a laptop and Audacity. I don't know its price **[verify]**.
- Eight **well-watered** pinto bean plants, mic 1–2 cm from the stem, quiet lab room, 18 sessions of 30 minutes. **They did not test drought.**
- Raw counts were mostly noise: about 13 per 30 min for plants but about 10 per 30 min for empty rooms and plain soil. After removing audible-sound overlaps, single-sample spikes, spikes with fewer than 3 oscillations, duplicates and a family of very short 60–100 kHz peaks, plants averaged **2.3 per 30 min** and controls **0** (Kruskal–Wallis p = 0.0085; only 6 sessions per group).
- Lesson: **noise rejection, not microphone cost alone, is the hard part.** Their filtering rules were built by looking at the controls, so a fresh dataset is needed to check them.

## 3. The gap (what I did not find)
1. No independent replication of the drought-click result with different, cheaper hardware.
2. No study using a **cheap, two-microphone coincidence detector** (Khait's key noise filter) in an ordinary room.
3. No study that pairs click rate with a **continuous soil-water reference** over a dry-down to ask: can click rate act as a "water now" signal given that it rises and then falls?
4. No field-style test of whether clicks would improve a watering decision over a soil moisture sensor alone. (A patent-style source claimed 20–40 % water savings; I don't trust it.)

I searched with standard web searches only, so I can't rule out unpublished or unfound work.

## 4. Questions and hypotheses (you pick and word your own)
- **H1 (replication):** Dry-down tomato plants produce more coincident ultrasonic clicks than well-watered plants in the same room.
- **H2 (shape):** Click rate versus soil water content is hump-shaped, not rising steadily, so a single threshold would mislead.
- **H3 (decision rule):** There is a window of soil water content in which click rate gives earlier warning of wilting than soil moisture alone.
- **H4 (hardware):** Two-channel coincidence detection gives a lower false-positive rate than single-mic thresholding with the same hardware.

## 5. Design

**Plants**
- Tomato (the species with the strongest published signal). Optionally a second species such as pinto bean, matching the 2024 paper.
- At least **8 dry-down and 8 well-watered** plants of the same age, same pots, same soil. This is a minimum I picked to match the scale of the published studies, not a power calculation **[verify with a power estimate]**.
- Controls: 4 pots of soil with no plant, and empty-box recordings.

**Reference measurements for every plant, every day**
- Pot weight on a kitchen scale (gravimetric water loss), plus a cheap capacitive soil moisture probe.
- A wilting score from a dated photo.
- Room temperature and humidity logged continuously.

**Procedure**
1. Water everything to saturation. Record a baseline day.
2. Dry-down group: withhold water; control group: keep watering. Record continuously or by trigger.
3. Rewater each plant when it shows clear wilting, and record recovery. The aim is stress, not killing plants.
4. Keep the recording location, timing and plant positions fixed, and randomise which plants are in which group.

**Recording environment**
- A sealed box lined with foam, away from any electronics. Phone and Wi-Fi off. No fans, chargers or LED drivers inside, because they make ultrasound. Run the recorder on battery if possible.
- Mic distance about 10 cm from the stem, aimed at the stem with a clear line of sight (this matches the published setup).

**Positive control:** a cut tomato stem, which Khait found makes about 25 clicks per hour. If your setup can't see that, it can't see drought clicks.

**Negative controls:** empty box, soil-only pots, and a mic with a sealed cap (electronic noise only).

## 6. Hardware plan (build in two stages)
**Stage A — answer the science first.** Use a purchased or borrowed ultrasonic recorder with at least 250–384 kHz sampling (the 2024 paper used a Dodotronic Ultramic 384K BLE; open-source acoustic loggers such as the AudioMoth may also work **[verify sensitivity at 10 cm for ~65 dB SPL clicks]**). Libraries, universities and bat-survey groups sometimes lend such gear. Use two units if you can, to test coincidence.

**Stage B — the cheap-hardware question (H4).** Two analog MEMS ultrasonic mics (for example the Knowles SPU0410LR5H, reported flat to about 80 kHz **[verify]**), analog amplification and anti-alias filtering, and a microcontroller ADC sampling at 250 kS/s per channel or more (RP2040 and Teensy are candidates **[verify ADC speed, noise and whether two channels can be sampled fast enough]**). Open-source bat-detector projects are a starting point. This is new engineering, with real risk, and should only start after Stage A works.

## 7. Gates and kill criteria
| Gate | When | Pass if | If it fails |
|---|---|---|---|
| G0 bench test | Weeks 1–2 | A known ultrasound source (a pencil-lead break or a small 40 kHz transducer) is detected at 10 cm, and the two channels agree on timing | Fix the front end or switch to a better recorder |
| G1 noise | Week 3 | Empty-box coincident false events under about 1 per hour | Improve shielding; remove electronics; add filtering rules written **before** looking at plants |
| G2 positive control | Week 3–4 | Cut tomato stems give clearly more coincident clicks than the empty box, in at least 2 of 3 plants | Try a better mic or distance. If still nothing, report "this hardware can't see it" as a finding, and move to a borrowed recorder |
| G3 dry-down | Weeks 4–10 | Dry-down plants differ from controls | Report the null honestly |

## 8. Analysis plan
Fix all counting rules **before** unblinding: band, threshold, coincidence window, artifact rules. Count coincident clicks per plant per hour. Compare dry-down and control with rank tests and confidence intervals. Plot clicks per hour against relative soil water content and against days since watering to test the hump (H2). Estimate how many days before visible wilting the click rate first leaves the control range (H3). I can write the analysis code and plots for you. Be wary of tuning the filter on the same data you then test (the 2024 paper's filters came from its own controls).

## 9. Timeline (about 12 weeks)
| Weeks | Work |
|---|---|
| This week | Buy 20–25 tomato seedlings and start growing. This is the longest lead time. Decide the recorder route. |
| 1–2 | Bench tests (G0), build the recording box |
| 3–4 | Noise and cut-stem tests (G1, G2); fix the analysis rules in writing |
| 5–9 | Dry-down experiment with daily reference measurements |
| 10 | Unblind and analyse |
| 11–12 | Stage B electronics (optional), write-up, data release |

## 10. Safety and approvals
Low risk. Low-voltage electronics, plants and soil. Use normal care with any mains-powered grow light and wet pots near electronics. No hazardous chemicals. No animals. Check your fair's rules if you enter one (plants are usually unregulated, but forms still apply).

## 11. Risks
| Risk | Why | Handling |
|---|---|---|
| No clicks seen | The effect may be small or hardware too noisy | Gates G1/G2; a null result is still a result |
| Noise looks like clicks | Electronics, HVAC, pest repellers | Sealed box, battery power, two-channel coincidence, controls |
| Click rate not usable for decisions | Hump shape; plant-to-plant variation | This is H2/H3, and it is the finding |
| One group's result may not replicate | I found no independent replication | Report either way |
| Hardware cost and availability | Unknown prices | Borrow first; check prices before buying |
| Not world-unique | Searches were limited | Cite both papers; claim only replication, cheaper hardware and the decision-window analysis |

## 12. Outputs
Open dataset (raw clips, counts, reference measurements, temperature and humidity), recording-box build notes, analysis code, and a short report. If Stage B works, an open two-mic design.

## 13. Decisions I need from you
1. **Can you start growing tomato seedlings now** (a sunny window or a grow light)? This sets the whole schedule.
2. Budget and gear: can you borrow an ultrasonic recorder, or must you buy? I should price the options first.
3. Who is helping (an adult, a teacher, a university contact)? Not required for safety here, but useful for lending equipment and sanity-checking your results.

---

## 14. Student-journal track (added 2026-11-23)

**Status of the checks:** JEI details come from an earlier read of its site (see `jei_track_plan.md`). The Journal of Student Research High School Edition (JSR) site was down (HTTP 522) when I tried, so **I have no verified JSR rules** beyond one search summary: first author must be a high school student at an accredited school, a teacher or advisor guides submission, rolling submissions. Recheck JSR when it is back up: fees, review process, AI policy, scope, preprint and data-sharing rules.

**Which journal depends on one choice: who writes the paper.**
- **JEI** bans AI help with writing text, statistics, figures and literature summaries. If you want me to draft and analyse, JEI is out for this manuscript.
- **JSR** AI policy: unknown. Ask before you rely on it.

**What each journal needs from the project**
- **JEI scope:** hypothesis-driven natural science only. H1–H3 (dry-down vs control, hump shape, decision window) fit. **H4 (cheap hardware vs single mic) is a method comparison and would be out of scope, so keep it out of the JEI paper** and publish the hardware separately as an open design.
- Both: an adult mentor or teacher, a clear hypothesis written before data collection, honest reporting of null results, enough method detail to repeat.

**Changes to the plan for a journal**
1. Write one primary hypothesis (H1) and label H2/H3 secondary, in your own words, before the dry-down starts. Post it publicly (for example on OSF).
2. Fix counting rules (band, threshold, coincidence window, artifact rules) in writing before unblinding.
3. Keep a lab-notebook-style log: dates, plant IDs, readings, any deviations.
4. Keep all raw data and photos. Journals may ask.
5. Keep Stage B hardware as a separate open release, not part of the journal paper.

**Order of work**
1. Choose the journal and confirm its current rules.
2. Line up the adult mentor or teacher (needed by both).
3. Start the tomato seedlings, run the gates, then the dry-down.
4. Write, get mentor review, submit.

---

## 15. Correction (2026-11-23): prior art is bigger than section 3 says

A pasted answer from another tool, plus my own check of its sources, found work I missed. I have **not read these papers in full** (ScienceDirect was not readable), so details are from search summaries.

- **Contact acoustic-emission (AE) irrigation control on tomato is established.** Simbeye et al. 2023, *Smart Agricultural Technology*, "Plant water stress monitoring and control system": real-time AE detection from potted tomatoes with a precision-irrigation model, using sensors fixed to the stem. Earlier work: Kageyama and colleagues (2002 onward), AE-based deficit irrigation of miniature tomato (2013), and a note that AE signals were not sufficient for calculation at all times in cherry tomato (2016). An ASABE paper cited by the other tool was not found in my search.
- **Airborne, non-contact detection with water stress has also been tested.** Bonisoli, Forti & Arru 2025, *Physiologia* 5(1):9, "Outdoor Detection of Plant Ultrasonic Emissions Using a Contactless Microphone": pinto bean and tomato under water stress, indoors and outdoors, 30-minute sessions in four bands (20–100 kHz), reporting detection despite wind, rain and insect noise. This weakens my earlier statements that the 2024 low-cost method had never been tried on stressed plants, and that no one had used a contactless mic with water stress.

**What is probably still open (unverified):** a closed-loop, non-contact, low-cost system that waters a plant when airborne clicks cross a threshold, compared head-to-head against a soil-moisture controller. The other tool's framing is a fair one: the gap is a low-cost home build's effectiveness and comparison, not whether anyone has linked tomato sounds to irrigation.

**Honest effect on novelty:** lower than I said. The project is now a practical re-implementation plus a comparison, not a new discovery. Before claiming any gap, read Simbeye 2023 and Bonisoli 2025 in full.
