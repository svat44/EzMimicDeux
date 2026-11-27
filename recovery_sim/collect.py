"""Collect scripted demonstrations for the recovery-demo experiment.

A simplified gripper (moves in x, y, z) puts a block into a bowl in MuJoCo.
Modes:
  clean     - no disturbance, whole episode saved
  embedded  - block is shifted during the approach (early or late), whole episode saved
  separate  - same shifts; saved frames are the training window plus up to CONTEXT
              context frames before it (train=False)

Examples:
  python collect.py --mode clean --frames 2000 --no-images     (physics check)
  python collect.py --mode embedded --frames 600 --preview     (writes GIFs)
"""
import argparse
import json
import math
from pathlib import Path

import mujoco
import numpy as np

XML = """
<mujoco>
  <option timestep="0.002" integrator="implicitfast" cone="elliptic" impratio="10"/>
  <visual><global offwidth="640" offheight="480"/></visual>
  <worldbody>
    <light pos="0 0 1.2" dir="0 0 -1"/>
    <geom name="table" type="plane" size="0.5 0.5 0.1" rgba="0.75 0.72 0.65 1"/>
    <camera name="top" pos="0 -0.45 0.55" xyaxes="1 0 0 0 0.77 0.64"/>

    <body name="hand" pos="0 0 0.25" gravcomp="1">
      <joint name="x" type="slide" axis="1 0 0" range="-0.3 0.3" damping="40"/>
      <joint name="y" type="slide" axis="0 1 0" range="-0.3 0.3" damping="40"/>
      <joint name="z" type="slide" axis="0 0 1" range="-0.18 0.1" damping="40"/>
      <geom type="box" size="0.025 0.055 0.012" mass="0.3" rgba="0.25 0.25 0.3 1"/>
      <camera name="wrist" pos="0.09 0 0.03" xyaxes="0 1 0 -0.77 0 0.64"/>
      <body name="left" pos="0 0.04 -0.05" gravcomp="1">
        <joint name="left" type="slide" axis="0 -1 0" range="0 0.032" damping="5"/>
        <geom type="box" size="0.01 0.005 0.025" mass="0.03" friction="1.5 0.02 0.001" condim="4" rgba="0.1 0.1 0.1 1"/>
      </body>
      <body name="right" pos="0 -0.04 -0.05" gravcomp="1">
        <joint name="right" type="slide" axis="0 1 0" range="0 0.032" damping="5"/>
        <geom type="box" size="0.01 0.005 0.025" mass="0.03" friction="1.5 0.02 0.001" condim="4" rgba="0.1 0.1 0.1 1"/>
      </body>
    </body>

    <body name="block" pos="-0.08 0 0.02">
      <freejoint name="block"/>
      <geom type="box" size="0.02 0.02 0.02" mass="0.05" friction="1.5 0.02 0.001" condim="4" rgba="0.85 0.15 0.1 1"/>
    </body>

    <body name="bowl" pos="0.16 0 0">
      <geom type="box" size="0.065 0.065 0.003" pos="0 0 0.003" rgba="0.15 0.35 0.8 1"/>
      <geom type="box" size="0.005 0.07 0.022" pos="0.065 0 0.022" rgba="0.15 0.35 0.8 1"/>
      <geom type="box" size="0.005 0.07 0.022" pos="-0.065 0 0.022" rgba="0.15 0.35 0.8 1"/>
      <geom type="box" size="0.07 0.005 0.022" pos="0 0.065 0.022" rgba="0.15 0.35 0.8 1"/>
      <geom type="box" size="0.07 0.005 0.022" pos="0 -0.065 0.022" rgba="0.15 0.35 0.8 1"/>
    </body>
  </worldbody>
  <actuator>
    <position joint="x" kp="500" ctrlrange="-0.3 0.3"/>
    <position joint="y" kp="500" ctrlrange="-0.3 0.3"/>
    <position joint="z" kp="500" ctrlrange="-0.18 0.1"/>
    <position joint="left" kp="300" ctrlrange="0 0.032"/>
    <position joint="right" kp="300" ctrlrange="0 0.032"/>
  </actuator>
</mujoco>
"""

HAND_Z0 = 0.25          # world height of the hand when joint z = 0
GRASP_Z = 0.08          # hand height for grasping
HIGH_Z = 0.19           # hand height for carrying
DROP_Z = 0.13           # hand height for releasing over the bowl
BOWL = np.array([0.16, 0.0])
OPEN, CLOSED = 0.0, 0.026
SIM_STEPS = 25          # 25 x 0.002 s = one 20 Hz control step
SPEED = 0.01            # metres per control step
MODES = ("clean", "embedded", "separate")
SHIFT_MIN, SHIFT_MAX = 0.07, 0.10       # shift distance, metres, uniform
WORKSPACE = ((-0.18, 0.04), (-0.13, 0.13))  # block centre x and y range (strict)
TRIGGER_MIN, TRIGGER_MAX = 0.12, 0.16   # early trigger: hand world z, uniform
CLEARANCE = 0.002                       # min block-to-hand/finger distance after a shift
REDIRECT_Z = 0.14                       # early redirect height floor
REDIRECT_CLEAR_Z = 0.125                # hand z at which fingers clear the block top; sideways travel starts above this
CARRY_BLOCK_Z = 0.12                  # block z that counts as lifted to carrying height
CONTEXT = 20                            # max context frames before a separate training start
GRIP_EMPTY = 0.022                      # closed on empty space above this finger joint value
SHIFT_DISTANCE_DRAWS = 20               # max distance draws per shift
SHIFT_ANGLE_DRAWS = 1000                # max angle draws per distance


def make_model():
    return mujoco.MjModel.from_xml_string(XML)


def episode_rng(seed, mode, attempt):
    return np.random.default_rng([seed, MODES.index(mode), attempt])


def in_workspace(xy):
    (x0, x1), (y0, y1) = WORKSPACE
    return bool(x0 < xy[0] < x1 and y0 < xy[1] < y1)


class Episode:
    on_substep = None

    def __init__(self, model, rng, renderer=None, shift_type="none"):
        if shift_type not in ("none", "early", "late"):
            raise ValueError(f"bad shift_type: {shift_type}")
        self.shift_type = shift_type
        self.model, self.rng, self.renderer = model, rng, renderer
        self.data = mujoco.MjData(model)
        self.block_adr = model.joint("block").qposadr[0]
        start = rng.uniform([-0.14, -0.09], [-0.02, 0.09])
        self.data.qpos[self.block_adr:self.block_adr + 2] = start
        self.target = np.array([0.0, 0.0, HIGH_Z])
        self.grip = OPEN
        self.data.qpos[2] = HIGH_Z - HAND_Z0
        self._apply()
        self.frames = []
        self.shift_frame = None
        self.block_body = model.body("block").id
        hand_bodies = [model.body(n).id for n in ("hand", "left", "right")]
        self.block_geoms = [g for g in range(model.ngeom) if model.geom_bodyid[g] == self.block_body]
        self.hand_geoms = [g for g in range(model.ngeom) if model.geom_bodyid[g] in hand_bodies]
        self.block_dof = model.joint("block").dofadr[0]
        for _ in range(200):
            mujoco.mj_step(model, self.data)
            if self.on_substep is not None:
                self.on_substep()
        self.block_before = None
        self.block_after = None
        self.trigger_z = rng.uniform(TRIGGER_MIN, TRIGGER_MAX) if shift_type == "early" else None

    def _apply(self):
        x, y, z = self.target
        self.data.ctrl[:] = [x, y, z - HAND_Z0, self.grip, self.grip]

    def block(self):
        return self.data.qpos[self.block_adr:self.block_adr + 3].copy()

    def hand_z(self):
        return float(self.data.qpos[2] + HAND_Z0)

    def _block_contact(self):
        blk, hand = set(self.block_geoms), set(self.hand_geoms)
        for i in range(self.data.ncon):
            c = self.data.contact[i]
            if (c.geom1 in blk and c.geom2 in hand) or (c.geom2 in blk and c.geom1 in hand):
                return True
        return False

    def block_touches_hand(self):
        if self._block_contact():
            return True
        fromto = np.zeros(6)
        for b in self.block_geoms:
            for h in self.hand_geoms:
                d = mujoco.mj_geomDistance(self.model, self.data, b, h, CLEARANCE * 10, fromto)
                if d < CLEARANCE:
                    return True
        return False

    def _do_shift(self):
        before, after = self.shift_block()
        self.shift_frame = len(self.frames)
        self.block_before, self.block_after = before, after

    def step(self):
        """Record what the policy would see and do, then advance one control step."""
        if self.shift_type == "late" and self.shift_frame is None and self.grip == CLOSED:
            self._do_shift()
        frame = {
            "state": self.data.qpos[:5].astype(np.float32).copy(),
            "action": np.array([*self.target, self.grip], dtype=np.float32),
            "block_pos": self.block().astype(np.float32),
            "touch": self._block_contact(),
        }
        if self.renderer:
            for cam in ("top", "wrist"):
                self.renderer.update_scene(self.data, camera=cam)
                frame[cam] = self.renderer.render().copy()
        self.frames.append(frame)
        self._apply()
        for _ in range(SIM_STEPS):
            mujoco.mj_step(self.model, self.data)
            if self.on_substep is not None:
                self.on_substep()
        if self.shift_type == "early" and self.shift_frame is None and self.hand_z() <= self.trigger_z:
            self._do_shift()

    def move(self, xy, z, noise=0.0015, stop_on_shift=False):
        """Move the target to (xy, z). Returns False if stop_on_shift and a shift fired during this move."""
        goal = np.array([xy[0], xy[1], z])
        shifted_before = self.shift_frame is not None
        while np.linalg.norm(goal - self.target) > 1e-6:
            delta = goal - self.target
            dist = np.linalg.norm(delta)
            speed = SPEED * self.rng.uniform(0.8, 1.2)
            if dist <= speed:
                self.target = goal.copy()
            else:
                self.target = self.target + delta / dist * speed + self.rng.normal(0, noise, 3)
            self.step()
            if stop_on_shift and not shifted_before and self.shift_frame is not None:
                return False
        for _ in range(4):
            self.step()
            if stop_on_shift and not shifted_before and self.shift_frame is not None:
                return False
        return True

    def set_grip(self, value, steps=10):
        self.grip = value
        for _ in range(steps):
            self.step()

    def shift_block(self):
        before = self.block()
        old = before[:2]
        # Draw the distance once, then redraw only the angle; a new distance is drawn
        # only when no angle works for the current one. This keeps distance uniform.
        for _ in range(SHIFT_DISTANCE_DRAWS):
            dist = self.rng.uniform(SHIFT_MIN, SHIFT_MAX)
            for _ in range(SHIFT_ANGLE_DRAWS):
                angle = self.rng.uniform(0, 2 * np.pi)
                new = old + dist * np.array([np.cos(angle), np.sin(angle)])
                if not in_workspace(new):
                    continue
                self.data.qpos[self.block_adr:self.block_adr + 2] = new
                self.data.qvel[self.block_dof:self.block_dof + 6] = 0
                mujoco.mj_forward(self.model, self.data)
                if not self.block_touches_hand():
                    return before, self.block()
        raise RuntimeError("no clear shift found within the draw caps")

    def run(self, mode):
        """Run the scripted expert to the end (bowl delivery). Returns the result dict (see contract)."""
        if mode not in MODES:
            raise ValueError(f"bad mode: {mode}")
        if mode == "clean" and self.shift_type != "none":
            raise ValueError("clean mode requires shift_type='none'")
        if mode != "clean" and self.shift_type == "none":
            raise ValueError(f"{mode} mode requires a shift_type of 'early' or 'late'")

        old_xy = self.block()[:2]
        self.move(old_xy, HIGH_Z)
        if self.shift_type == "none":
            self.move(old_xy, GRASP_Z)
        elif self.shift_type == "early":
            # Descend; the shift fires as the hand passes trigger_z and the move stops.
            if self.move(old_xy, GRASP_Z, stop_on_shift=True):
                raise RuntimeError("early shift did not fire during descent")
            # Redirect at once: the next recorded action already heads for the new xy.
            # The hand may still be falling, so lift the target first and creep sideways
            # until the fingers clear the block top; then travel normally.
            new_xy = self.block()[:2]
            creep = SPEED / 5
            for _ in range(200):
                if self.hand_z() >= REDIRECT_CLEAR_Z:
                    break
                delta = new_xy - self.target[:2]
                dist = np.linalg.norm(delta)
                if dist > 0:
                    self.target[:2] = self.target[:2] + delta / dist * min(dist, creep)
                self.target[2] = REDIRECT_Z
                self.step()
            else:
                raise RuntimeError("early redirect did not clear the block")
            self.move(new_xy, REDIRECT_Z)
            self.move(new_xy, GRASP_Z)
        else:  # late
            # Close on the old xy; the shift fires on the first closed step.
            # The expert finishes closing on empty space, reopens, then retries.
            self.move(old_xy, GRASP_Z)
            self.set_grip(CLOSED)
            self.set_grip(OPEN)
            new_xy = self.block()[:2]
            self.move(old_xy, HIGH_Z)
            self.move(new_xy, HIGH_Z)
            self.move(new_xy, GRASP_Z)
        self.set_grip(CLOSED, 14)
        grabbed_xy = self.target[:2].copy()
        self.move(grabbed_xy, HIGH_Z)
        self.move(BOWL, HIGH_Z)
        self.move(BOWL, DROP_Z)
        self.set_grip(OPEN, 14)
        self.move(BOWL, HIGH_Z)
        pos = self.block()
        success = bool(np.all(np.abs(pos[:2] - BOWL) < 0.06) and pos[2] < 0.06)

        def _nan3(v):
            return np.full(3, np.nan) if v is None else np.asarray(v, dtype=float)

        return {
            "success": success,
            "frames": self.frames,
            "shift_type": self.shift_type,
            "shift_frame": -1 if self.shift_frame is None else int(self.shift_frame),
            "trigger_z": float("nan") if self.trigger_z is None else float(self.trigger_z),
            "block_before": _nan3(self.block_before),
            "block_after": _nan3(self.block_after),
        }


def select(result, mode):
    """Saved arrays and metadata for one successful episode (see contract "Saved episode"), None if not success."""
    if mode not in MODES:
        raise ValueError(f"bad mode: {mode}")
    if not result["success"]:
        return None
    frames = result["frames"]
    n = len(frames)
    idx = np.arange(n)
    grip = np.array([f["action"][3] for f in frames], dtype=np.float64)
    block_z = np.array([f["block_pos"][2] for f in frames], dtype=np.float64)
    shift_type = result["shift_type"]
    shift_full = int(result["shift_frame"])

    if mode == "separate":
        if shift_type == "early":
            train_start = shift_full
        else:
            reopened = np.nonzero((idx > shift_full) & (np.abs(grip - OPEN) < 1e-6))[0]
            if reopened.size == 0:
                raise RuntimeError("late episode never reopened after the empty close")
            train_start = int(reopened[0])
        closed = grip > (OPEN + CLOSED) / 2
        closes = np.nonzero(closed & ~np.r_[False, closed[:-1]])[0]
        if closes.size == 0:
            raise RuntimeError("episode has no close")
        final_close = int(closes[-1])
        lifted = np.nonzero((idx >= max(train_start, final_close)) & (block_z >= CARRY_BLOCK_Z))[0]
        if lifted.size == 0:
            raise RuntimeError("block never reached carrying height after the final close")
        train_end = int(lifted[0])
        start = max(0, train_start - CONTEXT)
        stop = train_end + 1
    else:
        train_start, train_end = 0, n - 1
        start, stop = 0, n

    window = range(start, stop)
    keys = ["state", "action", "block_pos", "touch"]
    if "top" in frames[0]:
        keys += ["top", "wrist"]
    out = {k: np.stack([frames[i][k] for i in window]) for k in keys}
    out["state"] = out["state"].astype(np.float32)
    out["action"] = out["action"].astype(np.float32)
    out["block_pos"] = out["block_pos"].astype(np.float32)
    out["touch"] = out["touch"].astype(bool)
    if "top" in out:
        out["top"] = out["top"].astype(np.uint8)
        out["wrist"] = out["wrist"].astype(np.uint8)
    out["train"] = np.arange(start, stop) >= train_start
    out["shift_type"] = np.array(shift_type)
    out["shift_frame"] = np.int64(-1 if shift_full < 0 else shift_full - start)
    out["shift_frame_full"] = np.int64(shift_full)
    out["trigger_z"] = np.float64(result["trigger_z"])
    out["block_before"] = np.asarray(result["block_before"], dtype=np.float64)
    out["block_after"] = np.asarray(result["block_after"], dtype=np.float64)
    out["train_start"] = np.int64(train_start)
    out["train_end"] = np.int64(train_end)
    return out


def _plain(v):
    """Convert numpy and NaN/inf values to plain JSON-safe Python (NaN and inf become None)."""
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, np.ndarray):
        return _plain(v.tolist())
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def collect(mode, frames, seed=0, out="data", images=True, preview=False):
    """Collect saved episodes until `frames` train frames are filled. Writes files; returns the summary dict."""
    if mode not in MODES:
        raise ValueError(f"bad mode: {mode}")
    if preview and not images:
        raise ValueError("preview needs images")
    model = make_model()
    renderer = mujoco.Renderer(model, 240, 320) if images else None
    out_dir = Path(out) / f"{mode}_seed{seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    if any(out_dir.glob("episode_*.npz")):
        raise SystemExit(f"{out_dir} already has episodes; use another --seed or --out.")

    types = ["none"] if mode == "clean" else ["early", "late"]
    attempts = {k: 0 for k in types}
    successes = {k: 0 for k in types}
    by_type = {k: 0 for k in types}
    episodes = []
    first = {}
    train_frames = total_frames = 0
    attempt = 0
    while train_frames < frames:
        if mode == "clean":
            shift = "none"
        else:
            shift = "early" if by_type["early"] <= by_type["late"] else "late"
        this = attempt
        attempt += 1
        result = Episode(model, episode_rng(seed, mode, this), renderer=renderer, shift_type=shift).run(mode)
        attempts[shift] += 1
        successes[shift] += int(result["success"])
        n_att, n_ok = sum(attempts.values()), sum(successes.values())
        if n_att > 20 and n_ok < n_att / 2:
            raise SystemExit(f"Expert is failing too often: {n_ok}/{n_att} succeeded.")
        sel = select(result, mode)
        if sel is None:
            continue
        sel["seed"] = np.int64(seed)
        sel["attempt"] = np.int64(this)
        name = f"episode_{len(episodes):04d}.npz"
        np.savez_compressed(out_dir / name, **sel)
        n_train = int(sel["train"].sum())
        n_frames = int(sel["train"].size)
        by_type[shift] += 1
        train_frames += n_train
        total_frames += n_frames
        episodes.append({
            "file": name, "shift_type": shift, "shift_frame": int(sel["shift_frame"]),
            "shift_frame_full": int(sel["shift_frame_full"]), "trigger_z": float(sel["trigger_z"]),
            "train_start": int(sel["train_start"]), "train_end": int(sel["train_end"]),
            "seed": seed, "attempt": this, "n_train": n_train, "n_frames": n_frames,
        })
        first.setdefault(shift, sel)

    if preview:
        from PIL import Image
        red = np.array([255, 0, 0], dtype=np.uint8)
        for shift, sel in first.items():
            name = "preview.gif" if mode == "clean" else f"preview_{shift}.gif"
            imgs = []
            total_here = int(sel["train"].size)
            for i in range(total_here):
                frame = np.hstack([sel["top"][i], sel["wrist"][i]]).copy()
                if not sel["train"][i]:
                    frame[:6], frame[-6:] = red, red
                    frame[:, :6], frame[:, -6:] = red, red
                # progress bar: makes every frame unique so Pillow does not merge identical frames
                bar = max(1, round(640 * (i + 1) / total_here))
                frame[-12:-8, :bar] = 255
                imgs.append(Image.fromarray(frame))
            imgs[0].save(out_dir / name, save_all=True, append_images=imgs[1:], duration=50, loop=0,
                         optimize=False)

    summary = {
        "mode": mode, "seed": seed, "frames_budget": frames,
        "train_frames": train_frames, "total_frames": total_frames,
        "episodes": len(episodes), "episodes_by_type": by_type,
        "attempts": attempts, "successes": successes,
    }
    (out_dir / "episodes.json").write_text(json.dumps(_plain(episodes), indent=2, allow_nan=False) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(_plain(summary), indent=2, allow_nan=False) + "\n")
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=MODES, required=True)
    p.add_argument("--frames", type=int, default=1000, help="train frame budget to fill")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="data")
    p.add_argument("--no-images", action="store_true")
    p.add_argument("--preview", action="store_true",
                   help="write GIF preview(s) of the first saved episode(s); needs images")
    args = p.parse_args()
    if args.preview and args.no_images:
        p.error("--preview needs images; drop --no-images")

    s = collect(args.mode, args.frames, seed=args.seed, out=args.out,
                images=not args.no_images, preview=args.preview)
    out_dir = Path(args.out) / f"{args.mode}_seed{args.seed}"
    att, suc, by = s["attempts"], s["successes"], s["episodes_by_type"]
    if args.mode == "clean":
        print(f"{args.mode}: {s['episodes']} episodes (clean), {s['train_frames']} train frames, "
              f"{s['total_frames']} total frames. Expert success: clean {suc['none']}/{att['none']}. "
              f"Saved to {out_dir}")
    else:
        print(f"{args.mode}: {s['episodes']} episodes ({by['early']} early, {by['late']} late), "
              f"{s['train_frames']} train frames, {s['total_frames']} total frames. "
              f"Expert success: early {suc['early']}/{att['early']}, late {suc['late']}/{att['late']}. "
              f"Saved to {out_dir}")


if __name__ == "__main__":
    main()
