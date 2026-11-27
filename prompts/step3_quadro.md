# Step 3: build the LeRobot datasets

You are Claude Opus 5.5, the orchestrator. Deliver step 3 of section 10 in `plan_recovery_demos.md`: convert the collected episodes into LeRobot datasets that load with correct frame counts. Haiku subagents do the work in an instruct, run, review loop. This machine is Windows with a Quadro RTX 3000 (6 GB).

## Start
1. In the `EzMimicDeux` repo, run `git fetch`. If there are uncommitted changes, stop and ask.
2. **Gate:** find step 2's results in `recovery_sim/results/step2.md` on `step2-expert` (local or `origin`). It must show every mode at least 98% over 200 episodes, with no behaviour violations. If the file is missing or does not show this, stop and report. Do not run step 2 yourself.
3. Create branch `step3-dataset` from `step2-expert`, then merge `origin/main` into it to get this prompt. If the merge conflicts, stop and ask.
4. Read `plan_recovery_demos.md` (the authority, especially sections 3 to 6), `recovery_sim/collect.py` and `recovery_sim/README.md`. Run the existing tests and record the result.

## Environment
- Install LeRobot v0.7.0, pinned, in a new `recovery_sim/.venv-lerobot`. Check its Python requirement and dataset API from the installed source, not from memory.
- Save exact versions to `recovery_sim/requirements-lerobot.txt`.
- If it needs a Python version or system tool that is missing, or does not work on Windows, stop and ask.
- Add the new environment and dataset folders to `.gitignore`.

## Datasets
Build one dataset per condition. Each is the same base set plus that condition's extra frames.

| Dataset | Base | Extra |
|---|---|---|
| `control` | 50 clean episodes | Exactly 6,000 clean frames |
| `separate` | Same 50 | Exactly 6,000 `separate` training frames |
| `embedded` | Same 50 | Exactly 6,000 `embedded` frames |

- Base episodes are the same files in all three. Control's extra episodes use a different seed, so none repeats a base episode.
- Use data seeds from 1000 upward, never the seeds used in step 2.
- Collect with images, using `collect.py`.
- **Exact trimming:** take extra episodes in order and cut the end of the last one so the training total is exactly 6,000. Log the episode and the frames removed.
- Report the early and late episode counts after trimming. They differ by at most one in `separate` and `embedded`.

## Conversion
Write `recovery_sim/convert.py`.
- 20 fps. Features: both cameras (240 x 320 x 3), joint state (5) and action (4), plus one task description.
- `block_pos`, `touch` and shift metadata must never be policy inputs. Keep metadata in a separate manifest file outside the observation features.
- **Context frames** (`train = False`) must stay in their episode so history can read them, but must never be sampled as training targets and do not count toward 6,000. Store the flag and provide a tested way to list valid training indices. Show that LeRobot's loader can be restricted to those indices.
- Normalisation statistics for each dataset use training frames only. Check what LeRobot computes by default and correct it if it includes context frames.
- Action chunks of 40 must not cross episode boundaries; steps past an episode's end are marked as padding.
- Datasets stay on this machine. Do not upload them to Hugging Face or anywhere else.
- Check free disk space before collecting, from the size of a small trial run.

## Do not build
Observation history is step 4. Verify only that the stored data can supply frames at offsets -20, -10 and 0, repeating the first frame at the start of an episode.

## Orchestration
Use many narrow Haiku subagents (`model: "haiku"`), up to 8 running at once, about 17 in total.

| Agent | Count | Gets only |
|---|---|---|
| API researcher | 1 | The installed LeRobot dataset source and the conversion needs |
| Collection builder: seeds, base set, exact trimming | 1 | Dataset rules, `collect.py` outputs |
| Conversion builder (owns `convert.py`) | 1 | Conversion rules, the API report |
| Test writers: counts and trimming, image and value fidelity, training mask and statistics, chunks and history indices | 4 | Their rules and the interface contract |
| Runners: one per dataset to collect and convert, one per dataset to load and count | 6 | Their commands and folders |
| Reviewers: data leakage, mask and statistics, plan compliance | 3 | Their rules, relevant code and diff |
| Docs writer | 1 | Commands and outputs |

- Before spawning, write `.orchestration/contract.md` with function signatures, feature names, types, shapes and manifest fields, and one context packet per agent with only its task, rules, files, line ranges, edit permissions and expected reply.
- Spawn each agent once and reuse it with `SendMessage`. Send only what is new.
- One editor per file at a time. Reviewers do not edit code.
- Judge claims from real command output. Reproduce a defect before assigning a fix.
- Stop after 6 fix rounds, or if one defect survives 3 attempts, and report the blocker.

## Done when
- All old and new tests pass.
- All three datasets load through LeRobot, and a data loader returns a batch of 8 from each.
- Counted from the loaded datasets: 50 base episodes, identical across all three, and exactly 6,000 extra training frames in each.
- Loaded state and action values match the source files exactly. Image differences from any video compression are measured and reported.
- Sampling a full pass of valid indices never returns a context frame.
- You have viewed sample loaded frames from both cameras for each dataset. Say plainly if you could not judge them.
- `README.md` documents the commands, and `recovery_sim/results/step3.md` records versions, commit hash, seeds, counts, trimmed episodes, dataset sizes and file checksums.

## Limits
- Change only `recovery_sim/`, `.gitignore` and `.orchestration/`. Do not edit the plan: if it is ambiguous or cannot be met, stop and ask.
- Change `collect.py` only to fix a defect, then rerun the tests and the step 2 check.
- Do not start steps 4 to 9. No model changes, training or rented machines.
- Do not weaken a test or requirement to pass.
- Install only LeRobot and its required dependencies, plus the packages already pinned. Delete only files you created in this session.
- The repo is public. Never commit keys, tokens, personal details, datasets or virtual environments.
- Commit locally on `step3-dataset` with a GitHub no-reply email. Ask before pushing or merging into `main`.

## Final report
Each "Done when" item with command and result; counts per dataset; disk use; agents used; anything unverified or still open.
