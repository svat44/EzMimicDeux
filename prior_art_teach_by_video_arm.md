# Prior-art check: teach-by-video low-cost robot arm for small businesses

Date: 2026-11-24. Sources: a full read of the EasyMimic paper (arXiv 2602.11464, HTML version) by a subagent, plus standard web searches. I have not read the other papers named below in full. "I found none" means none surfaced in these searches.

## Verdict
**Moderate-to-low novelty as a method, a real but narrow gap as an applied study.** The core method (teach a cheap arm from human video plus a little robot data) is published. What I did not find is a test with real non-expert workers, realistic capture conditions, and honest compute cost.

## What EasyMimic (ICRA 2026) already does
- **Hardware:** a LeRobot SO100 arm upgraded to 6 joints ("SO100-Plus"), two ordinary RGB cameras (one fixed, one on the wrist), a Nintendo Joy-Con for teleoperation. Claimed total hardware cost **under $300** (no itemised bill).
- **Compute (not in the $300):** a single **NVIDIA RTX 4090** GPU, 5,000 training steps, built on the GR00T N1.5-3B pretrained model, with HaMeR for 3D hand tracking from video and a pre-calibrated hand-to-camera transform.
- **Data:** 20 robot teleoperation trajectories plus 100 human videos per task. Human collection took 8–15 min per task; robot collection 10–40 min.
- **Tasks and results** (10 trials each, scored out of 1.0): pick-and-place 1.00, drawer 0.90, stacking 0.70, language-conditioned 0.90, average 0.88 versus 0.51 for robot-only with 20 trajectories. On unseen objects: 0.65 versus 0.35.
- **Caveats:** one average per row with no error bars; four toy tasks; human videos came from the **same fixed camera** as the robot data, not a phone, though the paper says phones are the motivation; **no non-expert user study**; no code-release or licence statement in the text (a project website is linked, not checked).

## Related work found
- HumanEgo: egocentric smart-glasses video, about 30 minutes of human video ([page](https://humanego-ai.github.io/)).
- Phantom (2025): trains from human video with the arm replaced by a rendered robot.
- VideoManip (CMU) and others on human-video-to-robot transfer.
- HRI studies on non-experts teaching robots, none on a low-cost arm in a small-business or low-income setting: everyday users training before teaching improved demonstrations ([ACM 2025](https://dl.acm.org/doi/10.1145/3737892)); a comparison of kinesthetic, joystick and gesture teaching ([arXiv 2605.28033](https://arxiv.org/pdf/2605.28033)); a home study with care providers using a commercial JACO arm ([arXiv 2608.25196](https://arxiv.org/html/2608.25196v1)); a 2021 study where non-experts struggled to give fast demonstrations.
- SME robot-adoption literature names cost and integration skills as barriers, but I found nothing on teaching by demonstration in low- and middle-income settings.

## What I did not find (candidate gaps)
1. **A user study with real non-expert workers** teaching a cheap arm from video, in a real workplace.
2. **Realistic capture:** phone videos in cluttered, changing light and backgrounds. EasyMimic used a fixed lab camera.
3. **Honest compute cost:** what does it take to train on a free or consumer GPU, or a smaller model? (SmolVLA is built for affordable hardware ([paper](https://arxiv.org/pdf/2506.01844)); I haven't checked its fit.)
4. **Independent replication** with error bars across many trials.
5. **Tasks that matter in an emerging-market workplace** (packing, sorting, stacking), measured against how long a human takes.

## Narrowed project claim (unverified novelty)
"Can people with no robotics training teach a sub-$500 arm a useful task by showing it on video, and what does it cost in time, data and compute? A replication and user study of EasyMimic-style learning with phone video, on consumer hardware."

## Feasibility and risks
- **Hardware:** SO-101-class arm is listed at about $130–$500 depending on source; its reach is about 413 mm and payload about 0.5 kg per one review ([arXiv 2606.03392](https://arxiv.org/pdf/2606.03392)). Only light, small tasks.
- **Compute and skill:** robot learning is hard to get working. Expect many failed runs. You need GPU access.
- **Human participants:** a user study means people recorded on video. That needs consent, adult supervision and possibly ethics review. Use adults and keep faces out of frame.
- **Results may not replicate.** The published numbers come from one lab and 10 trials per task.
- **Not a breakthrough.** The finding would be about usability, cost and reliability.

## Next step options
1. Check EasyMimic's project page for code and data (it may make replication cheap or impossible).
2. Price a minimal setup and check free GPU options.
3. Decide whether you can recruit adults for a small user study.
