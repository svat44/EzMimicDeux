# Recovery-demo simulation: step 1, collect demos

Status: **not yet run.** MuJoCo was not installed on the computer where this was written, so expect to fix errors on the first try.

## What it is
A simplified gripper (moves in x, y, z; not an SO-101 arm) puts a block into a bowl. A script collects three kinds of demos: `clean`, `embedded`, `separate`.

## Setup (on the Quadro computer, inside this folder)
```powershell
py -3.12 -m venv .venv
```
```powershell
.\.venv\Scripts\python -m pip install mujoco numpy pillow
```
(Any Python from 3.10 up should do for this step; change `-3.12` to match.)

## Check 1: does the scripted expert work?
```powershell
.\.venv\Scripts\python collect.py --mode clean --frames 2000 --no-images --out check
```
```powershell
.\.venv\Scripts\python collect.py --mode embedded --frames 2000 --no-images --out check
```
```powershell
.\.venv\Scripts\python collect.py --mode separate --frames 2000 --no-images --out check
```
Want: expert success close to 100%.

## Check 2: look at it
```powershell
.\.venv\Scripts\python collect.py --mode embedded --frames 300 --preview --out look
```
Open `look\embedded_seed0\preview.gif`. Confirm the block jumps, the gripper misses, then recovers.

## Not built yet
1. Convert episodes to a LeRobot dataset.
2. Combine the base clean demos with each condition's extra frames (control, separate, embedded).
3. Train ACT.
4. Test trained policies on normal, shifted and dropped-block starts.

## Design notes to report
- Groups are matched by frame count, not human recording time.
- The expert reads the true block position; the policy will only see cameras and joint positions.
- In `separate`, saved episodes start right after the gripper closes on empty space.
