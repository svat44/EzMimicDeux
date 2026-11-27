# Prior-art check: used-cell safety screen and closed-loop smoke alarm

Scope and limits: 10 web searches (3 in extended mode) across papers, patents and standards. I read search summaries and snippets, not full patent claims or full papers. **Before you claim novelty in a write-up, read the claims of the patents named below on Google Patents.** "I found none" means none surfaced in these searches.

## Verdict

| Project | Method novelty | Where the gap really is | Status |
|---|---|---|---|
| Used-cell safety screen | **Mostly taken.** Fast (minutes to hours) self-discharge and short detection is published and patented. | Head-to-head benchmark on *salvaged* cells, open low-cost hardware, and a public dataset. | Survives, but as a validation + open-hardware + dataset project, not a new method. |
| Closed-loop alarm | **Not found as a whole**, but adaptive-volume and bedside-listening patents exist around it. | A low-cost node that verifies the pillow-level criterion in real homes, plus measured 520 Hz vs 3.1 kHz door and wall loss. | Survives with a narrower claim. Cleaner novelty and safer to build. |

My recommendation is now to **lead with the alarm** and treat the cell screen as the second choice. Both are narrower than I first presented.

---

## 1. Used-cell safety screen

### What already exists (so you cannot claim it)
- **INL constant-voltage method:** hold the cell slightly below open-circuit voltage and read the current. It separates short severities in about 1–1.5 h, and it is patented ([US 10,036,779](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10036779); [Sazhin, Dufek, Gering, JES 2017](https://iopscience.iop.org/article/10.1149/2.0431701jes)). It was validated on single 18650s with *artificial external* shorts. I found no error bounds or false-positive rates in the abstracts.
- **Other fast self-discharge methods:** a pulse technique reported about 60x faster than a 30-day test ([2014](https://www.sciencedirect.com/science/article/abs/pii/S0378775314017820)); a 2020 classification method that ranks cells within about 2 h ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0378775320313367)); an equivalent-resistance model method ([ResearchGate](https://www.researchgate.net/publication/370624213_A_Novel_Measurement_Method_for_the_Self-Discharge_of_Lithium-Ion_Cells_Employing_an_Equivalent_Resistance_Model)); Keysight's commercial analyzer claiming about 15 min to under 1 h (vendor claim).
- **Sorting by self-discharge:** a patent for sorting factory-fresh cells in parallel ([US 12,113,179](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12113179)) and relaxation-voltage ML work on aging ([arXiv 2404.12769](https://arxiv.org/pdf/2404.12769v1.pdf)). UL 1974 already includes a self-discharge section for repurposed cells.
- **Open DIY testers** measure capacity and internal resistance of salvaged 18650s ([Open Green Energy tester](https://hackaday.io/project/201803-smart-multipurpose-battery-tester), [others](https://github.com/ArminJo/Ultimate-Battery-Tester)). None I found does self-discharge.

### What I did not find (the open gaps)
1. **No head-to-head comparison** of the fast methods against each other or against a 28-day reference. The search summary says the sources use different references and conditions.
2. **Used and salvaged cells.** The prior work is on fresh or lab cells. Han et al. (Energies, vol. 16, 2022) found 18650s recycled from the field can show an end-of-charge temperature rise (ECTR) from a self-terminating internal lithium short, with low coulombic efficiency, and concluded that capacity or resistance alone should not decide state of health ([paper](https://mdpi.com/1996-1073/16/1/405)). *(Corrected: an earlier version of this file called it a 2024 study and linked the wrong paper.)*
3. **Natural shorts.** INL validation used artificial external shorts, not shorts that formed in the field.
4. **No open dataset** pairing short-test readings with long self-discharge for second-life cells.
5. **No open, low-cost multichannel hardware** that does it.

### Suggested narrowed claim
"The first open, low-cost multichannel rig and public dataset that benchmarks minutes-scale self-discharge screens against 28-day voltage decay on salvaged 18650 cells, and tests whether any of them flag the late-charge thermal signature that capacity and resistance miss."

### Feasibility check (corrected)
My first estimate (about 0.1 mA at 3%/month) was too loose for healthy cells. A published 10-month study of 24 commercial 18650s measured an *average self-discharge current of 4.2 µA* (3.5 Ah cells, 70% SOC, 25 °C), with about 10% relative variance ([search summary](https://www.electronicdesign.com/technologies/test-measurement/article/21808344/keysight-technologies-measure-self-discharge-using-ocv-on-lithium-ion-cells) for Keysight's OCV note; the 4.2 µA study was surfaced via search and I did not read it). To rank healthy cells the rig needs roughly **0.2–0.5 µA resolution**, not 1–5 µA. Resolving shorted cells (tens of µA and up) is easier. This resolution is the main engineering risk, so test it first.

### First experiments and kill criteria
- Build one channel, then validate it against a bench source-measure unit (borrow one) on 5 known cells.
- **Kill or downgrade if** the rig's current noise is above about 0.5 µA RMS, or if the short test's rank order does not match the 28-day decay rank order (Spearman below about 0.7) on 30+ cells. (Thresholds tightened after the feasibility correction above.)

### Safety
Used cells are a fire hazard. Fireproof container, adult supervision, voltage-limited measurement, no charging of swollen, dented or hot cells, no abuse testing. Check your fair's hazardous-device rules.

### Patent note
The INL method is patented. A school research project that cites it and benchmarks it is normal, but say so plainly and do not present the constant-voltage method as your invention.

---

## 2. Closed-loop smoke alarm / pillow-level audibility verifier

### What already exists (so you cannot claim it)
- **Standards:** NFPA 72 sets a sleeping-area minimum of 75 dBA at the pillow, or 15 dB above average ambient, or 5 dB above the maximum sound lasting at least 60 s, whichever is greater, with a 520 Hz low-frequency signal where required ([NFPA 2024 submittal](https://docinfofiles.nfpa.org/files/AboutTheCodes/72/72_A2024_SIG_HOU_SD_pcsubmittals.pdf)). The 520 Hz rule applies to fire-alarm-system sleeping rooms, not generally to single-station home alarms.
- **Alarm-listening bedside units:** patents for devices that detect an alarm and wake the user ([US 7,522,035](https://patents.google.com/patent/US7522035B2/en) and family). They detect that an alarm is sounding; they do not measure how audible it is.
- **Adaptive audibility:** [EP 2787746 A1](https://patents.google.com/patent/EP2787746A1/en) measures background noise and uses a perceptual loudness model to set speaker level for a target sound such as an alarm. This is the nearest patent to your idea. Read its claims first.
- **Hub and smart-speaker patents** that raise alarm volume for the farthest occupant or for ambient noise ([US 9,692,380](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9692380), [US 10,674,260](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10674260)). I found nothing on closed doors.
- **Self-test:** Nest Protect and a 2016 patent use a built-in microphone for speaker self-tests of under 5 seconds. They check the speaker works, not that a bedroom is covered ([Nest](https://support.google.com/googlenest/answer/9250972)).
- **Audibility measurements:** CPSC measured real homes, with roughly 11–22 dBA lost through closed bedroom doors and about 20 dBA per floor ([CPSC 2005](https://www.cpsc.gov/s3fs-public/audibility%20(1).pdf)). A Canadian model says higher-frequency alarms (2–5 kHz) are attenuated more ([JCAA](https://jcaa.caa-aca.ca/index.php/jcaa/article/download/604/299/689)). Waking effectiveness of 520 Hz is established ([Bruck & Thomas 2009](https://www.audiologyonline.com/releases/smoke-alarms-and-hearing-loss-3332)).
- **Efficient 520 Hz sounder design** is patented ([US 8,749,394](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8749394) and related). Do not try to claim that.

### What I did not find (the open gaps)
1. A low-cost, in-home **node that verifies the NFPA-style pillow-level criterion** by playing a test tone from the alarm location and measuring at the pillow, including the ambient-noise term.
2. **Frequency-resolved transmission loss** (520 Hz vs about 3.1 kHz) through real doors and walls across many homes. The CPSC data is broadband dBA, and the Canadian work models a single band.
3. The reported **market gap**: a 2025 Bend, Oregon document says no single or multi-station smoke alarms meeting the 520 Hz requirement are on the market. I could not verify its date or whether it still holds.
4. No published **measurement procedure** (microphone height, door state, ambient baseline) for residential verification.

### Suggested narrowed claim
"A low-cost, self-calibrating bedside node that measures, at the pillow, the frequency-resolved loss from an alarm's location, checks it against the NFPA 72 pillow-level criterion, and reports which rooms in a home fail. Includes the first public dataset of 520 Hz vs 3.1 kHz door and wall loss across home types."

Treat adapting or raising the alarm's volume automatically as the riskiest part to claim, because of the adaptive-volume patents. The verification and the dataset are the safer claims.

### First experiments and kill criteria
- Measure the transmission loss of 10–20 interior doors at 520 Hz and 3.1 kHz with a calibrated phone or MEMS microphone and a speaker source.
- **Kill or downgrade the frequency story if** the loss difference between 520 Hz and 3.1 kHz is under about 2 dB across doors. The verification node can still stand on its own.
- Validate the node's dBA reading against a calibrated sound-level meter (many libraries and schools can lend one).

### Safety
No fire, no smoke and no sleepers needed. Use test tones at moderate levels, and keep them well below hearing-damage levels for anyone present.

---

## Next step
1. Read the claims of US 10,036,779, EP 2787746 A1 and US 7,522,035 directly on Google Patents.
2. Run the two kill-criteria experiments (about a weekend each).
3. Decide which project to plan in full.
