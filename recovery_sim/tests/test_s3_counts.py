"""S3 count rules: plan_base / plan_extra trimming, make_plan, built-dataset counts,
manifests, summary and train loader.

All data is synthetic (written to tmp dirs). Rules come from
.orchestration/contract.md. convert.py and make_sets.py are imported, not read.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pytest

RECOVERY_SIM = Path(__file__).resolve().parents[1]
if str(RECOVERY_SIM) not in sys.path:
    sys.path.insert(0, str(RECOVERY_SIM))

H, W = 240, 320
N_BASE = 3              # base episodes used by the plan
N_BASE_WRITTEN = 4      # one more than N_BASE, so plan_base must cut
T_BASE = 20             # all train
T_EXTRA = 30            # per extra episode
N_CTX = 6               # context frames (train False) at the start of separate episodes
N_EXTRA_EPS = 4         # extra episodes written per extra set
N_TRAIN = 60            # n_train for the extras
# separate, n_train=60: episodes 0 and 1 give 24+24 train, episode 2 is cut at 12 train
# (keeps 6 + 12 = 18 frames), so 30 - 18 = 12 frames are removed
SEP_TRIM_REMOVED = T_EXTRA - (N_CTX + (N_TRAIN - 2 * (T_EXTRA - N_CTX)))
EXTRA_SETS = ("control", "separate", "embedded")
FOLDERS = {
    "base": "base/clean_seed1000",
    "control": "control/clean_seed1001",
    "separate": "separate/separate_seed1002",
    "embedded": "embedded/embedded_seed1003",
}
REQUIRED_EP_KEYS = (
    "episode_index", "role", "file", "sha256", "mode", "seed", "attempt",
    "shift_type", "shift_frame", "trigger_z", "block_before", "block_after",
    "n_frames", "n_train", "trimmed", "frames_removed",
)


def _ms():
    import make_sets  # noqa: PLC0415  (import inside helper so a missing module errors per test)
    return make_sets


def _cv():
    import convert  # noqa: PLC0415
    return convert


def _shift_for(i: int, set_name: str) -> str:
    if set_name in ("base", "control"):
        return "none"
    return "early" if i % 2 == 0 else "late"


def _write_episode(path: Path, *, ep_id: int, T: int, seed: int,
                   n_ctx: int = 0, shift_type: str = "none") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed * 100 + ep_id)
    train = np.ones(T, dtype=bool)
    train[:n_ctx] = False
    t = np.arange(T, dtype=np.float32)
    # distinct per frame and per episode, so byte comparisons mean something
    state = np.stack([ep_id * 1000.0 + t + 0.25 * j for j in range(5)], axis=1).astype(np.float32)
    action = np.stack([ep_id * 1000.0 + t + 0.5 * j + 0.125 for j in range(4)], axis=1).astype(np.float32)
    shifted = shift_type != "none"
    np.savez(
        path,
        state=state,
        action=action,
        block_pos=np.zeros((T, 3), np.float32),
        touch=np.zeros(T, dtype=bool),
        train=train,
        top=rng.integers(0, 256, size=(T, H, W, 3), dtype=np.uint8),
        wrist=rng.integers(0, 256, size=(T, H, W, 3), dtype=np.uint8),
        shift_type=np.array(shift_type),
        shift_frame=np.int64(10 if shifted else -1),
        shift_frame_full=np.int64(10 if shifted else -1),
        train_start=np.int64(n_ctx),
        train_end=np.int64(T),
        seed=np.int64(seed),
        attempt=np.int64(0),
        trigger_z=np.float64(0.1 if shift_type == "early" else np.nan),
        block_before=np.zeros(3) if shifted else np.full(3, np.nan),
        block_after=np.zeros(3) if shifted else np.full(3, np.nan),
    )


def _write_raw(raw: Path) -> None:
    # base files are written in reverse name order; plan_base has to sort by name
    for i in reversed(range(N_BASE_WRITTEN)):
        _write_episode(raw / FOLDERS["base"] / f"episode_{i:04d}.npz",
                       ep_id=i, T=T_BASE, seed=1000)
    for set_name, seed in (("control", 1001), ("separate", 1002), ("embedded", 1003)):
        n_ctx = N_CTX if set_name == "separate" else 0
        for i in range(N_EXTRA_EPS):
            _write_episode(raw / FOLDERS[set_name] / f"episode_{i:04d}.npz",
                           ep_id=(seed - 1000) * 10 + i, T=T_EXTRA, seed=seed,
                           n_ctx=n_ctx, shift_type=_shift_for(i, set_name))


@pytest.fixture(scope="module")
def raw_root(tmp_path_factory) -> Path:
    raw = tmp_path_factory.mktemp("raw")
    _write_raw(raw)
    return raw


def _folder(raw: Path, set_name: str) -> Path:
    return raw / FOLDERS[set_name]


def _early_late(entries):
    early = sum(1 for e in entries if e["shift_type"] == "early")
    late = sum(1 for e in entries if e["shift_type"] == "late")
    return early, late


# ---------------------------------------------------------------- plan_base

def test_plan_base_takes_first_n_in_name_order(raw_root):
    ms = _ms()
    entries = ms.plan_base(_folder(raw_root, "base"), n=N_BASE)
    names = [Path(e["file"]).name for e in entries]
    assert names == [f"episode_{i:04d}.npz" for i in range(N_BASE)], \
        "plan_base rule: takes the first n files in name order (files were written in reverse)"
    for e in entries:
        assert e["n_frames"] == T_BASE and e["n_train"] == T_BASE, \
            "plan_base rule: base episodes are kept whole (all train)"
        assert e["trimmed"] is False and e["frames_removed"] == 0, \
            "plan_base rule: base episodes are never trimmed"
        path = _folder(raw_root, "base") / Path(e["file"]).name
        assert e["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest(), \
            "plan_base rule: sha256 is the sha256 of the episode file"


# ---------------------------------------------------------------- plan_extra

def test_plan_extra_cut_inside_separate_episode_with_context(raw_root):
    ms = _ms()
    n_train = 40
    plan = ms.plan_extra(_folder(raw_root, "separate"), n_train=n_train)
    assert len(plan) == 2, \
        "plan_extra rule: walks episodes in order and stops at the one that reaches n_train (expected 2 entries)"
    first, cut = plan
    first_train = T_EXTRA - N_CTX
    need = n_train - first_train
    k = N_CTX + need  # keep frames 0..k-1; the need-th train frame is at index N_CTX+need-1
    assert sum(e["n_train"] for e in plan) == n_train, \
        "plan_extra rule: train total is exactly n_train"
    assert not first["trimmed"] and first["frames_removed"] == 0 and first["n_frames"] == T_EXTRA, \
        "plan_extra rule: earlier episodes are untrimmed"
    assert cut["n_frames"] == k, \
        f"plan_extra rule: cut keeps frames 0..k-1 with k={k} (got {cut['n_frames']})"
    assert cut["n_frames"] - cut["n_train"] == N_CTX, \
        "plan_extra rule: context frames before the cut stay (they are not train frames)"
    assert cut["frames_removed"] == T_EXTRA - k, \
        "plan_extra rule: frames_removed == original length - n_frames"
    assert cut["trimmed"] is True, "plan_extra rule: the cut episode is marked trimmed"
    assert cut["shift_type"] == "late", \
        "plan_extra rule: the trimmed episode keeps its own shift_type (episode 1 is late)"


def test_plan_extra_cut_exactly_at_episode_end(raw_root):
    ms = _ms()
    plan = ms.plan_extra(_folder(raw_root, "separate"), n_train=2 * (T_EXTRA - N_CTX))
    assert len(plan) == 2, "plan_extra rule: a cut at an episode end uses exactly the episodes needed"
    assert sum(e["n_train"] for e in plan) == 2 * (T_EXTRA - N_CTX), \
        "plan_extra rule: train total is exactly n_train at an episode end"
    last = plan[-1]
    assert last["frames_removed"] == 0, \
        "plan_extra rule: cut exactly at an episode end gives frames_removed 0"
    assert last["trimmed"] is False, \
        "plan_extra rule: cut exactly at an episode end is not trimmed"
    assert last["n_frames"] == T_EXTRA, \
        "plan_extra rule: a full episode keeps all its frames"


def test_plan_extra_cut_exactly_at_episode_end_control(raw_root):
    ms = _ms()
    plan = ms.plan_extra(_folder(raw_root, "control"), n_train=N_TRAIN)
    assert len(plan) == 2, "plan_extra rule: control with n_train=60 uses 2 episodes of 30"
    assert all(e["trimmed"] is False and e["frames_removed"] == 0 for e in plan), \
        "plan_extra rule: nothing is trimmed when the cut lands on an episode end"
    assert sum(e["n_train"] for e in plan) == N_TRAIN, \
        "plan_extra rule: train total is exactly n_train"


def test_plan_extra_n_train_smaller_than_first_episode(raw_root):
    ms = _ms()
    n_train = 10
    plan = ms.plan_extra(_folder(raw_root, "separate"), n_train=n_train)
    assert len(plan) == 1, \
        "plan_extra rule: n_train smaller than the first episode uses only that episode"
    only = plan[0]
    k = N_CTX + n_train
    assert only["n_train"] == n_train, \
        "plan_extra rule: train total is exactly n_train"
    assert only["n_frames"] == k, \
        f"plan_extra rule: keeps frames 0..k-1 with k={k} (got {only['n_frames']})"
    assert only["frames_removed"] == T_EXTRA - k and only["trimmed"] is True, \
        "plan_extra rule: frames_removed == original length - n_frames and trimmed is set"


def test_plan_extra_errors_when_folder_runs_out(raw_root):
    ms = _ms()
    total_train = N_EXTRA_EPS * (T_EXTRA - N_CTX)
    # contract says "error" without naming the type, so any Exception counts
    with pytest.raises(Exception):  # noqa: B017
        ms.plan_extra(_folder(raw_root, "separate"), n_train=total_train + 1)


def test_plan_extra_early_late_counts_differ_by_at_most_one(raw_root):
    ms = _ms()
    plan = ms.plan_extra(_folder(raw_root, "separate"), n_train=N_TRAIN)
    early, late = _early_late(plan)
    assert abs(early - late) <= 1, \
        f"plan_extra rule: early and late counts differ by at most one after trimming (early={early}, late={late})"
    assert plan[-1]["shift_type"] == "early", \
        "plan_extra rule: the trimmed episode counts as its own type (episode 2 is early)"


# ---------------------------------------------------------------- make_plan

def test_make_plan_shape_and_base_shared(raw_root):
    ms = _ms()
    plan = ms.make_plan(raw_root, n_base=N_BASE, n_extra=N_TRAIN)
    for key in ("base", "control", "separate", "embedded", "seeds"):
        assert key in plan, f"make_plan rule: returns key '{key}'"
    assert len(plan["base"]) == N_BASE, \
        "make_plan rule: base holds the first n_base files"
    direct = ms.plan_base(_folder(raw_root, "base"), n=N_BASE)
    assert [Path(e["file"]).name for e in plan["base"]] == [Path(e["file"]).name for e in direct], \
        "make_plan rule: base entries are the first n_base files in name order"
    assert [e["sha256"] for e in plan["base"]] == [e["sha256"] for e in direct], \
        "make_plan rule: base entries carry the same sha256 as plan_base"
    for name in EXTRA_SETS:
        assert sum(e["n_train"] for e in plan[name]) == N_TRAIN, \
            f"make_plan rule: '{name}' extras total exactly n_extra train frames"
        assert all(e["file"].startswith(FOLDERS[name].split("/")[0]) for e in plan[name]), \
            f"make_plan rule: '{name}' entries point into its own set folder"


# ---------------------------------------------------------------- build + load

@pytest.fixture(scope="module")
def built(raw_root, tmp_path_factory):
    pytest.importorskip("lerobot")
    ms = _ms()
    cv = _cv()
    plan = ms.make_plan(raw_root, n_base=N_BASE, n_extra=N_TRAIN)
    out = tmp_path_factory.mktemp("datasets")
    for name in EXTRA_SETS:
        cv.build(name, plan, raw_root, out)
    return {"plan": plan, "raw": raw_root, "out": out, "cv": cv}


def _manifest(built, name):
    path = built["out"] / "manifests" / f"{name}.json"
    assert path.exists(), f"manifest rule: manifest exists at {path}"
    return json.loads(path.read_text())


def _load(built, name):
    return built["cv"].load(name, built["out"])


@pytest.mark.parametrize("name", EXTRA_SETS)
def test_manifest_top_level_and_episode_fields(built, name):
    pytest.importorskip("lerobot")
    cv = built["cv"]
    m = _manifest(built, name)
    assert m["name"] == name, "manifest rule: name"
    assert m["lerobot_version"] == "0.7.0", "manifest rule: lerobot_version is 0.7.0"
    assert m["fps"] == cv.FPS and m["task"] == cv.TASK, "manifest rule: fps and task"
    assert m["stats"] == "train_frames_only", "manifest rule: stats recorded as train_frames_only"
    eps = m["episodes"]
    assert len(eps) == N_BASE + len(built["plan"][name]), \
        "manifest rule: one entry per base episode plus per extra episode"
    for i, e in enumerate(eps):
        for key in REQUIRED_EP_KEYS:
            assert key in e, f"manifest rule: episode {i} has field '{key}'"
        assert e["episode_index"] == i, "manifest rule: episode_index is the dataset index"
        expected_role = "base" if i < N_BASE else "extra"
        assert e["role"] == expected_role, \
            f"manifest rule: episode {i} role is '{expected_role}' (base first, then extras)"


@pytest.mark.parametrize("name", EXTRA_SETS)
def test_manifest_entries_match_plan(built, name):
    pytest.importorskip("lerobot")
    m = _manifest(built, name)
    plan = built["plan"]
    expected = plan["base"] + plan[name]
    for i, (e, p) in enumerate(zip(m["episodes"], expected)):
        assert e["file"] == p["file"] and e["sha256"] == p["sha256"], \
            f"manifest rule: episode {i} file and sha256 come from the plan (base entries are the same in every dataset)"
        assert e["n_frames"] == p["n_frames"] and e["n_train"] == p["n_train"], \
            f"manifest rule: episode {i} n_frames and n_train match the plan"
        assert e["trimmed"] == p["trimmed"] and e["frames_removed"] == p["frames_removed"], \
            f"manifest rule: episode {i} trimmed and frames_removed match the plan"


@pytest.mark.parametrize("name", EXTRA_SETS)
def test_manifest_train_total_and_trimmed_records(built, name):
    pytest.importorskip("lerobot")
    m = _manifest(built, name)
    eps = m["episodes"]
    assert sum(e["n_train"] for e in eps) == N_BASE * T_BASE + N_TRAIN, \
        "manifest rule: train frames over base and extras add up to base train + n_train"
    for i, e in enumerate(eps):
        assert e["trimmed"] == (e["frames_removed"] > 0), \
            f"manifest rule: episode {i} trimmed is set exactly when frames_removed > 0"
        orig = T_BASE if i < N_BASE else T_EXTRA
        assert e["frames_removed"] == orig - e["n_frames"], \
            f"manifest rule: episode {i} frames_removed == original length - n_frames"
    trimmed = [e for e in eps if e["trimmed"]]
    if name == "separate":
        assert len(trimmed) == 1 and trimmed[0]["episode_index"] == N_BASE + 2, \
            "manifest rule: the cut episode is recorded as trimmed (separate cuts episode 2)"
        assert trimmed[0]["frames_removed"] == SEP_TRIM_REMOVED, \
            "manifest rule: trimmed entry records frames_removed"
    else:
        assert trimmed == [], \
            f"manifest rule: '{name}' cuts on an episode end, so nothing is trimmed"


@pytest.mark.parametrize("name", EXTRA_SETS)
def test_loaded_episode_and_frame_counts(built, name):
    pytest.importorskip("lerobot")
    ds = _load(built, name)
    plan = built["plan"]
    assert ds.meta.total_episodes == N_BASE + len(plan[name]), \
        "build rule: dataset episodes == n_base + extra episodes"
    expected_frames = sum(e["n_frames"] for e in plan["base"] + plan[name])
    assert len(ds) == expected_frames, \
        f"build rule: frames kept equal the plan's n_frames (expected {expected_frames}, got {len(ds)})"


@pytest.mark.parametrize("name", EXTRA_SETS)
def test_extra_train_frames_from_train_feature(built, name):
    pytest.importorskip("lerobot")
    cv = built["cv"]
    ds = _load(built, name)
    train = np.asarray(ds.hf_dataset["train"]).reshape(len(ds), -1)[:, 0].astype(bool)
    ep = np.asarray(ds.hf_dataset["episode_index"]).reshape(-1)
    extra_train = int(np.sum(train & (ep >= N_BASE)))
    assert extra_train == N_TRAIN, \
        f"build rule: extra train frames counted from the loaded train feature == n_train (got {extra_train})"
    idx = np.asarray(cv.train_indices(ds))
    assert np.array_equal(idx, np.flatnonzero(train)), \
        "train_indices rule: returns the global indices with train == True, sorted"
    if name == "separate":
        n_context = int(np.sum(~train))
        assert n_context == N_CTX * 3, \
            f"build rule: context frames (train False) are kept but not counted (expected {N_CTX * 3}, got {n_context})"


def test_first_n_base_episodes_identical_across_datasets(built):
    pytest.importorskip("lerobot")
    plan = built["plan"]
    # expected: state+action bytes straight from the raw base npz files
    expected = []
    for p in plan["base"]:
        z = np.load(built["raw"] / p["file"])
        expected.append(hashlib.sha256(
            z["state"].astype(np.float32).tobytes() + z["action"].astype(np.float32).tobytes()
        ).hexdigest())
    for name in EXTRA_SETS:
        ds = _load(built, name)
        ep = np.asarray(ds.hf_dataset["episode_index"]).reshape(-1)
        state = np.asarray(ds.hf_dataset["observation.state"], dtype=np.float32).reshape(len(ds), 5)
        action = np.asarray(ds.hf_dataset["action"], dtype=np.float32).reshape(len(ds), 4)
        got = []
        for i in range(N_BASE):
            mask = ep == i
            got.append(hashlib.sha256(state[mask].tobytes() + action[mask].tobytes()).hexdigest())
        assert got == expected, \
            f"build rule: first n_base episodes in '{name}' are byte-identical to the raw base files (state+action)"


def test_base_sha256_identical_across_built_datasets(built):
    pytest.importorskip("lerobot")
    cv = built["cv"]
    sums = {name: cv.summarize(name, built["out"], built["raw"])["base_sha256"] for name in EXTRA_SETS}
    assert len(sums["control"]) == N_BASE, "summary rule: base_sha256 has one hash per base episode"
    assert sums["control"] == sums["separate"] == sums["embedded"], \
        "build rule: the first n_base episodes are identical across the three built datasets"


@pytest.mark.parametrize("name", EXTRA_SETS)
def test_summary_counts_and_checks(built, name):
    pytest.importorskip("lerobot")
    plan = built["plan"]
    s = built["cv"].summarize(name, built["out"], built["raw"])
    for key in ("name", "episodes", "frames", "base_episodes", "base_sha256", "extra_train_frames",
                "context_frames", "early", "late", "trimmed", "state_action_exact", "image_diff", "batch_ok"):
        assert key in s, f"summary rule: summary has '{key}'"
    assert s["episodes"] == N_BASE + len(plan[name]), "summary rule: episodes == base + extras"
    assert s["frames"] == sum(e["n_frames"] for e in plan["base"] + plan[name]), \
        "summary rule: frames == frames kept across the dataset"
    assert s["base_episodes"] == N_BASE, "summary rule: base_episodes is the n_base used"
    assert s["extra_train_frames"] == N_TRAIN, "summary rule: extra_train_frames == n_train exactly"
    expected_ctx = sum(e["n_frames"] - e["n_train"] for e in plan[name])
    assert s["context_frames"] == expected_ctx, \
        f"summary rule: context_frames counts only the non-train frames (expected {expected_ctx})"
    early, late = _early_late(plan[name])
    assert (s["early"], s["late"]) == (early, late), \
        "summary rule: early and late counts from the dataset match the plan's counts"
    assert abs(s["early"] - s["late"]) <= 1, \
        "summary rule: early and late counts differ by at most one after trimming"
    if name == "separate":
        assert s["trimmed"]["episode_index"] == N_BASE + 2 and s["trimmed"]["frames_removed"] == SEP_TRIM_REMOVED, \
            "summary rule: trimmed records the episode index and frames_removed"
    else:
        assert not s["trimmed"], f"summary rule: '{name}' has no trimmed episode"
    assert s["state_action_exact"] is True, "build rule: state and action values are copied exactly"
    assert s["batch_ok"] is True, "summary rule: batch_ok is True"
    for cam in ("top", "wrist"):
        d = s["image_diff"][cam]
        for key in ("mean_abs", "max_abs", "psnr"):
            assert key in d, f"summary rule: image_diff.{cam} has '{key}'"


@pytest.mark.parametrize("name", EXTRA_SETS)
def test_stats_are_train_frames_only(built, name):
    pytest.importorskip("lerobot")
    cv = built["cv"]
    ds = _load(built, name)
    idx = np.asarray(cv.train_indices(ds))
    state = np.asarray(ds.hf_dataset["observation.state"], dtype=np.float32).reshape(len(ds), 5)
    want_mean = state[idx].mean(axis=0)
    got = cv.train_stats(ds)
    assert np.allclose(np.asarray(got["observation.state"]["mean"]).reshape(-1), want_mean,
                       rtol=1e-4, atol=1e-2), \
        "stats rule: train_stats uses train frames only"
    stored = np.asarray(ds.meta.stats["observation.state"]["mean"]).reshape(-1)
    assert np.allclose(stored, want_mean, rtol=1e-4, atol=1e-2), \
        "build rule: the dataset's stored stats are replaced with train-only stats"


@pytest.mark.parametrize("name", ("separate",))
def test_train_loader_only_samples_train_indices(built, name):
    pytest.importorskip("lerobot")
    cv = built["cv"]
    ds = _load(built, name)
    allowed = set(np.asarray(cv.train_indices(ds)).tolist())
    dl = cv.train_loader(ds, batch_size=8, seed=0)
    seen = set()
    for batch in itertools.islice(dl, 10):
        assert "index" in batch, "train_loader rule: batches carry the global 'index' so sampling can be checked"
        seen.update(np.asarray(batch["index"]).reshape(-1).tolist())
    assert seen, "train_loader rule: loader yields batches"
    assert seen <= allowed, \
        "train_loader rule: only ever samples train_indices (context frames must never appear)"
