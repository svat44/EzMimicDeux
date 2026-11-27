# Step 1: update the data collector

You are Claude Opus 5.5, the orchestrator. Deliver step 1 of section 10 in `plan_recovery_demos.md`: update `recovery_sim/collect.py` for early and late block shifts so that it runs in all modes. Haiku subagents do the work in an instruct, run, review loop. This machine is Windows with a Quadro RTX 3000 (6 GB).

## Start
1. Work in the `EzMimicDeux` repo. If this folder is not it, clone `https://github.com/svat44/EzMimicDeux.git`; otherwise run `git pull --ff-only`. If the pull fails or there are uncommitted changes, stop and ask.
2. Read `plan_recovery_demos.md`, `recovery_sim/README.md` and `recovery_sim/collect.py` in full. The plan is the authority. The code and README predate it and have never been run.
3. Create branch `step1-collector`.
4. In `recovery_sim`, create `.venv` with an installed Python 3.10 or newer (`py -0` lists them) and install `mujoco`, `numpy` and `pillow` into it. Save the exact versions to `recovery_sim/requirements.txt`. If no suitable Python exists, stop and ask.
5. Run the unmodified script in all three modes with `--no-images --frames 500` and record the output as the baseline.

## Required behaviour
Control rate is 20 Hz. Modes stay `clean`, `embedded`, `separate`.

**Shifts** (`embedded` and `separate`)
- Distance uniform from 7 to 10 cm, random direction, block stays inside the workspace already used by the script.
- Redraw any shift that leaves the block overlapping or touching the hand or fingers. Check this with MuJoCo contacts or geometry after the move.
- Early: triggers when the hand passes a random height from 0.12 to 0.16 m on the way down. The expert redirects at once and goes to the new position without closing on empty space and without hitting the block.
- Late: the block moves on the first control step of closing. The expert finishes closing on empty space, reopens and retries.
- Saved episodes are half early and half late. Balance the episodes that are saved, not the attempts, so that failures cannot skew the mix. With an odd count the difference is one.
- Report attempts and successes separately for early and late.

**What each mode saves**
- `clean`: whole episode, no disturbance.
- `embedded`: whole episode, including delivery to the bowl.
- `separate`: training frames start at the shift (early) or at the first frame after the empty close has finished (late). They end when the block has been lifted to carrying height.
- `separate` also stores up to 20 frames before the start as context, for observation history. Mark every frame with a boolean `train`; context frames are `False`. In `clean` and `embedded` all frames are `True`.
- An episode is kept only if the full task succeeds, including in `separate`, so run the expert to the end even though later frames are not saved.

**Frame budget and records**
- `--frames` counts only `train` frames. Keep whole episodes; exact trimming belongs to step 3.
- Each episode records shift type, shift frame index, block position before and after, and seed. Clean episodes mark these as not applicable.
- The same seed and arguments give the same result.
- Keep the existing flags. `--preview` writes one GIF for an early episode and one for a late episode, with context frames visibly marked.

## Orchestration
Your job is to split the work, write instructions, judge evidence and integrate. Use many narrow Haiku subagents (`model: "haiku"`), about 23 in total, with up to 8 running at once. Each sees only the context for its own job, and is spawned once and then reused.

| Agent | Count | Output | Gets only |
|---|---|---|---|
| Spec auditor | 1 | Checklist mapping every requirement to the code | Required behaviour, `collect.py` |
| Shift builder | 1 | Shift sampling, overlap rejection, triggers | Shift rules, scene XML, shift and trigger code |
| Expert builder | 1 | Early redirect and late retry | Expert behaviour rules, movement and run code |
| Saving builder | 1 | Modes, `train` mask, metadata, budget, balance | Mode, saving and record rules, recording and main code |
| Test writers | 5: shifts, expert, saving, budget and balance, repeatability and shapes | Tests in `recovery_sim/tests/`, one file each | Their rules and the interface contract. No implementation code |
| Runners | 9: one per mode and seed | Commands, exit codes and numbers, each in its own folder under `smoke/` | Their commands and where to write |
| Reviewers | 4: shift geometry, expert behaviour, saved data, plan compliance | Defects with file, line, evidence and how to reproduce | Their rules, relevant code and diff |
| Docs writer | 1 | `recovery_sim/README.md` | Final flags, outputs and commands |

**Context packets**
- Before spawning, write the interface contract in `.orchestration/contract.md`: function signatures, saved array names, types and shapes, and metadata fields. Builders and test writers follow it.
- Write one packet per agent in `.orchestration/context/<agent>.md`: the task, only the spec text that applies, exact files and line ranges, what it may edit and what to return.
- Tell each agent to read its packet and only what the packet lists. If it needs more, it asks you and you add just that.

**Reuse**
- Record each agent's ID in `.orchestration/board.md`.
- Give later tasks to the same agent with `SendMessage`, which keeps its context. A new `Agent` call starts from nothing.
- Follow-ups contain only the new defect, task or changed lines. Send them only to agents they affect.
- After an edit, update line ranges for the affected agents.
- Replace an agent only if it can no longer be continued or keeps repeating the same mistake.

**Loop, once per round**
1. **Instruct.** State the task, what may be edited, what to return and how it will be checked.
2. **Run.** Only one agent edits a given file at a time, so the three builders work one after another. Test writers can work alongside them. Runners and reviewers work in parallel after edits finish. Ask for short replies, with details in report files.
3. **Review.** Check claims against real command output and the diff. Reproduce each reported defect before assigning a fix. A subagent saying "passed" is not evidence.

You keep `board.md` (tasks, owners, status, decisions). Each agent writes only its own report file in `.orchestration/`. You pass findings between agents, sending each only what applies to it.

Stop looping when every check below passes. After 6 rounds, or if the same defect survives 3 fix attempts, stop and report what is blocking.

## Done when
- All three modes finish without errors at `--frames 2000 --no-images` for seeds 0, 1 and 2.
- All three modes finish with images at `--frames 600 --preview`, with correct array shapes (240 x 320 x 3).
- Tests pass for: shift distance and workspace, no overlap, trigger timing, no empty close in early episodes, empty close in late episodes, start and end of `separate`, context length and `train` mask, early and late balance, frame budget, repeatability.
- You have opened frames from the early and late previews and confirmed the behaviour. Say plainly if you could not judge it.
- Expert success rates are reported per mode and shift type. The 98% target over 200 episodes is step 2, so report the numbers but do not tune toward it unless the script cannot complete the runs.
- `README.md` matches the code.

## Limits
- Change only `recovery_sim/`, `.gitignore` and `.orchestration/`. Do not edit the plan: if it is ambiguous, contradictory or physically impossible, stop and ask.
- Do not start steps 2 to 9. No LeRobot, no training, no rented machines.
- Do not weaken a test or a requirement to make it pass.
- Install nothing beyond the packages above and `pytest` without asking. Delete only files you created in this session.
- The repo is public. Never commit keys, tokens, personal details, datasets or virtual environments.
- Commit locally on `step1-collector`, using a GitHub no-reply email. Ask before pushing.

## Final report
What changed; each "Done when" item with the command and result; success rates; rounds, agents spawned and any replaced; anything unverified or still open. Then show the preview file paths so I can watch them.
