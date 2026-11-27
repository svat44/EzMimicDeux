# Samsung Solve for Tomorrow (US) application draft: "Safe Second Life"

## Read this first: what I could and could not verify

- **Verified by search (US):** applications are due **November 23, 2026**; Promising Innovators and semi-finalists are announced January 20, 2027; national finalists March 18, 2027; the final event is in April 2027 (dates subject to change). The contest is for U.S. public middle and high school students in grades 6–12, and educators apply on behalf of their classrooms ([Samsung US](https://news.samsung.com/us/samsung-opens-applications-17th-annual-solve-for-tomorrow-competition/), [SamMobile](https://www.sammobile.com/news/samsung-solve-for-tomorrow-competition-now-open-for-us-students/)).
- **Could not read:** the actual US application form and the official rules. Both my fetches failed (the rules link returned 404, the news page timed out, and the flyer PDF came back unreadable). So I do **not** know the form's questions, word limits, whether a video or prototype is needed, or the exact judging weights.
- **Only a hint, not US rules:** a Hong Kong page describes three judging stages (need and creativity; feasibility and AI/tech use; impact and storytelling). Treat that as a guide to what Samsung values, not the US rubric.
- **Teacher required.** An educator submits for the classroom. If you don't have a teacher lined up, that is the first thing to fix today. Samsung also advertises free Virtual Application Clinics for educators (from the search results; I didn't find the schedule).

**What to do before pasting anything:** get the real form from samsung.com/solvefortomorrow, then fit the text below to its questions and word limits.

---

## Draft pitch (about 400 words; cut to fit)

**Title:** Safe Second Life: an open, low-cost way to check used laptop batteries

**The need.** Laptop battery packs are thrown away with working cells still inside. Those cells could power lights, phone charging or small solar storage for people who can't afford new batteries. The danger is a hidden internal short that makes a cell leak charge and, in the worst case, overheat. The standard way to catch one is to wait **7–28 days** and watch the voltage drop. Faster tests exist in research papers and one patent, but we found no open, low-cost tool and no public comparison of them on real salvaged cells.

**Our idea.** We will build a low-cost battery checker and test whether a measurement that takes **1–2 hours** can predict which salvaged cells would have leaked the most charge over **28 days**. We will compare the fast tests to the slow one on at least 30–40 cells, and we will publish the hardware designs and all of our data for free so other schools and repair groups can repeat it. Our goal is to learn what fast checks can and can't tell you, including how often they miss a bad cell, which is the number that matters for safety.

**How we use technology.** A microcontroller and a precision current-measurement circuit hold a cell at a fixed voltage and record tiny leakage currents. Data logging and statistics (rank correlation, error rates) turn the readings into a clear "flag this cell" signal. [If your team adds a simple classifier, say so here. Don't claim AI if it is only statistics.]

**Is it doable?** Yes. A 14-week plan with go/no-go checkpoints: build one channel, check it against a borrowed lab instrument, collect and label cells, run the 28-day reference test, then analyse. If the low-cost circuit can't reach the needed precision, we switch to a borrowed instrument and keep the benchmark. If the fast tests don't predict decay, we publish that result, because it tells others not to trust them.

**Impact and how we'll measure it.** (1) An open-source design and dataset anyone can use. (2) A one-page community guide on what a battery check can and cannot prove, with clear "do not use" rules. (3) Reported accuracy numbers, including false negatives. [Add a real partner here only if you have one, such as a local e-waste or repair group. Do not invent one.]

**Safety.** We will not build products from salvaged cells or tell anyone a cell is safe. All testing is supervised by [teacher/adult], in a fire-resistant container, with no abuse testing, and damaged cells are rejected and taken to a battery recycler.

---

## Modular answers (paste whichever question the form asks)

**One-sentence summary (about 30 words):** We're building a low-cost, open-source battery checker and testing whether a 1–2 hour measurement can predict which salvaged laptop cells leak charge over 28 days, so used batteries can be reused more safely.

**Who is affected:** Households, schools and repair groups that could reuse salvaged cells for small solar or backup power, and anyone near a badly checked battery. [Name your actual community and what you know about their need. Replace this with a real, specific detail.]

**What makes it new (say it carefully):** "We looked for an open, low-cost tool and a public comparison of fast self-discharge checks on salvaged cells and did not find one." Do **not** say "first" or "invented." The fast constant-voltage method is the Idaho National Laboratory's, and it is patented, so we cite it.

**Biggest risk and how we handle it:** The circuit may not be precise enough. We test it at week 2 against a lab instrument and have a fallback. Cells are hazardous, so work is supervised and limited to non-abusive tests.

**What we need:** A supervising teacher, a fire-resistant test area, a borrowed lab instrument for checking our circuit, and salvaged laptop packs. [Add any budget the form asks for. I have no price figures, so build the budget from real quotes.]

---

## Fit risks you should know about

1. **It's a research benchmark, not a finished solution.** Samsung's stages reportedly weigh need, feasibility and impact. Lead with the community problem and the open tool, not the benchmark.
2. **Lithium cells in a public school.** The school and district may restrict battery work. Ask your teacher and administration before you write it into the application. If they say no, the safer version is to use **new, labelled cells with deliberately varied storage history**, or to do the cell testing at a partner lab and keep the school work to circuit design and data analysis. That weakens the "salvaged cell" claim, so say so honestly.
3. **Individual vs classroom.** The contest is classroom-based. If you're working alone, ask your teacher how a classroom entry could include you.
4. **Unverified numbers.** I did not include any statistic about how many used cells exist or how many fires they cause, because I haven't found a source. If you add one, cite it.
5. **AI emphasis.** The Hong Kong stage description mentions AI/tech application. Don't force AI into this. Honest statistics beat decorative machine learning.

## Checklist for the next three days

- [ ] Confirm a teacher will submit by **Nov 23, 2026**, and get the real application form.
- [ ] Ask the teacher about school battery-safety rules and a supervised test area.
- [ ] Fit this pitch to the form's questions and limits. Replace every bracket.
- [ ] Check whether Samsung's rules say anything about hazardous materials, prototypes or open-source licensing (I couldn't read them).
- [ ] Have the teacher or a Samsung clinic confirm your reading of the rules.
