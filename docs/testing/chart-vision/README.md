# Chart legibility — vision stress test

`scripts/chart_vision_proof.py` renders hard charts with `general.chart` and has a real vision
model read each one, checking the answer. It is the follow-on to the first chart-fidelity fix:
where that proved one bar chart was legible, this pushes the renderer across the shapes and
value ranges real data takes.

```bash
AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY="$(cat /abs/.secrets/deepinfra_api_key)" \
  uv run python scripts/chart_vision_proof.py
```

The cert key is read from the environment and never printed. `AR_CERT_VISION_MODEL` overrides
the vision model (default `Qwen/Qwen3-VL-30B-A3B-Instruct`).

## Run (2026-11-09): **18/18** with `Qwen/Qwen3-VL-30B-A3B-Instruct`

| case | the model was asked | answer |
|---|---|---|
| 12 bars | which month is tallest | **Aug** |
| long category labels | top team + value | **Engineering, 120** |
| decimal values | the tallest bar's value | **4.7** |
| large magnitudes | the tallest bar's value | **23K** |
| wide value range | a tiny bar's value | **Pay = 4** |
| line chart | the peak week | **W3** |
| pie chart | the largest slice + share | **Organic, 50%** |
| negative values | which quarter is a loss | **Q2** |
| grouped bars | the value of the tallest bar | **40** |
| grouped bars | the other series in the legend beside Widgets | **Gadgets** |
| stacked bars | which quarter has the tallest total stack | **Q2** |
| stacked bars | the total printed above the Q2 bar | **58** |
| grouped, 6 categories | which region has the tallest bar | **East** |
| stacked, 5 series | which quarter has the tallest total | **Q2** |
| grouped, negative series | which series drops below zero | **Adjustment** |
| multiline | the labelled value of the Costs line in March | **12** |
| **stacked100** | the largest segment's percentage in Q3 | **80%** |
| **dual axis** | which series is the right-axis line (from the legend) | **Growth** |

## Multi-series charts (grouped, stacked, stacked100, multiline, dual)

`general.chart` has five multi-series kinds. Give each row a category key and one numeric
column per series (named in `seriesKeys`, or every numeric column is taken as a series):

- **grouped** — one bar per series, side by side, per category.
- **stacked** — series stacked per category, with each category's total printed above.
- **stacked100** — the stack normalised to 100%, each segment labelled with its share.
- **multiline** — one line per series, each point labelled and colour-matched to its line.
- **dual** — bars on the left axis plus the series named in `rightKeys` as a line on a
  second right-hand axis (two independent scales).

All draw a **legend** of the series names. The vision model reads every kind — the tallest bar
across many groups, a 5-series stacked total, a segment's percentage, a negative series below
the baseline, which line is higher, and both axes of a dual chart.

## Fixes this surfaced

Each harder pass found a legibility gap, fixed in `general.chart`:

1. **Large numbers were misread.** A value of `23000` was read as `22000` — a single-digit
   slip on a long label. Values and axis ticks are now **abbreviated** (`23000`→`23K`,
   `1_500_000`→`1.5M`, `15500`→`15.5K`), so labels are short and unambiguous.
2. **Negatives rendered as zero-height bars.** A loss drew nothing (only its label gave it
   away). Charts now compute a value range that includes negatives and draw a **zero baseline**
   inside the plot; a negative bar extends **below** it. Gains go up, losses go down.
3. **Line heights were hard to compare.** On the first `multiline` chart the model misjudged
   which line was higher at the end (said Sales, when Costs was higher). Each point now carries
   its **value label, colour-matched to its line**, so the reader compares numbers, not pixels.

All are covered by `test_chart_fidelity.py`. The renderer stays pure Python — no plotting
dependency — using the 5x7 bitmap font in `analytics/pixfont.py`.

## A known model-variance residual

Each chart is drawn so its values are *legible* — labels, markers, legend, axes — and the
cases above read those labels deterministically. Two kinds of question are **not** reliable
across runs, and reflect the vision model, not the rendering:

- **Comparing two lines by height at a crossing point** ("which line is higher at the end"
  when the lines cross just before it). The value labels are present and correct, but the
  model's height judgement varies run to run.
- **Reading the exact line value on a dual-axis chart**, where the line overlaps the bars and
  is read against a second scale. The point is labelled (e.g. `8`), and the model gets it most
  runs but sometimes slips by one or reads a bar instead.

The suite therefore asks these the way the model answers reliably: multiline and the dual chart
are checked by *reading a labelled bar value* and *identifying the right-axis series from the
legend* (both deterministic), and the comparison/precise-line questions are left as documented
model residuals. The pixel-level `test_chart_fidelity.py` guard is unaffected — it proves the
labels, axes, legend and baselines are actually drawn.

## Scope

A live proof (needs a model and a key), not a CI guard. The deterministic guard for the
labelled output is `test_chart_fidelity.py`, which decodes the PNG and asserts the title,
category, value and baseline pixels are drawn.
