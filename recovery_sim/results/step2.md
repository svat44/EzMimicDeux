# Step 2 results: scripted expert check

Date: 2026-11-26. Machine: Quadro RTX 3000 (6 GB), Linux, Python 3.14, mujoco 4.0.1. All runs without images.
Code: commit `6e8c4f5` (branch `step2-expert`); every JSON below records that hash.

## Commands
Run from `recovery_sim/`, once per mode and seed (S = 100, 200, 300):
```bash
.venv/bin/python check_expert.py --mode clean    --seed S --episodes 200 --out results/step2
.venv/bin/python check_expert.py --mode embedded --seed S --episodes 200 --out results/step2
.venv/bin/python check_expert.py --mode separate --seed S --episodes 200 --out results/step2
```
Raw output: `results/step2/check_<mode>_seed<S>.json`.

Seed 100 was the development seed; seeds 200 and 300 are the result and were each run once, unchanged.

## Success rates (200 episodes per mode and seed; 100 early + 100 late for embedded and separate)

| Mode | Shift | Seed 100 | Seed 200 | Seed 300 | Wilson 95% per seed |
|---|---|---|---|---|---|
| clean | none | 200/200 | 200/200 | 200/200 | [0.981, 1.000] |
| embedded | early | 100/100 | 100/100 | 100/100 | [0.963, 1.000] |
| embedded | late | 100/100 | 100/100 | 100/100 | [0.963, 1.000] |
| embedded | total | 200/200 | 200/200 | 200/200 | [0.981, 1.000] |
| separate | early | 100/100 | 100/100 | 100/100 | [0.963, 1.000] |
| separate | late | 100/100 | 100/100 | 100/100 | [0.963, 1.000] |
| separate | total | 200/200 | 200/200 | 200/200 | [0.981, 1.000] |

Target: at least 98% per mode over 200 episodes. Met on seeds 200 and 300 (and 100) in every mode.

## Behaviour checks
0 violation episodes in all 9 runs (checks listed in `README.md`, Check 4). Contact was sampled at every physics substep, plus the state just before each shift. Late-retry contact (info only): 0 episodes in every run.

Trigger: sampled trigger heights all lie in 0.12-0.16 m. The real hand height on the first frame after an early shift ranged 0.111-0.159 m, because the shift fires at the 20 Hz step on which the falling hand first passes the sampled height (about 1 cm per step).

## Failed runs
None. No run failed, no episode failed, no episode raised an exception. No fixes to the expert were needed in step 2. (The checker itself was corrected during development before the final runs: Wilson bounds were rounded in the JSON, the settle loop and the pre-shift state were not sampled for contact, and "redirect at once" had no check. All seed results above are from the corrected checker.)

## Train frames per saved episode (min / median / max)

| Mode | Shift | Seed 100 | Seed 200 | Seed 300 |
|---|---|---|---|---|
| clean | none | 108 / 122 / 137 | 111 / 125 / 139 | 108 / 123 / 139 |
| embedded | early | 122 / 141 / 153 | 123 / 139 / 154 | 120 / 137.5 / 157 |
| embedded | late | 171 / 188 / 205 | 172 / 189 / 203 | 168 / 188 / 203 |
| separate | early | 48 / 51 / 55 | 48 / 50 / 54 | 48 / 51 / 55 |
| separate | late | 78 / 81 / 86 | 77 / 81 / 85 | 77 / 81 / 84 |

`separate` counts only `train` frames (up to 20 context frames per episode are extra).

Compared with the plan's N = 6,000 extra frames per condition (section 4), using the medians and an even early/late mix:
- A (clean): about 123 frames per episode, so about 49 episodes. The 50-episode base set is about 6,150 frames, matching the plan's estimate that N is roughly the size of the base set.
- B (separate): about 66 frames per episode, so about 91 episodes (about 91 recoveries).
- C (embedded): about 163 frames per episode, so about 37 episodes (about 37 recoveries).
B gets about 2.5 times as many recoveries as C for the same frames, as section 4 expects.

## Previews
Generated with `collect.py --mode <mode> --seed 100 --frames 300 --preview` (not committed; under `smoke/step2/previews/`). Frames were inspected for the early redirect, the late empty close and retry, the separate context border and a clean delivery.
