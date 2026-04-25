#!/usr/bin/env python3
"""Compare red-team security scores between baseline (main branch) and current run.

Reads:
  .redteam-score.json         - baseline score restored from cache (last main run)
  .redteam-score-current.json - score from the current CI run

Exits with code 1 if the regression exceeds the configured threshold.
"""

import json
import os
import sys

BASELINE_FILE = ".redteam-score.json"
CURRENT_FILE = ".redteam-score-current.json"

# Regression threshold: how many points the score is allowed to drop.
# Override via REDTEAM_REGRESSION_THRESHOLD env var (default: -5).
try:
    THRESHOLD = float(os.environ.get("REDTEAM_REGRESSION_THRESHOLD", "-5"))
except ValueError:
    print(
        "ERROR: REDTEAM_REGRESSION_THRESHOLD must be a number.", file=sys.stderr
    )
    sys.exit(2)


def load_score(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: score file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def main() -> None:
    baseline = load_score(BASELINE_FILE)
    current = load_score(CURRENT_FILE)

    baseline_score = float(baseline.get("score", 0))
    current_score = float(current.get("score", 0))
    delta = current_score - baseline_score

    print("=" * 50)
    print("Red-team score comparison")
    print("=" * 50)
    print(f"  Baseline : {baseline_score:.1f}/100  (branch: {baseline.get('branch', '?')}, {baseline.get('timestamp', '?')})")
    print(f"  Current  : {current_score:.1f}/100  (branch: {current.get('branch', '?')}, {current.get('timestamp', '?')})")
    print(f"  Delta    : {delta:+.1f} points")
    print(f"  Threshold: {THRESHOLD:+.1f} points (fail if delta < threshold)")
    print("=" * 50)

    if delta < THRESHOLD:
        print(
            f"FAIL: score regressed by {delta:.1f} points "
            f"(threshold {THRESHOLD:+.1f}). "
            f"Baseline={baseline_score:.1f}, Current={current_score:.1f}.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"PASS: score delta ({delta:+.1f}) is within acceptable threshold ({THRESHOLD:+.1f}).")


if __name__ == "__main__":
    main()
