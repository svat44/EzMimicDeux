# Rohab demo review (screen recording, 85 s, Redmi 7A, 720x1440)

**How I reviewed it:** I pulled a frame every 2.5 s (35 frames) and read the app source in `C:\Users\delib\rohab\lib` to explain what I saw. I did not run the app myself.

**Tags:** **[seen]** = visible in the recording. **[code]** = found in the source, not visible in the recording. **[verify]** = I'm not sure, check on the phone.

**What I can't judge from frames:** audio, haptics, touch gestures, exact timing and lag. I can't tell what the person was *trying* to do between frames, so "0 rounds" may be partly user error. The app still gave no hint why.

---

## About "I don't even see the DeepMind stuff"

The hand tracking is Google's MediaPipe Hand Landmarker. It runs, but **nothing is drawn from it**. There is no `CustomPaint` or landmark drawing anywhere in `lib/` [code]. The preview is the plain camera plus a decorative green rectangle. The only sign that tracking is working is a rep count that goes up, and in this recording it never did (0 of 5 rounds for the whole time). So you see no skeleton, no dots on the fingertips, and no hint that the hand was detected. This is the single biggest gap for a demo.

---

## A. Blocks use or hides what matters

**1. Live feedback is below the fold on the exercise screen. [seen + code]**
Frames t=27.5–72.5 show only the camera, "0 of 5 rounds" and "End exercise". The code puts a hint line, a progress bar, the "Hold your hand inside the frame" warning and the "Wrist moved. That one did not count." warning *under* the rep count, in a scrolling list (`camera_layout.dart`, `camera_exercise_flow.dart` `_ExerciseReadout`). On this phone they are off-screen. So the user never sees "Next: index finger", never sees the bar, and never sees that the hand was lost (t=72.5: hand has left the frame and nothing says so).

**2. Zero rounds in 25 s and again in 17 s, with no explanation. [seen]**
Unknown cause: it could be the user doing the wrong gesture (frames t=27.5–50 show open hand and fist, which is the calibration gesture, not finger touches), tracking at about 9 fps, or the touch rule being missed. Either way the app only says "Set ended. 0 rounds. Nothing was saved." with no reason.

**3. Calibration flows straight into counting with no "get ready". [seen]**
t=25 "Now make a fist, 1 s" then t=27.5 "0 of 5 rounds". The instruction on screen right before counting starts is "make a fist", the last thing the user sees, and the real instruction ("touch thumb to index, then middle...") is not repeated. That likely explains the fists at t=30–50.

**4. Finger touches doesn't need the open/fist calibration, but forces it. [code]**
`_Touches` counts thumb-to-fingertip distance only. The range from calibration isn't used for counting. It costs about 7 s and tells the user to do a different movement from the exercise.

**5. No rep feedback. [code]**
`onRepCounted` exists but the flow never passes it, and there is a `TODO(audio)`. No sound, vibration or flash when a touch or rep counts. The user must watch a number that's cut off (see 1).

**6. Text and controls clipped with no scroll cue. [seen]**
- t=20: the calibration countdown number is cut off at the bottom (only the top of the digit shows).
- t=10: the set summary ends mid-sentence ("Camera measurements are").
- t=55: instruction step 2 stops at "Touch your thumb to the tip".
- t=75: pain scale shows only 0, 1, 2, 3 with blank space below. The code has 0–10 in a wrap of four per row, so rows 2–3 should show. **[verify]** it may be a mid-transition frame, but the code comment says "all of 0-10 fits above the buttons", which isn't true here.
- t=12.5: the plan screen shows the heading and a bar, then blank space, then Start. The list of planned exercises isn't visible. **[verify]**

---

## B. High-impact usability problems

**7. The header eats the screen. [seen]**
Status bar + banner (about 15% of the height) + "Rohab" + big screen title + bottom nav leave roughly half the screen for content on a 720x1440 phone. This is the root cause of most clipping above.

**8. The preview jumps size. [seen]** 40% of the height during hand check and calibration, 55% during the exercise (t=25 → 27.5). The camera view resizes mid-flow.

**9. The preview shows less than the camera sees. [seen + code]** `BoxFit.cover` in a wide box crops the top and bottom of the portrait camera image. At t=57.5–60 the fingers go above the preview edge. The green rectangle is decorative only, not the tracking area, so "Hold your hand inside the frame" refers to something that doesn't match what the tracker uses.

**10. "Photo to come" is shown to users. [code]** `PhotoSlot` is a literal placeholder box on every instruction screen. No assets exist except fonts and the model. The caption says "right hand shown" with no photo. The instruction page also doesn't say where to put the phone, how far away, or what lighting to use.

**11. Camera restarts every set. [seen + code]** "Starting the camera." is a blank page with only "Back" (t=15, t=57.5), taking 2.5 s or more. The tracker and model are created again every set.

**12. Slow tracking on this phone. [seen]** The debug overlay shows 7–11 fps and 56 dropped frames after about 25 s (roughly 2 a second). With a 200 ms touch hold and the lowest camera resolution (`ResolutionPreset.low`), quick touches can be missed.

**13. Stale and misleading result screens. [seen]**
- t=10: tapping Exercises showed an old "set summary" (5° to 257°, "Your later movements were smaller") from a previous run.
- t=52.5: a 0-rep set still shows "Range of motion: 233°", "Rest for 60 s." and "Next set". The 233° came from the open/close movement, not from the exercise, and nothing was saved.

**14. The pain check is a trap. [code]** After "Finish for today" the "after" pain screen has no Back or Skip and Save is disabled until a number is picked, even if no reps were done (t=72.5 → 75).

---

## C. Wrong or inconsistent numbers and wording

**15. "Finger bend 257°" is a sum of three joints, not a bend. [seen + code]** `JointAngles.closure` is the mean over four fingers of (MCP + PIP + DIP). A reader sees "257° (most closed)" and thinks one joint bent 257°. Clinically this is total active motion, and it should be labelled that way. The comment in the controller also says "mean MCP + PIP + DIP", which is wrong.

**16. The accuracy note contradicts the app's own science notes. [seen + code]** The screen says "about 10° either way per joint". The source comment says errors run "from about 4 to over 20 degrees", worst at the PIP, and that's per joint. A total over three joints can be off by far more than 10°.

**17. "0 of 120 today" mixes units. [seen + code]** Rounds count double toward the plan total (`weight = 1 / setSizeFactor`), so 4 sets of 5 touch rounds counts as 40, not 20. The screen gives no unit and no explanation.

**18. Two different "calibrations". [seen]** The Calibrate tab (glove muscle signal, "Last calibrated: Not yet") and the camera range step inside exercises share a name. A user who calibrated through the camera still sees "Not yet".

**19. "Connected / Ready" is a simulated glove. [seen + code]** The README says the glove is `MockGloveService`. Nothing in the UI says "demo" or "simulated". A viewer would assume hardware is attached.

**20. Unfinished copy in Settings. [seen]** "Session length and reminders come in a later update." The PIN screen's title is still "Settings", the field has no label, and the explanation is the only text.

**21. Empty Progress page. [seen]** Only a description line, no empty-state message or chart. A first-time user can't tell whether it's loading or empty.

---

## D. Experiment and measurement validity

**22. Finger touches counts closeness, not contact. [code]** A touch is the thumb tip within 0.25 palm widths of a fingertip (roughly 2 cm) for 200 ms. A single RGB camera has weak depth, so "touching" can be a thumb hovering near the finger. It can also miss real touches when tracking is noisy at 9 fps.

**23. Wrist-compensation rule can silently discard reps. [code]** `WristMonitor` takes the first 10 frames of a set as the reference direction and flags every rep once the hand tilts more than 25° from it. If the hand is moving at the start (as at t=27.5), the reference is wrong and every later rep may be discarded. The "Wrist moved" message that explains this is the one hidden in item 1. The same limit is used for exercises (grip a cup, pinch) where the wrist legitimately moves.

**24. Palm-facing exercises measure joint angles poorly. [code]** The touches and spread exercises say "palm facing the phone", but the angle maths is about the palm axis and is weakest when fingers bend toward the camera. The code comment warns about PIP errors over 20°. The summary still reports whole degrees.

**25. Range calibration is only 3 s per pose. [code]** One effort is taken as the user's "best", so a weak attempt shrinks the range and makes later reps look easier by percentage. The app saves degrees for open/close, which is good, but percentages (spread, counting thresholds) are relative to that one 3 s window.

**26. Fatigue and "smaller movements" messages rest on very few reps. [code]** Sets are 5 rounds or 10 reps. The summary says "Your later movements were smaller" from that few swings. **[verify]** thresholds in `movement_quality.dart`.

---

## E. Smaller annoyances

- Banner text is cut off: "Glove not conne…" (t=0–2.5).
- A huge red STOP button on every screen, always active, with no confirmation and no visible result when pressed. Intentional, but it takes about 10% of the height and does nothing visible when the glove is a mock.
- Debug "fps · dropped" label covers the corner of the preview (debug builds only).
- Dim gray secondary labels ("Reps this session", "Pressure") are low contrast, which matters for users with weak vision.
- "Back" and "Cancel" are plain text buttons next to the big primary button, easy to mis-tap with one hand while the other hand is in front of the camera.
- No "too dark" or "hand too close/far" detection: at t=17.5 the preview is nearly black for a moment.
- Which hand isn't asked in this flow, only "right hand shown" in the caption. **[verify]** against the baseline step.
- Rest is 60 s for every exercise, even after a 0-rep set.

---

## Suggested fix order

1. Draw the hand landmarks on the preview (also show the target fingertip for touches).
2. Put the rep count, the "Next: …" hint and the hand-lost / wrist-moved messages *on* the preview, not under it.
3. Shrink the header (merge title and wordmark, make STOP smaller) to stop the clipping.
4. Add a "Get ready: touch thumb to index finger" screen between calibration and counting, and skip the open/fist calibration for Finger touches.
5. Add a haptic or sound on every counted rep.
6. Hide range, rest prompt and "Next set" on 0-rep sets, and say why nothing counted.
7. Fix wording: "total finger bend", the ±10° claim, "demo glove".
8. Replace "Photo to come" with real images or remove it.
9. Test touch detection on real contact vs hovering before trusting the count.

I haven't changed any code. Say which of these you want fixed first.
