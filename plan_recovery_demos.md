# Plan: how should recovery be recorded for a cheap robot arm?

Status: draft v1, 2026-11-25. Numbers marked **(guess)** are estimates. Nothing here has been built or run.

## 1. Question
With the same recording time, does a low-cost arm recover from mistakes better when it learns from **separate recovery demos** (start at the failed state, fix it) or from **embedded corrections** (make the mistake and fix it inside a full successful demo)?

Hypothesis (write yours down before collecting data): ______ . State which you expect to win and why.

## Simulation version (added 2026-11-26, current plan)
We run the study in MuJoCo first. **Where this section differs from sections 3–10, this section wins.** Code: `recovery_sim/collect.py` (syntax checked only, never run).

| Item | Simulation |
|---|---|
| Robot | Simplified gripper moving in x, y, z. Not an SO-101 |
| Cameras | Simulated top and wrist, 320 x 240 |
| Demonstrator | Scripted expert that reads the true block position |
| Failure | Block jumps 8 cm during the approach; the gripper closes on empty space |
| Separate demos | Saved from just after that empty close |
| Embedded demos | The whole episode, with miss and fix |
| Matching | Equal **frame count** per condition, not recording time |
| Unseen failure test | Block dropped on the way to the bowl (not built yet) |
| Compute | ACT, batch size about 8, on a Quadro RTX 3000 (6 GB), untested |
| Testing | Aim for 200 or more trials per start type, same start positions for all conditions, 3 training seeds per condition |
| Cost and safety | No hardware, no arm safety measures |

**Order of work:** (1) expert succeeds near 100% in all three modes, (2) watch preview GIFs, (3) convert to a LeRobot dataset, (4) train on clean demos and check how it fails, (5) train all conditions, (6) test.

**Make it harder to dismiss:** vary friction, block mass, lighting, camera position and shift size; check a second failure type or task. Decide the final values before the main runs.

**Claim limit:** a simulation result on one simplified gripper. It does not show the same method wins on a real robot. Contact physics is simplified and scripted corrections are neater than human ones.

## 2. Prior work (limited search)
| Work | Relation |
|---|---|
| [EgoRecovery](https://arxiv.org/html/2607.19745) | Separate recovery clips; human video helps; robot data still needed for regrasping. Bimanual, large GPUs, no embedded comparison |
| [RaC](https://arxiv.org/html/2509.07953) | Human takes over during policy rollouts: recover, then correct, then end the episode. Its ablations vary the intervention protocol, not recovery-only against embedded. It argues staged failures may not match the policy's real errors, but does not test this. Two xArm-7 arms |
| [DART](https://arxiv.org/html/1703.09327v2) | Noise injected during full demos, so recovery is embedded. No recovery-only condition. Baselines are plain cloning, DAgger variants and unoptimised noise. Robot grasping: 49% cloning, 79% and 72% with DART |
| [REBOOT](https://arxiv.org/html/2609.22591v1) | Dataset of separate recovery episodes (snippet only) |
| [Hobbyist write-up](https://medium.com/@alexsirk5/teaching-a-robot-arm-to-pick-a-bottle-first-results-with-pi0-5-and-imitation-learning-ba8ffadb2c10) | Informal observation that embedded corrections worked better (pi0.5) |

I found no controlled comparison. **Gate G0 passed (2026-11-25):** neither RaC nor DART makes it (main text read; appendices only partly). Other papers may exist.

**Known objection (from RaC):** staged failures may not look like the failures your policy actually makes. So during G3, record how the clean-demo policy fails on its own and check that your offset resembles one of those failures. State this limit in the write-up.

## 3. Setup
- SO-101 leader and follower, clamped. One fixed camera and one wrist camera.
- Policy: ACT, via LeRobot. Same settings and step count for every run.
- Task: pick up a block and place it in a bowl.
- One failure type, caused the same way every time: **offset grasp** (the block is shifted a fixed distance, about 2 cm **(guess)**, as the gripper approaches). Mark positions on a printed mat.
- Second failure type, used **only for testing**: block dropped partway to the bowl.

## 4. Three conditions
Everyone gets the same base set of 50 clean successful demos, then an equal extra block of recording time T (start with 30 minutes **(guess)**).

| Condition | Extra data recorded in time T |
|---|---|
| A. Control | More clean successful demos |
| B. Separate | Recovery-only demos starting from the offset state |
| C. Embedded | Full demos containing the offset, then the fix |

- Time T includes resets and discarded attempts. Log all of it.
- Also report episode count and frame count per condition, since equal time will give unequal amounts.
- A is essential: without it you can't tell whether recovery data helps or just more data does.
- One operator records everything. Practise first, and rotate between A, B and C in short blocks so skill gains and lighting changes affect all three equally.

## 5. Testing
- Three start types: normal, offset (trained), dropped (unseen).
- 40 trials per condition for the offset test, 20 for each of the others. Interleave conditions in random order.
- Same start positions for all conditions.
- Score: success within a fixed time limit. Also record failure kind and time taken. Film every trial.
- If possible, a second person scores videos without knowing the condition.

## 6. Analysis
- Success rate with 95% Wilson intervals per condition and start type.
- Main comparison, fixed in advance: B against C on offset starts (Fisher's exact test).
- 40 trials per group can reliably show only large gaps, roughly 30 points **(guess)**.
- Trials from one trained model don't capture training randomness. Aim for 3 seeds per condition (9 runs). With 1 seed, call the result preliminary.

## 7. Gates
| Gate | Pass condition |
|---|---|
| G0 | RaC and DART read; question still open (passed 2026-11-25) |
| G1 | Arm teleoperates reliably |
| G2 | Clean-demo policy succeeds at least 6 of 10 from normal starts |
| G3 | The offset makes that policy fail clearly more often (otherwise enlarge it) |
| G4 | All data collected and logged under the protocol |
| G5 | Trials complete |

Rough time: 8–12 weeks **(guess)**.

## 8. Compute and cost
- Arm kit about $259–$300 (search listings, check at checkout), plus a second camera and clamps.
- ACT on Colab or Kaggle T4, or a rented GPU. Time 200 steps first and multiply up.

## 9. Safety
Clamp the arm, keep hands clear while a policy runs (apply the offset only with a stick or a fixed fixture, not fingers), keep the power switch within reach, and have an adult supervisor. No human participants or video of people are needed.

## 10. What you may claim
"A controlled comparison of two ways of recording recovery data on one low-cost arm, one task and one failure type." Not "first ever", and not that it holds for other robots or tasks. A tie is a valid result.
