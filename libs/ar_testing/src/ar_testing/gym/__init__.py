"""Tool-choice eval gym. CI uses a scripted model; a live model is opt-in."""

from ar_testing.gym.runner import run_suite
from ar_testing.gym.score import render_scorecard

__all__ = ["render_scorecard", "run_suite"]
