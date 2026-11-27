"""Collect scripted demonstrations for the recovery-demo experiment.

A simplified gripper (moves in x, y, z) puts a block into a bowl in MuJoCo.
Modes:
  clean     - no disturbance, whole episode saved
  embedded  - block is shifted during the approach, whole episode saved
  separate  - same shift, but only the part after the missed grasp is saved

Examples:
  python collect.py --mode clean --frames 2000 --no-images     (physics check)
  python collect.py --mode embedded --frames 600 --preview     (writes a GIF)
"""
import argparse
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
SHIFT = 0.08            # how far the block jumps, metres (clears the fingers)


class Episode:
    def __init__(self, model, rng, renderer=None):
        self.model, self.rng, self.renderer = model, rng, renderer
        self.data = mujoco.MjData(model)
        self.block_adr = model.joint("block").qposadr[0]
        start = rng.uniform([-0.14, -0.09], [-0.02, 0.09])
        self.data.qpos[self.block_adr:self.block_adr + 2] = start
        self.target = np.array([0.0, 0.0, HIGH_Z])
        self.grip = OPEN
        self.data.qpos[2] = HIGH_Z - HAND_Z0
        self._apply()
        for _ in range(200):
            mujoco.mj_step(model, self.data)
        self.frames = []

    def _apply(self):
        x, y, z = self.target
        self.data.ctrl[:] = [x, y, z - HAND_Z0, self.grip, self.grip]

    def block(self):
        return self.data.qpos[self.block_adr:self.block_adr + 3].copy()

    def step(self):
        """Record what the policy would see and do, then advance one control step."""
        frame = {
            "state": self.data.qpos[:5].astype(np.float32).copy(),
            "action": np.array([*self.target, self.grip], dtype=np.float32),
        }
        if self.renderer:
            for cam in ("top", "wrist"):
                self.renderer.update_scene(self.data, camera=cam)
                frame[cam] = self.renderer.render().copy()
        self.frames.append(frame)
        self._apply()
        for _ in range(SIM_STEPS):
            mujoco.mj_step(self.model, self.data)

    def move(self, xy, z, noise=0.0015):
        goal = np.array([xy[0], xy[1], z])
        while np.linalg.norm(goal - self.target) > 1e-6:
            delta = goal - self.target
            dist = np.linalg.norm(delta)
            speed = SPEED * self.rng.uniform(0.8, 1.2)
            if dist <= speed:
                self.target = goal.copy()
            else:
                self.target = self.target + delta / dist * speed + self.rng.normal(0, noise, 3)
            self.step()
        for _ in range(4):
            self.step()

    def set_grip(self, value, steps=10):
        self.grip = value
        for _ in range(steps):
            self.step()

    def shift_block(self):
        old = self.block()[:2]
        while True:
            angle = self.rng.uniform(0, 2 * np.pi)
            new = old + SHIFT * np.array([np.cos(angle), np.sin(angle)])
            if -0.18 < new[0] < 0.04 and -0.13 < new[1] < 0.13:
                break
        self.data.qpos[self.block_adr:self.block_adr + 2] = new
        self.data.qvel[:] = 0
        mujoco.mj_forward(self.model, self.data)

    def run(self, mode):
        """Run the scripted expert. Returns (success, saved_frames)."""
        old_xy = self.block()[:2]
        self.move(old_xy, HIGH_Z)
        start = 0
        if mode == "clean":
            self.move(old_xy, GRASP_Z)
        else:
            # The block jumps partway down; the expert finishes the old motion
            # and closes on empty space before it reacts.
            self.move(old_xy, 0.13)
            self.shift_block()
            self.move(old_xy, GRASP_Z)
            self.set_grip(CLOSED)
            if mode == "separate":
                start = len(self.frames)
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
        return success, self.frames[start:]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["clean", "embedded", "separate"], required=True)
    p.add_argument("--frames", type=int, default=1000, help="frame budget to fill")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="data")
    p.add_argument("--no-images", action="store_true")
    p.add_argument("--preview", action="store_true", help="save first episode as a GIF")
    args = p.parse_args()

    model = mujoco.MjModel.from_xml_string(XML)
    renderer = None if args.no_images else mujoco.Renderer(model, 240, 320)
    mode_id = ["clean", "embedded", "separate"].index(args.mode)
    rng = np.random.default_rng([args.seed, mode_id])
    out = Path(args.out) / f"{args.mode}_seed{args.seed}"
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob("episode_*.npz")):
        raise SystemExit(f"{out} already has episodes; use another --seed or --out.")

    total = saved = tried = 0
    while total < args.frames:
        tried += 1
        success, frames = Episode(model, rng, renderer).run(args.mode)
        if not success:
            if tried > 20 and saved < tried / 2:
                raise SystemExit(f"Expert is failing too often: {saved}/{tried} succeeded.")
            continue
        arrays = {k: np.stack([f[k] for f in frames]) for k in frames[0]}
        np.savez_compressed(out / f"episode_{saved:04d}.npz", **arrays)
        if args.preview and saved == 0 and renderer:
            from PIL import Image
            imgs = [Image.fromarray(np.hstack([f["top"], f["wrist"]])) for f in frames[::2]]
            imgs[0].save(out / "preview.gif", save_all=True, append_images=imgs[1:], duration=100, loop=0)
        saved += 1
        total += len(frames)

    print(f"{args.mode}: {saved} episodes, {total} frames, expert success {saved}/{tried}. Saved to {out}")


if __name__ == "__main__":
    main()
