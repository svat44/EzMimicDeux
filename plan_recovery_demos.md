# Plan: how should recovery be recorded for a robot arm?

Status: draft v3, 2026-11-26. Design choices are fixed; change one only before the main runs, and log why. Simulation first. Numbers marked **(guess)** are estimates. No code has been run and no results exist.

## 1. Question
With the same number of extra training frames, does a policy recover better when it learns from **separate recovery demos** (only the reaction and fix) or from **embedded corrections** (the fix inside a full successful demo)?

**Hypothesis:** embedded corrections will do better, because the policy learns what triggers a recovery.

**Goal:** a research result in 2–3 months. A real arm may follow (section 11).

## 2. Setup

| Item | Choice |
|---|---|
| Simulator | MuJoCo |
| Robot | Simplified gripper moving in x, y, z. Not an SO-101 |
| Task | Pick up a block and place it in a bowl |
| Cameras | Simulated top and wrist, 320 x 240 |
| Demonstrator | Scripted expert that reads the true block position |
| Policy | ACT through LeRobot, with and without observation history |

## 3. Disturbances
The policy should learn both triggers.

| Case | When the block moves | Expert does | Trigger | Separate demo is saved from |
|---|---|---|---|---|
| Early shift | During the approach | Redirects at once, no empty grasp | The block moved | The shift |
| Late shift | As the fingers close | Misses, reopens, retries | The grasp missed | After the empty close |

- Shift distance: uniform from 7 to 10 cm, random direction, inside the workspace.
- Early shift: when the hand passes a random height from 0.12 to 0.16 m.
- Late shift: on the first step of closing.
- Redraw any shift that would put the block inside the fingers. Check this in the preview.
- Early and late episodes are mixed in equal numbers in both recovery conditions.
- A recovery is complete when the block is lifted to carrying height. B demos end there; C demos continue to the bowl.

## 4. Conditions
Every condition gets the same base set of clean demos (50 episodes), plus N = 6,000 extra frames.

| Condition | Extra N frames |
|---|---|
| A. Control | More clean demos |
| B. Separate | Reaction and fix only, ending at the lift |
| C. Embedded | Full episodes containing the disturbance and fix |

- **Equal frames** is the matching rule. Trim each extra set to exactly N frames and log which episode was cut.
- N = 6,000 is roughly the size of the base set **(estimate from the script, not run)**.
- Report episodes, recoveries and frames per condition. B will contain more recoveries than C.
- Report **estimated human recording time**: frames at 20 Hz plus an assumed reset time per episode. State the assumption. This is an estimate, not a measurement.

## 5. Observation history
ACT normally sees only the current observation, so it cannot remember movement or a miss.

- Train each condition **with history** and **without history**.
- LeRobot's ACT rejects more than one observation step (checked 2026-11-26 in the repository's default branch; latest release v0.7.0). History needs a change to the config, model and data loading. Pin the LeRobot version.
- History is three observations: now, 0.5 s ago and 1 s ago (offsets -20, -10, 0 at 20 Hz). Each includes both cameras and joint positions, with a marker for its time.
- At the start of an episode, repeat the first frame.
- B's first saved frames get the same earlier observations the policy would have at test time. These are context only: they are not training targets and do not count toward N. The data loader must enforce this. Without this, B is tested on history it never trained with.

## 6. Training runs
3 conditions x 2 history settings x 3 seeds = **18 runs**, all with the same settings and step count.

| Setting | Value |
|---|---|
| Batch size | 8 |
| Action chunk | 40 steps (2 s) |
| Steps run before the policy looks again | 10 (0.5 s) |
| Training steps | 50,000, subject to the timing rule below |
| Other settings | LeRobot ACT defaults |

The LeRobot default runs 100 actions before looking again, which is 5 s here and too slow to react to a shift.

**Timing rule:** time 1,000 steps with history on the rented GPU. Use the largest of 80,000, 50,000 or 30,000 steps at which all 18 runs cost $20 or less. If none fits, use 30,000 and cut stages as below. Decide this before seeing any condition's results.

| Stage | Runs | If we stop here |
|---|---|---|
| 1 | Seed 1 of all 6 setups | Complete but preliminary |
| 2 | Seed 2 of all 6 | Better |
| 3 | Seed 3 of all 6 | Planned result |

If money or time runs short, cut the no-history runs first (leaving 9 with history). The history comparison can then no longer be claimed.

## 7. Compute and budget
- **Limit: $30.** $20 for the 18 runs, $10 for the clean-demo policy, timing and reruns.
- **Service:** Vast.ai, one RTX 3090, on-demand, at $0.25 per hour or less. A third-party tracker listed a $0.20 median on 2026-11-16 ([source](https://markaicode.com/pricing/vast-ai-pricing/)); check the live listing. Storage and bandwidth may cost extra.
- At $0.25 per hour, $20 buys 80 hours, about 4.4 hours per run. Whether a run fits is untested.
- Write, debug, collect data and run tests on the Quadro RTX 3000 computer. Train there only if a short run fits in 6 GB, and never split one comparison across different settings.
- Check that the code runs on the rented machine before a long job.
- Copy checkpoints and logs off rented machines, and stop them when idle.
- The repository is public: never commit keys or tokens.
- Vast.ai's terms require a parent or guardian's permission and direct supervision for minors (search summary; read [the terms](https://vast.ai/terms)).

## 8. Testing
| Start type | Role |
|---|---|
| Normal | Check that recovery data does not hurt the basic task |
| Early shift | Trained disturbance |
| Late shift | Trained disturbance |
| Natural failure | Extra test, from the clean-demo policy |

- **Natural failure rule, fixed in advance:** train a clean-demo policy, record how it fails on its own, and use the most common failure type. If the scripted expert succeeds on it less than 95% of the time, take the next most common. Save start states that reproduce it. If it looks like a trained disturbance, say so and do not call it unseen.
- 200 trials per start type for each trained model.
- Same start positions for every model.
- Score success within 20 s of simulated time. Also record failure kind and time taken. Save videos of a sample.

## 9. Analysis
- **Main comparison, fixed in advance:** B against C, with history, on early and late shift starts combined.
- Report each shift type, each start type and each seed separately too.
- Give success rates with 95% Wilson intervals. Trials of one model do not capture training randomness, so show the spread across seeds and do not rely on pooled-trial tests alone.
- History against no history is a secondary comparison.
- A tie, or a win for B or A, is a valid result.

## 10. Order of work and gates

| Step | Work | Pass condition |
|---|---|---|
| 1 | Update `recovery_sim/collect.py` for early and late shifts | Runs in all modes |
| 2 | Check the scripted expert and preview GIFs | At least 98% over 200 episodes per mode; behaviour matches section 3 |
| 3 | Convert to a LeRobot dataset | Loads, with correct frame counts |
| 4 | Add history to ACT | Short training run works with and without it |
| 5 | Time training and estimate cost | Fits section 7, or runs are cut as in section 6 |
| 6 | Train the clean-demo policy | At least 30 of 50 from normal starts |
| 7 | Check disturbances and find the natural failure | Success on each shift type is at least 20 points below normal starts |
| 8 | Apply the timing rule | Step count written here before main runs |
| 9 | Collect, train and test | Logged under this protocol |

Rough time: 8–12 weeks **(guess)**.

## 11. Later: real arm (not secured)
Outside this phase. Revisit after the simulation results.

Possibly an SO-101 leader and follower with a fixed camera and a wrist camera; about $259–$300 for the arm kit (search listings, check at checkout), separate from the $30. It needs its own protocol, including adult supervision, a clamped arm, hands clear while a policy runs, and a power switch within reach.

## 12. Prior work (limited search)
| Work | Relation |
|---|---|
| [EgoRecovery](https://arxiv.org/html/2607.19745) | Separate recovery clips; human video helps; robot data still needed for regrasping. Bimanual, large GPUs, no embedded comparison |
| [RaC](https://arxiv.org/html/2509.07953) | Human takes over during policy rollouts: recover, then correct, then end the episode. Its ablations vary the intervention protocol, not recovery-only against embedded. It argues staged failures may not match the policy's real errors, but does not test this. Two xArm-7 arms |
| [DART](https://arxiv.org/html/1703.09327v2) | Noise injected during full demos, so recovery is embedded. No recovery-only condition. Baselines are plain cloning, DAgger variants and unoptimised noise. Robot grasping: 49% cloning, 79% and 72% with DART |
| [REBOOT](https://arxiv.org/html/2609.22591v1) | Dataset of separate recovery episodes (snippet only) |
| [Hobbyist write-up](https://medium.com/@alexsirk5/teaching-a-robot-arm-to-pick-a-bottle-first-results-with-pi0-5-and-imitation-learning-ba8ffadb2c10) | Informal observation that embedded corrections worked better (pi0.5) |

We found no controlled comparison. As of 2026-11-25, neither RaC nor DART makes it (main text read; appendices only partly). Other papers may exist, and observation history has not been searched.

## 13. What we may claim
"A controlled comparison, in simulation, of two ways of recording recovery data for one simplified gripper and one task." Not "first ever", and not that the same method wins on a real robot or other tasks.

- Contact physics is simplified, and scripted corrections are neater than human ones.
- Staged disturbances may differ from a policy's real errors (the RaC objection). The natural-failure test only partly addresses this.
- Showing that history helps does not by itself show which trigger the policy learned.
