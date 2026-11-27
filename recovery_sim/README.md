# Recovery-demo simulation: step 1, collect demos

Status: the collector runs. This is step 1 of the plan in `../plan_recovery_demos.md` (section 10). Expert success rates are measured in step 2, not here. Step 2's expert check exists: `check_expert.py` (see Check 4).

## What it is
A simplified gripper moves in x, y and z. It is not an SO-101 arm. It picks up a block and puts it into a bowl, in MuJoCo. The script `collect.py` records demos in three modes:

- `clean`: no disturbance. The whole episode is saved.
- `embedded`: the block is shifted during the approach. The whole episode is saved, including the shift and the recovery.
- `separate`: the same shifts. Saves only the recovery window, plus up to 20 context frames before it (marked `train = False`).

### Shifts
- Early: the block jumps 7-10 cm while the hand passes 0.12-0.16 m on the way down. The expert redirects at once.
- Late: the block jumps on the first step of closing. The expert closes on nothing, reopens and tries again.

Saved episodes alternate between early and late, so the two counts differ by at most one.

### What each mode saves
- `clean`: whole episodes.
- `embedded`: whole episodes with an early or late shift and recovery.
- `separate`: from the shift (early) or from the first frame after the empty close (late) until the block is lifted. Up to 20 context frames before that are included with `train = False`.

## Setup
Run these inside this folder. You need Python 3.10 or newer.

Windows (PowerShell):
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```
Change `-3.12` to match the Python you have.

Linux or macOS:
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`requirements.txt` pins `mujoco`, `numpy`, `pillow` and `pytest`.

## Commands

Print all flags:
```powershell
.\.venv\Scripts\python collect.py --help
```

```
usage: collect.py [-h] --mode {clean,embedded,separate} [--frames FRAMES]
                  [--seed SEED] [--out OUT] [--no-images] [--preview]

options:
  -h, --help            show this help message and exit
  --mode {clean,embedded,separate}
  --frames FRAMES       train frame budget to fill
  --seed SEED
  --out OUT
  --no-images
  --preview             write GIF preview(s) of the first saved episode(s);
                        needs images
```

Flags:
- `--mode`: required. One of `clean`, `embedded`, `separate`.
- `--frames`: how many train frames to fill. Default 1000. Only `train` frames count. Whole episodes are kept, so the total can run a little over.
- `--seed`: random seed. Default 0.
- `--out`: output folder. Default `data`.
- `--no-images`: skip the camera images. Faster.
- `--preview`: write GIF previews of the first saved episode of each shift type (clean: one GIF; embedded and separate: one early, one late). Needs images, so do not combine it with `--no-images`. A white bar along the bottom of each GIF frame shows progress through the episode.

Each run ends with one line in this form (numbers are placeholders):
```
<mode>: <E> episodes (<e> early, <l> late), <N> train frames, <T> total frames. Expert success: early <s>/<a>, late <s>/<a>. Saved to <out>
```
For `clean`, the line shows `clean <s>/<a>` for expert success and `(clean)` for the episode types.

## Check 1: does the scripted expert work?
Run each mode without images:
```powershell
.\.venv\Scripts\python collect.py --mode clean --frames 2000 --no-images --out check
.\.venv\Scripts\python collect.py --mode embedded --frames 2000 --no-images --out check
.\.venv\Scripts\python collect.py --mode separate --frames 2000 --no-images --out check
```
Look for: expert success close to 100% in each run.

## Check 2: look at it
Run each mode with previews:
```powershell
.\.venv\Scripts\python collect.py --mode clean --frames 600 --preview --out look
.\.venv\Scripts\python collect.py --mode embedded --frames 600 --preview --out look
.\.venv\Scripts\python collect.py --mode separate --frames 600 --preview --out look
```
Open the GIFs in `look\embedded_seed0\` and `look\separate_seed0\`. Early shift: the block jumps while the hand is still above it. The hand lifts slightly, heads straight to the new spot and grasps once, never touching the block on the way. Late shift: the block jumps as the fingers start closing. The fingers close on nothing, reopen, lift, move over and grasp.

In the separate GIFs, a red border marks the context frames (`train = False`). Frames without a red border are the training frames.

## Check 3: tests
```powershell
.\.venv\Scripts\python -m pytest tests -q
```
Linux or macOS: use `.venv/bin/python` in place of `.\.venv\Scripts\python`.

## Check 4: scripted expert (step 2)
`check_expert.py` runs the scripted expert over seeded episodes and reports whether it meets the step 2 bar.

What it checks: 200 episodes per mode by default (100 early and 100 late for `embedded` and `separate`; `--episodes` must be even for those two). Every attempt counts. Attempts are never retried or replaced, and an exception inside a run is a failure. Success means the block is delivered and the episode can be saved. The target is at least 98% per mode.

Windows (PowerShell):
```powershell
.\.venv\Scripts\python check_expert.py --mode embedded --seed 100 --out results/step2
.\.venv\Scripts\python check_expert.py --mode all --seed 100 --out results/step2
```

Linux or macOS:
```bash
.venv/bin/python check_expert.py --mode embedded --seed 100 --out results/step2
.venv/bin/python check_expert.py --mode all --seed 100 --out results/step2
```

Flags:
- `--mode`: required. One of `clean`, `embedded`, `separate`, `all`. `all` runs the three modes.
- `--seed`: required. Episode `i` uses `episode_rng(seed, mode, i)`.
- `--episodes`: default 200.
- `--out`: output folder. With `--out results/step2` each mode writes `results/step2/check_<mode>_seed<seed>.json`.

Each run prints one summary line per mode and shift type. The exit code is 0 even when there are failures, because the JSON holds the verdict. A nonzero exit means the checker itself crashed.

Behaviour checks run only on successful episodes. A violation does not turn a success into a failure, but it is listed in the JSON.

| Check | Applies to | Flags a violation when |
|---|---|---|
| `shift_distance` | early, late | The block moves less than 7 cm or more than 10 cm in xy. |
| `shift_workspace` | early, late | The shifted block lands outside the workspace. |
| `shift_clearance` | early, late | The hand or fingers are closer to the block than the clearance minimum right after the shift. |
| `trigger_height` | early | The sampled trigger height is outside 0.12 to 0.16 m, or the shift does not fire on the control step where the falling hand first passes it. The shift can only fire at 20 Hz step boundaries, so the hand may be up to about 1 cm below the trigger height when it fires (see `info.shift_hand_z`). |
| `early_redirect` | early | The expert does not steer toward the new block position on the frame of the shift. |
| `early_empty_close` | early | The expert closes on nothing more than once before the release over the bowl, or the fingers end the first close outside the empty-close limit. |
| `early_contact_before_grasp` | early | The hand touches the block after the shift and before the grasp starts. |
| `late_shift_step` | late | The shift does not happen on the first frame of the close. |
| `late_empty_close` | late | The fingers end the first close outside the empty-close limit, the hand touches the block during that close, or the grip does not reopen after it. |
| `contact_before_shift` | early, late | Any block-hand contact happens before the shift. |
| `separate_window` | separate | The saved window or the context frames are not where they should be, or the train mask is wrong. |

Contact is checked at every physics substep, not only on the 20 Hz `touch` array. Intended grasp contact is not a violation. Contact during a late retry, between the empty close and the final grasp, is not a rule. It is counted as info only (`late_retry_contact_episodes`).

The JSON (`check_<mode>_seed<seed>.json`) holds:
- `by_type`: for each shift type (`none` for clean), attempts, successes, rate, Wilson 95% interval, train-frame min, median and max of successful episodes, and the count of episodes with violations.
- `total`: the same fields over all attempts.
- `failures`: seed, attempt, shift type and reason (`task failed`, `select returned None`, or `exception: <Type>: <message>`) for each failure.
- `violations`: seed, attempt, shift type and the names of the checks that failed.
- `info`: late-retry contact count, and the range of trigger heights and the real hand height at the shift.
- `pass`: `true` when the total rate is at least 98% and there are no violations.

For recorded results, see `results/step2.md`.

## Outputs
Each run writes to `<out>/<mode>_seed<seed>/`:

- `episode_XXXX.npz`: one file per saved episode.
- `episodes.json`: scalar metadata for each saved episode, plus `file`, `n_train` and `n_frames`.
- `summary.json`: frame totals, episode counts by shift type, and expert attempts and successes.
- GIF previews, only with `--preview`:
  - `clean`: `preview.gif`
  - `embedded` and `separate`: `preview_early.gif` and `preview_late.gif`

Each `.npz` file holds these arrays:

| Array | dtype | shape |
|---|---|---|
| `state` | float32 | (T, 5) |
| `action` | float32 | (T, 4) |
| `block_pos` | float32 | (T, 3) privileged, not a policy input |
| `touch` | bool | (T,) privileged, not a policy input |
| `train` | bool | (T,) |
| `top`, `wrist` | uint8 | (T, 240, 320, 3), absent with `--no-images` |
| `shift_type` | str scalar | () `"early"`, `"late"`, or `"none"` for clean |
| `shift_frame` | int64 | () index into the saved arrays; -1 for clean |
| `shift_frame_full` | int64 | () index into the full episode; -1 for clean |
| `trigger_z` | float64 | () NaN unless early |
| `block_before`, `block_after` | float64 | (3,) NaN for clean |
| `train_start`, `train_end` | int64 | () full-episode indices |
| `seed`, `attempt` | int64 | () rebuild the episode with `episode_rng(seed, mode, attempt)` |

`block_pos` and `touch` are for analysis and checks only. The policy must not use them as inputs.

## Not built yet
1. Convert episodes to a LeRobot dataset.
2. Combine the base clean demos with each condition's extra frames (control, separate, embedded).
3. Train ACT.
4. Test trained policies on normal, shifted and natural-failure starts.

## Design notes
- Groups are matched by frame count, not by human recording time.
- The expert reads the true block position. The policy will only see cameras and joint positions.
