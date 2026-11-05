"""Tool-choice eval gym. CI uses a scripted model; a live model is opt-in."""

from ar_domain.evals.gym.runner import run_suite
from ar_domain.evals.gym.score import render_scorecard

__all__ = ["render_scorecard", "run_suite"]
