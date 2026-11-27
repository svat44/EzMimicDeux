# Recovery-demo simulation: step 1, collect demos

Status: the collector runs. This is step 1 of the plan in `../plan_recovery_demos.md` (section 10). Expert success rates are measured in step 2, not here.

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
