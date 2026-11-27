# Step 2: check the scripted expert

You are Claude Opus 5.5, the orchestrator. Deliver step 2 of section 10 in `plan_recovery_demos.md`: show that the scripted expert succeeds at least 98% of the time over 200 episodes in each mode, and that its behaviour matches section 3. Haiku subagents do the work in an instruct, run, review loop. This machine is Windows with a Quadro RTX 3000 (6 GB).

## Start
1. In the `EzMimicDeux` repo, run `git fetch`. If there are uncommitted changes, stop and ask.
2. Create branch `step2-expert` from `origin/step1-collector`, then merge `origin/main` into it to get this prompt. If the merge conflicts, stop and ask.
3. Read `plan_recovery_demos.md` (the authority), `recovery_sim/collect.py` and `recovery_sim/README.md`.
4. Set up `recovery_sim/.venv` from `requirements.txt` if needed, and run `pytest tests -q`. Record the result. If any test fails, report it and fix it before measuring anything.

## Build the check
Write `recovery_sim/check_expert.py`:
- Runs a set number of episodes (default 200) per mode, using `Episode`, `episode_rng` and `select` from `collect.py`. `embedded` and `separate` get exactly 100 early and 100 late.
- Counts every attempt. An episode that raises an exception is a failure with its message recorded. It must not crash the run or be retried or replaced.
- Success means the expert delivers the block and `select` returns a valid episode.
- Takes a `--seed` argument and runs without images.
- Writes JSON with attempts, successes, rate and 95% Wilson interval per mode and shift type, plus every failure's seed, attempt and reason.
- Reports saved frame counts per episode (minimum, median, maximum) for each mode and shift type, counting `train` frames.
- Checks each successful episode and reports violations separately from failures:

| Check | Applies to |
|---|---|
| Shift distance 7 to 10 cm, block inside workspace, clear of hand and fingers | Early and late |
| Trigger at hand height 0.12 to 0.16 m | Early |
| No empty close, and no hand or finger contact with the block between shift and grasp | Early |
| Shift on the first closing step, fingers close on nothing, then reopen | Late |
| No hand or finger contact before the block moves | Early and late |
| Training window starts and ends where section 3 says, with at most 20 context frames | Separate |

Contact must be checked at every physics substep. The saved `touch` array is sampled only at 20 Hz and can miss brief contacts, including during the early redirect, where the hand moves sideways while still low. If this needs a small hook in `collect.py`, it must not change any saved data or random draws; prove that by comparing episodes before and after.

Do not count intended grasp contact as a violation.

## Run it
1. Run with seed 100.
2. If any mode is below 98% or any behaviour check is violated, reproduce failures from their seed and attempt, find the cause and fix it. Rerun seed 100.
3. Once seed 100 passes, run seeds 200 and 300 once each, unchanged. These are the result. If either fails, fix the cause and confirm with three new seeds, and report every run, including failed ones.
4. Generate previews for all modes with `collect.py --preview`, and for up to three failed or violating episodes if any remain.

## Orchestration
Use many narrow Haiku subagents (`model: "haiku"`), up to 8 running at once, about 18 in total.

| Agent | Count | Gets only |
|---|---|---|
| Checker builder (owns `check_expert.py`) | 1 | Check requirements, public functions in `collect.py` |
| Expert fixer (owns `collect.py`; spawn only if needed) | 1 | A reproduced failure and the related code |
| Test writers: success counting, contact checks, report format | 3 | Their requirements and the interface contract |
| Runners: one per mode and seed | 9 | Their command and output folder |
| Failure analysts: one per mode (spawn only if needed) | up to 3 | That mode's failures and related code |
| Reviewers: contact detection, statistics, plan compliance | 3 | Their requirements, relevant code and diff |
| Docs writer | 1 | New commands and outputs |

- Before spawning, write `.orchestration/contract.md` with the function signatures and JSON fields, and one context packet per agent with only its task, rules, files, line ranges, edit permissions and expected reply.
- Spawn each agent once and reuse it with `SendMessage`. Send only what is new.
- One editor per file at a time. Reviewers and analysts do not edit code.
- Judge claims from real command output. Reproduce a defect before assigning a fix.
- Stop after 6 fix rounds, or if one failure survives 3 attempts, and report the blocker.

## Done when
- All tests pass.
- Each mode is at least 98% over 200 episodes on both seed 200 and seed 300 (or their replacements).
- No behaviour violations in those runs.
- Preview files exist and you have looked at frames from them. Say plainly what you could not judge; I will watch them myself.
- `README.md` documents the check, and a short results file is saved at `recovery_sim/results/step2.md` with commands, commit hash, rates, intervals, frame counts and every failed run.

## Limits
- Change only `recovery_sim/`, `.gitignore` and `.orchestration/`. Do not edit the plan.
- Do not weaken a check, lower the 98% target, filter out hard cases or narrow the shift or start ranges to pass. If the target needs any of these, stop and ask.
- Do not start steps 3 to 9. No LeRobot, training or rented machines.
- Install nothing new without asking. Delete only files you created in this session.
- The repo is public. Never commit keys, tokens, personal details, datasets or virtual environments.
- Commit locally on `step2-expert` with a GitHub no-reply email. Push the branch after every commit without asking. Ask before merging into `main`.

## Final report
Results per mode, shift type and seed; fixes made and why; typical frames per episode compared with the plan's N = 6,000; agents used; anything unverified. Then list the preview paths.
