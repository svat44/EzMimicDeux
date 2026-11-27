"""Budget and balance rules for recovery_sim/collect.py.

Tests the interface contract in .orchestration/contract.md only.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import collect

RECOVERY_DIR = str(Path(__file__).resolve().parents[1])
COLLECT_PY = os.path.join(RECOVERY_DIR, "collect.py")
VENV_PY = sys.executable
SEED = 0

LAST_LINE_RE = re.compile(
    r"^separate: (\d+) episodes \((\d+) early, (\d+) late\), (\d+) train frames, "
    r"(\d+) total frames\. Expert success: early (\d+)/(\d+), late (\d+)/(\d+)\. "
    r"Saved to (.+)$"
)


def _load_episodes(root):
    """Load every saved episode_XXXX.npz under root, in save order (sorted by name)."""
    files = sorted(str(p) for p in root.rglob("episode_*.npz"))
    eps = []
    for f in files:
        with np.load(f, allow_pickle=False) as z:
            eps.append({k: z[k] for k in z.files})
    return files, eps


def _kinds(eps):
    return [str(e["shift_type"]) for e in eps]


def _run_cli(args):
    return subprocess.run(
        [VENV_PY, COLLECT_PY, *args],
        cwd=RECOVERY_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )


# --- --frames counts only train frames -------------------------------------

@pytest.mark.parametrize("budget", [150, 400])
def test_frames_counts_only_train_frames_separate(tmp_path, budget):
    summary = collect.collect("separate", budget, seed=SEED, out=str(tmp_path), images=False)
    files, eps = _load_episodes(tmp_path)
    assert eps, "rule broken: no episodes were saved in separate mode"

    train_sum = sum(int(np.sum(e["train"])) for e in eps)
    assert summary["train_frames"] == train_sum, (
        f"rule broken: summary train_frames={summary['train_frames']} but sum of "
        f"train-True over saved files is {train_sum}"
    )
    assert summary["train_frames"] >= budget, (
        f"rule broken: train_frames={summary['train_frames']} is below budget {budget}"
    )
    last_train = int(np.sum(eps[-1]["train"]))
    assert summary["train_frames"] - last_train < budget, (
        "rule broken: stopping was not at the first whole episode reaching the budget; "
        f"removing the last saved episode still leaves {summary['train_frames'] - last_train} "
        f">= budget {budget}"
    )

    total = sum(len(e["train"]) for e in eps)
    assert summary["total_frames"] == total, (
        f"rule broken: summary total_frames={summary['total_frames']} but saved files hold {total}"
    )


def test_context_frames_exist_and_do_not_count_separate(tmp_path):
    summary = collect.collect("separate", 400, seed=SEED, out=str(tmp_path), images=False)
    files, eps = _load_episodes(tmp_path)
    assert eps, "rule broken: no episodes were saved in separate mode"

    context_total = 0
    for f, e in zip(files, eps):
        t = e["train"]
        n_ctx = int(np.sum(~t))
        context_total += n_ctx
        assert n_ctx <= collect.CONTEXT, (
            f"rule broken: {n_ctx} context frames in {f}, more than CONTEXT={collect.CONTEXT}"
        )
        assert (not t[:n_ctx].any()) and t[n_ctx:].all(), (
            f"rule broken: context frames (train=False) must be the leading frames of {f}"
        )
    assert context_total > 0, "rule broken: separate mode saved no context frames (train=False)"
    assert summary["total_frames"] == summary["train_frames"] + context_total, (
        "rule broken: total_frames must be train_frames plus context frames; "
        f"got total={summary['total_frames']}, train={summary['train_frames']}, "
        f"context={context_total}"
    )


# --- Balance ----------------------------------------------------------------

@pytest.mark.parametrize("mode", ["embedded", "separate"])
@pytest.mark.parametrize("budget", [150, 400, 900])
def test_balance_early_late_saved_episodes(tmp_path, mode, budget):
    summary = collect.collect(mode, budget, seed=SEED, out=str(tmp_path), images=False)
    _, eps = _load_episodes(tmp_path)
    kinds = _kinds(eps)
    early, late = kinds.count("early"), kinds.count("late")
    assert abs(early - late) <= 1, (
        f"rule broken: saved early={early} and late={late} differ by more than 1 "
        f"(mode={mode}, budget={budget})"
    )
    assert summary["episodes_by_type"]["early"] == early, (
        "rule broken: summary episodes_by_type['early'] does not match saved files"
    )
    assert summary["episodes_by_type"]["late"] == late, (
        "rule broken: summary episodes_by_type['late'] does not match saved files"
    )


@pytest.mark.parametrize("mode,budget", [("embedded", 1500), ("separate", 600)])
def test_balance_holds_when_every_second_late_attempt_fails(tmp_path, monkeypatch, mode, budget):
    orig_run = collect.Episode.run
    state = {"late_seen": 0}

    def run_forcing_late_failures(self, *args, **kwargs):
        result = orig_run(self, *args, **kwargs)
        if result["shift_type"] == "late":
            state["late_seen"] += 1
            if state["late_seen"] % 2 == 0:
                result = dict(result)
                result["success"] = False
        return result

    monkeypatch.setattr(collect.Episode, "run", run_forcing_late_failures)
    summary = collect.collect(mode, budget, seed=SEED, out=str(tmp_path), images=False)

    assert state["late_seen"] >= 2, "test broken: no late attempts were run, wrapper never forced a failure"
    _, eps = _load_episodes(tmp_path)
    kinds = _kinds(eps)
    early, late = kinds.count("early"), kinds.count("late")
    assert abs(early - late) <= 1, (
        f"rule broken: balance must be on saved episodes, not attempts; saved early={early}, "
        f"late={late} (mode={mode})"
    )
    assert summary["attempts"]["late"] > summary["successes"]["late"], (
        "rule broken: forced late failures were not counted; attempts['late'] must exceed "
        f"successes['late'] (got attempts={summary['attempts']['late']}, "
        f"successes={summary['successes']['late']})"
    )


# --- summary ----------------------------------------------------------------

@pytest.mark.parametrize("mode", ["embedded", "separate"])
def test_summary_early_late_reported_separately(tmp_path, mode):
    summary = collect.collect(mode, 150, seed=SEED, out=str(tmp_path), images=False)
    assert summary["mode"] == mode, "rule broken: summary mode mismatch"
    assert summary["seed"] == SEED, "rule broken: summary seed mismatch"
    assert summary["frames_budget"] == 150, "rule broken: summary frames_budget mismatch"

    for field in ("episodes_by_type", "attempts", "successes"):
        assert set(summary[field].keys()) == {"early", "late"}, (
            f"rule broken: summary['{field}'] must report early and late separately, "
            f"got keys {sorted(summary[field].keys())}"
        )
    for k in ("early", "late"):
        assert summary["successes"][k] == summary["episodes_by_type"][k], (
            f"rule broken: successes['{k}'] must equal episodes_by_type['{k}'] "
            "(every successful attempt is saved)"
        )
        assert summary["attempts"][k] >= summary["successes"][k], (
            f"rule broken: attempts['{k}'] must be >= successes['{k}']"
        )
    assert summary["episodes"] == summary["episodes_by_type"]["early"] + summary["episodes_by_type"]["late"], (
        "rule broken: episodes must equal early + late"
    )


def test_summary_clean_uses_none_key(tmp_path):
    summary = collect.collect("clean", 150, seed=SEED, out=str(tmp_path), images=False)
    for field in ("episodes_by_type", "attempts", "successes"):
        assert set(summary[field].keys()) == {"none"}, (
            f"rule broken: clean summary['{field}'] must use only the key 'none', "
            f"got {sorted(summary[field].keys())}"
        )
    assert summary["successes"]["none"] == summary["episodes_by_type"]["none"], (
        "rule broken: clean successes['none'] must equal episodes_by_type['none']"
    )
    assert summary["attempts"]["none"] >= summary["successes"]["none"], (
        "rule broken: clean attempts['none'] must be >= successes['none']"
    )


def test_summary_json_matches_returned_summary(tmp_path):
    summary = collect.collect("embedded", 150, seed=SEED, out=str(tmp_path), images=False)
    found = list(tmp_path.rglob("summary.json"))
    assert found, "rule broken: summary.json was not written"
    with open(found[0]) as fh:
        on_disk = json.load(fh)
    for key in ("episodes_by_type", "attempts", "successes", "train_frames", "total_frames"):
        assert on_disk[key] == summary[key], (
            f"rule broken: summary.json field '{key}' differs from the returned summary"
        )


# --- CLI ----------------------------------------------------------------------

def test_cli_separate_run_exit_code_and_last_line(tmp_path):
    out = tmp_path / "run"
    r = _run_cli(["--mode", "separate", "--frames", "300", "--no-images", "--out", str(out)])
    assert r.returncode == 0, (
        f"rule broken: CLI exit code {r.returncode}, stderr tail: {r.stderr[-500:]}"
    )
    lines = r.stdout.strip().splitlines()
    assert lines, "rule broken: CLI printed nothing on stdout"
    m = LAST_LINE_RE.match(lines[-1])
    assert m, f"rule broken: last stdout line does not match the contract format: {lines[-1]!r}"

    n_ep, n_early, n_late, n_train, n_total, s_early, a_early, s_late, a_late = (
        int(x) for x in m.groups()[:9]
    )
    assert n_early + n_late == n_ep, "rule broken: E must equal e + l in the CLI line"
    assert n_train >= 300, f"rule broken: CLI reports {n_train} train frames, below --frames 300"
    assert a_early >= s_early and a_late >= s_late, "rule broken: CLI attempts must be >= successes"
    assert str(out) in lines[-1], "rule broken: CLI last line must name the --out folder"

    files, eps = _load_episodes(out)
    kinds = _kinds(eps)
    assert kinds.count("early") == s_early, "rule broken: CLI early success count != saved early episodes"
    assert kinds.count("late") == s_late, "rule broken: CLI late success count != saved late episodes"
    assert sum(int(np.sum(e["train"])) for e in eps) == n_train, (
        "rule broken: CLI train frame count does not match saved files"
    )
    assert sum(len(e["train"]) for e in eps) == n_total, (
        "rule broken: CLI total frame count does not match saved files"
    )


def test_cli_existing_flags_accepted(tmp_path):
    r = _run_cli([
        "--mode", "clean", "--frames", "50", "--seed", "3",
        "--out", str(tmp_path / "flags"), "--no-images",
    ])
    assert r.returncode == 0, (
        f"rule broken: --mode/--frames/--seed/--out/--no-images not all accepted, "
        f"exit {r.returncode}, stderr tail: {r.stderr[-500:]}"
    )


def test_cli_preview_flag_accepted(tmp_path):
    out = tmp_path / "preview"
    r = _run_cli(["--mode", "clean", "--frames", "1", "--seed", "0", "--out", str(out), "--preview"])
    assert r.returncode == 0, (
        f"rule broken: --preview not accepted, exit {r.returncode}, stderr tail: {r.stderr[-500:]}"
    )
    assert list(out.rglob("preview.gif")), "rule broken: --preview did not write preview.gif for clean"


def test_cli_second_run_into_same_out_fails(tmp_path):
    out = str(tmp_path / "twice")
    args = ["--mode", "separate", "--frames", "300", "--no-images", "--out", out]
    first = _run_cli(args)
    assert first.returncode == 0, f"test broken: first CLI run exited {first.returncode}"
    second = _run_cli(args)
    assert second.returncode != 0, (
        "rule broken: a second run into the same out folder must exit nonzero (refuses to overwrite)"
    )
