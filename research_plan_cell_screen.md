# Research plan: Open, low-cost benchmark of fast self-discharge screens for salvaged lithium cells

Status: draft v1. Built from the gap analysis and prior-art check in this folder. Items marked **[verify]** are things I could not confirm from sources.

## 1. Project in one paragraph

Large numbers of used 18650 cells sit in discarded laptop packs **[verify: find a sourced figure before quoting any number]**. Reusing them could store solar power in communities that cannot afford new batteries, but the risk is cells with hidden internal shorts. Today the standard test for a short is waiting 7–28 days. Faster methods exist in papers, patents and a commercial instrument, yet I found no head-to-head comparison, no test on salvaged cells with naturally formed shorts, no open dataset, and no open low-cost hardware. This project builds that rig, collects that dataset, and answers: **do minutes-to-hours screens predict which salvaged cells will self-discharge fastest over 28 days, and do any of them catch cells that capacity and resistance tests miss?**

**What you may claim:** first open, low-cost, multichannel rig and public dataset benchmarking fast screens on salvaged cells (subject to a final prior-art read of the patent claims).
**What you may NOT claim:** inventing fast self-discharge detection. The constant-voltage method is the Idaho National Laboratory's, and it is patented ([US 10,036,779](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10036779)). Cite it and say you are benchmarking it.

## 2. Research questions and pre-registered hypotheses

| | Question | Hypothesis | Pre-registered success test |
|---|---|---|---|
| RQ1 | Does a constant-voltage current screen (INL-style, run for about 1–2 h) rank salvaged cells like their 28-day reference decay? | Yes. | Spearman ρ ≥ 0.7 on ≥ 30 cells |
| RQ2 | Does a short OCV-relaxation-slope screen do as well? | Weaker than RQ1, because relaxation overlaps self-discharge. | Compare ρ and ROC AUC with RQ1 (paired bootstrap) |
| RQ3 | Do capacity and DC internal resistance alone predict decay? | No (they are the baseline). | ρ with 28-day decay reported |
| RQ4 | Do the screens flag cells with low coulombic efficiency, the safe proxy for the end-of-charge heating seen by [Han et al. 2022](https://mdpi.com/1996-1073/16/1/405)? | Cells with low efficiency show higher screen current. | Point-biserial or Mann-Whitney test, effect size reported |

The primary outcome is the **top-quartile flag**: a screen "flags" a cell if it ranks in the highest 25% of current. **Safety-critical metric: the false-negative rate** (a fast-decaying cell the screen called fine), reported with a confidence interval.

Negative results are publishable here. "Fast screens do not predict used-cell decay" would itself be a useful, citable finding.

## 3. Measurement methods

Keep every condition fixed and written down before starting.

- **Reference (M1):** charge each cell to a fixed state of charge, rest at least 24 h (the Keysight note warns that OCV change from too-short rest is the sum of relaxation and self-discharge), then log open-circuit voltage for 28 days in a temperature-controlled box at 25 ± 1 °C. Self-discharge is strongly temperature dependent ([NASA test](https://ntrs.nasa.gov/api/citations/20180003308/downloads/20180003308.pdf): sharply higher at 35 °C than 10 °C), so log temperature every cell, every reading. Choose the state of charge once (the NASA work suggests rates are lowest near 30%, a 70% state of charge was used in the study I found), and do not change it.
- **Constant-voltage screen (M2):** hold the cell slightly below its open-circuit voltage and record current until it stabilises, per the INL description. **[verify]** exact offset and stop criterion from the paper before building.
- **Relaxation screen (M3):** precise OCV versus time over the first 1–2 h after the rest period.
- **Baselines:** capacity (one slow discharge), DC internal resistance (load step), and **coulombic efficiency** (charge in versus discharge out over 2 cycles at ≤ 0.5C).
- **Ground-truth check for the rig:** borrow a bench source-measure unit (SMU) and compare your rig to it on 5 cells before trusting any number.

## 4. Hardware plan (build in stages)

**Target specs (from the 4.2 µA healthy-cell figure and the need to rank cells):**
- Current resolution and noise ≤ 0.5 µA RMS, ideally ≤ 0.2 µA.
- Voltage hold stable to roughly tens of µV over hours **[verify by bench test, I have not calculated the allowed drift]**.
- Per-channel isolation, so one shorted cell cannot disturb the others.
- Over-voltage, over-current and over-temperature cut-offs in hardware, not only firmware.
- Design goal: small per-channel cost, but I have no price quote, so write the budget only after the first channel works.

**Architecture options to evaluate on the bench** (I found open potentiostat designs that reach nA-level current noise, such as [KickStat](https://pmc.ncbi.nlm.nih.gov/articles/PMC9041188) at about 4.5 nA, but none built for holding a 3–4.2 V battery cell, so the front end is yours to design):
1. Low-noise reference plus op-amp driving the cell through a precision shunt, with a 24-bit delta-sigma ADC across the shunt.
2. A dedicated analog front end (as in open potentiostats) with a level-shifting stage.
3. Fallback: use a borrowed SMU for all M2 data, and make the *low-cost rig* a second-stage question. This still answers RQ1–RQ4.

**Stages:** one channel, then 4, then 8. Do not scale until Gate G1 passes.

## 5. Sample and statistics

- **Cells:** at least 40 salvaged 18650s (to keep ≥ 30 after dropouts). Take them only from undamaged packs (no swelling, dents, heat marks or leaks), photograph and number every cell, and record brand, pack source and visible wear.
- **Why 30:** a rank correlation of about 0.5 is detectable at roughly 30 cells (my approximation, **[verify with a power calculation]**). If the true correlation is smaller, 30 cells will miss it, so report confidence intervals, not just p-values.
- **Blinding:** the person running M2/M3 does not see M1 results until all screens are finished.
- **Repeatability:** repeat M2 on every cell at day 14 and day 28. Report within-cell variation, because a screen that disagrees with itself cannot predict anything.
- **Analysis:** Spearman ρ with bootstrap confidence intervals; ROC AUC for the top-quartile flag; false-negative rate with a confidence interval; paired comparison of methods; a Bland-Altman style plot of rig versus SMU.
- **Do not** drop outliers after seeing results. Define exclusion rules (such as cells that fail visual inspection) in advance.

## 6. Timeline (about 14 weeks; the 28-day reference sets the minimum)

| Week | Work | Gate |
|---|---|---|
| 0 | Get approvals (see section 8) before any experiment. Read the INL paper and patent claims in full. | No approval, no experiments |
| 1–2 | Build one channel. Compare to a borrowed SMU on 5 cells. | **G1** |
| 3 | Collect cells, inspect, number, baseline capacity, DC resistance, coulombic efficiency. | |
| 4 | Set state of charge, start the 28-day reference logs (M1) for all cells. | **G2**: logs show measurable decay and low noise by day 7 |
| 4–8 | Run M2 and M3 on all cells (day 1, 14 and 28 repeats). | |
| 9 | Unblind. Run the pre-registered analysis. | **G3** |
| 10–12 | Optional extension (section 10). Write-up, open-hardware files, dataset release. | |
| 13–14 | Review with an adult mentor or lab contact. Release. | |

## 7. Go/no-go gates

- **G1 (week 2):** rig noise ≤ 0.5 µA RMS and agreement with the SMU within about 5% plus 0.5 µA on 5 cells. **If it fails**, switch to option 3 (borrowed SMU) and keep the benchmark, drop the low-cost-hardware claim.
- **G2 (week 4):** by day 7 the logs separate at least the fastest-decaying cells from the rest. **If every cell looks the same**, the sample is too uniform: add older or more varied cells.
- **G3 (week 9):** ρ ≥ 0.7 for the best screen. **If ρ < 0.5 for all screens**, report as a negative result (still publishable). **If between 0.5 and 0.7**, report as a partial predictor with the false-negative rate front and centre.

## 8. Safety and approvals

Used lithium cells can catch fire. Treat this as the main constraint, not a footnote.
- **Adult supervision and a risk assessment before starting.** Student-built devices and hazardous activities typically need review under the Society for Science rules ([International Rules](https://www.societyforscience.org/isef/international-rules/)). The search did not find a lithium-specific rule, so **[verify]** the current Hazardous Chemicals, Activities or Devices section and your local fair's rules.
- All testing inside a fire-resistant container, away from flammable material, with a Class D or ABC extinguisher and sand nearby. **[verify]** the right extinguisher advice with your supervisor or local fire safety contact.
- Reject any swollen, dented, leaking, hot or visibly damaged cell. Never charge or test one.
- Charge only at modest rates (≤ 0.5C), never unattended, with hardware voltage and temperature cut-offs.
- **No abuse testing**: no puncturing, crushing, overcharging or deliberately shorting cells. Use the 28-day reference and the coulombic-efficiency proxy instead of trying to trigger the end-of-charge heating.
- Store cells individually, partially charged, in a non-conductive container. Take rejected cells to a battery recycler. Do not put them in household trash.
- Do not present the output as safe-to-use certification. The deliverable is a research benchmark, not approval to put salvaged cells in a product.

## 9. Deliverables

1. Open-source hardware: schematics, board files, firmware, bench-validation report.
2. Public dataset: per-cell baselines, 28-day logs, every screen reading, temperature and metadata, in plain CSV with a README (release with a permanent identifier).
3. A short paper-style report with the pre-registered analysis, including negative findings.
4. A one-page community guide: what the screen can and cannot tell you, and the "do not use if" rules.

## 10. Optional extensions (only after G3)

- Test whether adding the screen to capacity and resistance improves a combined classifier (cross-validated, with a held-out set).
- Second chemistry or a second source of cells to test generality.
- Collaborate with a university lab to run a supervised end-of-charge temperature test on a few cells, **only** by their staff under their safety procedures.

## 11. Risks and how this plan handles them

| Risk | Handling |
|---|---|
| Method is patented and published | Position as benchmark, hardware and dataset. Cite INL. Read claims first. |
| Rig cannot reach sub-µA noise | G1 fallback to a borrowed SMU. Hardware claim dropped, not the project. |
| 28-day reference is slow | Start M1 early. Everything else runs in parallel. |
| Cells too uniform to rank | G2. Broaden the sample. |
| Temperature drift fakes differences | Insulated box, logged temperature, analysis includes temperature as a covariate. |
| Overclaiming safety | Section 8 last bullet. Report false-negative rate prominently. |
| Salvaged-cell sourcing is messy | Record provenance. Treat pack-of-origin as a grouping variable in the analysis. |

## 12. Competition fit and timing

- **Samsung Solve for Tomorrow (US):** the U.S. newsroom lists applications open through **November 23, 2026** (three days from today, 2026-11-20), for public middle and high school students in grades 6–12, submitted by educators on behalf of their classrooms ([Samsung US](https://news.samsung.com/us/samsung-opens-applications-17th-annual-solve-for-tomorrow-competition/); I could not find the official rules text, so **[verify]** on samsung.com/solvefortomorrow). Other countries have different dates and rules. I don't know where you are or whether you have a teacher to submit, so I can't say this applies to you.
  - The competition's published themes include environmental sustainability, and one regional rubric weights creativity (25%) and feasibility (30%) **[verify for your country]**. This project's strengths line up with those: a measurable e-waste and clean-energy problem, an open and affordable tool, and a feasible weekend-by-weekend build.
  - A "benchmark and open tool" framing is less flashy than an invention. Lead the pitch with the community problem and the finished open tool, not the benchmark.
- **ISEF-style fairs:** the project fits a Systems or Energy category, but the hazard approvals in section 8 must be in place before experiments begin. Check your regional fair's deadlines and forms.

## 13. What I need from you

1. Where are you competing, and is there a teacher or adult mentor who can supervise battery work and submit an entry?
2. Do you have access to a bench source-measure unit or a university or makerspace lab (for G1 and the ground-truth check)?
3. How many weeks do you have? If less than 14, I'd cut the sample to 30 cells and start the 28-day logs first.

---

## 14. Independent track (no competition required)

Updated after deciding the project does not have to be for Solve for Tomorrow. The science and the 14-week plan are unchanged. Only the outlets and deadlines change. Venue facts below come from search summaries, so **confirm each on the official site.**

### Timing if you start now (today is 2026-11-20)
My estimate, assuming approvals take about two weeks: approvals done early December, one-channel rig checked against a borrowed instrument by mid-December (G1), 28-day logs start early January, screens and analysis finish about mid-February, write-up and release by mid-March. This fits a spring fair. Trim to 30 cells if the schedule slips, and start the 28-day logs as early as possible because they set the minimum length.

### Where it can go
| Outlet | What I found | What it needs |
|---|---|---|
| **ISEF-affiliated science fair** (the route to [Regeneron ISEF](https://www.societyforscience.org/isef/affiliated-fair-network/)) | You qualify through an affiliated fair, not by direct entry. For 2027: grades 9–12 or equivalent, under age 20 on May 1, 2027. The last date to hold an affiliated fair is April 12, 2027, and ISEF is May 8–14, 2027 in Los Angeles. Use the Society's "Find an Affiliated Fair" tool. | Hazard and risk-assessment forms **before experiments start**, from the beginning of the research. I found no clear rule on research start dates or homeschool entry, so read the official International Rules and your fair's rules first. |
| **Journal of Emerging Investigators (JEI)** ([guidelines](https://emerginginvestigators.org/submissions/guidelines)) | Peer-reviewed for grades 6–12. Needs a mentor (teacher, parent or other adult) as senior last author. The mentor or a lab PI submits, not the student. Authors need a valid affiliation. JEI's payment page lists $49 per submission (an earlier summary said $45, so confirm). Pre-review decisions take at least 2–3 weeks. **Scope warning: JEI excludes manuscripts that only compare methods, and it bans AI help with writing, statistics and literature summaries. See [jei_track_plan.md](jei_track_plan.md) before committing to this route.** | An adult mentor. Same person you need for safety. |
| **Open dataset and hardware release** | A public Zenodo DOI is a standard way to publish data and design files. The open-hardware journal HardwareX accepts links only to approved repositories (Zenodo, OSF, Mendeley Data), fully public at submission, and does not accept GitHub or Google Drive as the main link ([HardwareX instructions](https://zenodo.org/record/3944758)). I did not find whether it takes high-school or independent authors. | Nothing but the work. This one does not depend on any school or competition. |
| **Public pre-registration** | Post your hypotheses and analysis plan (sections 2 and 5) in a public registry such as OSF **before** you unblind. It is cheap and makes a negative result more credible. | A few hours. |

### What changes in the plan
- **Week 0 is now the critical path.** The adult mentor and hazard approvals gate everything. Nothing else on the timeline can start without them.
- **Drop competition framing.** The "community impact" pitch language is optional. The deliverables in section 9 (open hardware, dataset, report, community guide) are the real output.
- **Pick the fair early.** Affiliated fairs often require paperwork before experiments begin. Choose a fair in December so the forms match your start date.
