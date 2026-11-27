# Who Gets to Teach? Demonstrator Differences in Teaching a Low-Cost Robot Arm by Video

Status: draft v1, 2026-11-24. Built on `prior_art_teach_by_video_arm.md`. Costs and times marked **(guess)** are my estimates; marked **[verify]** need checking. I have not checked prior art on the main question (section 1).

## 1. The project in one paragraph
EasyMimic (ICRA 2026) taught a cheap open arm from human video plus a few robot demonstrations, but it never asked **who** recorded the videos or whether the hand tracker works for everyone. This project (a) reproduces a simple version of that pipeline on an SO-101 arm, then (b) measures how hand-tracking quality and robot success change across different demonstrators (hand size, skin tone, atypical or limited hand movement). Question: **does teaching by video work equally well for everyone, and if not, who gets left out?**

What you may claim: a replication on different hardware, and the first measured effect of demonstrator differences, **if** a prior-art check confirms nobody did it. What you may not claim: inventing learning from human video.

## 2. Stages and gates (stop at a gate if it fails)

| Phase | Weeks (guess) | Goal | Gate to pass |
|---|---|---|---|
| 0 Decide | 1 | Budget, GPU access, adult supervisor, participant plan, prior-art check on the demonstrator question | G0: you have a supervisor, a GPU route and a budget |
| 1 Arm and cameras | 2–3 | Assemble or unbox SO-101, calibrate, mount two cameras, teleoperate | G1: arm teleoperates smoothly and repeatably for 10 minutes |
| 2 Baseline policy | 3–4 | Record about 50 robot demonstrations of one task, train SmolVLA, test | G2: at least 5 of 10 trials succeed on the simple task |
| 3 Human-video pipeline | 4–6 | Record human videos, extract hand motion with HaMeR (or Fast-HaMeR), map to arm actions, co-train | G3: co-training matches or beats robot-only over 10 trials each |
| 4 Tracker-quality study | 2–3 | Record many demonstrators, measure tracking quality | G4: at least 12 consenting adults recorded |
| 5 Policy study | 3–4 | Train policies from a subset of demonstrators, compare success | G5: at least 6 policies trained and tested |
| 6 Write-up and release | 2 | Report, code, consented data | Release |

Total about **16–22 weeks (guess)**. Phase 4 can start as soon as the hand-tracking pipeline runs, even before Phase 3 finishes.

**If a gate fails:**
- G2 fails: fix cameras, data quality or task difficulty before going on; try an easier task.
- G3 fails after three honest attempts: report "I couldn't reproduce the benefit with this hardware" as a replication result, then do only the tracker-quality study (Phase 4), which doesn't need the robot.

## 3. Phase details

**Phase 0 — Decide**
- Adult supervisor and a safe, clamped work area.
- GPU route: a rented GPU (Hugging Face Jobs or a cloud provider) or a borrowed machine. SmolVLA was reported to need about 10–16 GB of video memory ([guide](https://openelab.io/blogs/learn/how-to-fine-tune-smolvla-on-so-101-with-lerobot)). EasyMimic's 3-billion-parameter path needs about 25 GB, so skip it at first.
- Price the cheapest working setup before buying anything.
- Run a prior-art check on "demonstrator diversity in learning from human video".

**Phase 1 — Arm and cameras**
- SO-101 (SO-ARM101), not the deprecated SO-100. Confirm whether the kit includes both a leader and a follower arm **[verify]**.
- Two USB cameras (fixed overhead, plus wrist). Clamp everything.
- Install LeRobot per its current docs. Calibrate. Record a teleoperation test.
- Log: arm model, firmware, camera models, lighting, room.

**Phase 2 — Baseline policy**
- One simple task: pick up an object and place it in a bowl.
- Record about 50 robot demonstrations with the leader arm. The SmolVLA recipe suggests 50 episodes for one task.
- Train and test 10 trials. Write down every setting so it can be rerun.

**Phase 3 — Human-video pipeline**
- Record human demonstrations of the same task with the same fixed camera (as EasyMimic did), then later with a handheld phone as a stretch.
- Extract 3D hand motion with HaMeR (Python 3.10, example CUDA 11.7) or the faster distilled version. Map hand motion to arm end-effector poses via a calibrated transform. **EasyMimic's calibration details are unpublished**, so expect to design this yourself. Check the authors' GitHub code folder first **[verify]**.
- Check by replaying extracted trajectories on the arm before any training.
- Train with human data plus about 10–20 robot demonstrations. Compare with robot-only, 10 trials each. Report how many trials, with ranges.

**Phase 4 — Tracker-quality study (no GPU training needed)**
- Recruit at least 12 adult volunteers with varied hand sizes and skin tones. If you can recruit people with limited hand movement or tremor, do it only with their informed consent and extra care.
- Each person performs the same task about 20 times in front of the fixed camera (about 5 minutes).
- Measure, per person: fraction of frames with a confident hand detection; frame-to-frame jitter; and agreement with a reference where possible (for example, fingertip positions on a marked board). Also track occlusion and lighting.
- This is cheap, fast and may be your cleanest result.

**Phase 5 — Policy study**
- Choose about 3 demonstrators with the best tracking and 3 with the worst. Train a policy from each person's videos plus the same robot demonstrations. Test each policy over 10 trials (more if you can).
- Compare success scores. With 10 trials per policy, differences below about 20 percentage points will be hard to tell from luck **(guess)**. Report ranges, not just means.

## 4. Experiment design rules
- Fix all settings (task, camera positions, lighting, number of demonstrations, training steps) before running anything.
- Randomise test order, and have someone other than the person who trained the policy score the trials if you can.
- Pre-register the plan and metrics publicly (for example on OSF) before Phase 4 data are analysed.
- Keep a lab log: date, what changed, what failed.
- Report negative results.

## 5. Safety and ethics
**Arm safety**
- Small servo arms can pinch fingers and snap cables. Clamp the base, keep hands clear during autonomous runs, route cables, and know how to cut power fast (a power switch or unplug within reach).
- An adult is present during all robot runs.

**People on video**
- Adults only. Written informed consent, saying what is recorded, how it is used, whether data are shared, and that they can withdraw.
- Frame the camera on hands and the work area, not faces. Remove or blur anything identifying. Store videos securely. Do not publish raw video without explicit consent.
- Ask your supervisor or school or fair whether an ethics review is required for human participants **[verify]**.
- Treat any data about disability or health as sensitive. Collect only what you need.

## 6. Budget (placeholders; check current prices)
| Item | Notes |
|---|---|
| SO-101 arms | About $300–$600 depending on kit and whether you need leader and follower (Seeed lists $189–$299 tiers) **[verify]** |
| USB cameras | Two; the Pro kit includes one |
| GPU time | Rented or borrowed. 3–6 hours per SmolVLA run on a mid-range cloud GPU in one guide. Phase 5 with 6 runs is 18–36 hours **(guess)** plus failed runs |
| Misc | Clamps, lighting, mat, objects, cables |

## 7. What I can help with now
- Scripts for data collection, tracker-quality metrics and plots.
- Training configs, debugging and analysis (you set the question).
- Consent form wording to review with your supervisor.
- Pre-registration text.

## 8. Questions to settle first
1. Who supervises, and where will the arm live?
2. GPU: do you have one, can you borrow one, or must you rent? What budget?
3. Can you recruit 12 or more adult volunteers?
4. Do you want the robot part at all, or would the tracker-quality study alone (Phase 4) be enough? It needs no arm and no GPU for training.
