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

## Run (2026-11-09): **12/12** with `Qwen/Qwen3-VL-30B-A3B-Instruct`

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
| **grouped bars** | which quarter has the tallest single bar | **Q2** |
| **grouped bars** | the other series in the legend beside Widgets | **Gadgets** |
| **stacked bars** | which quarter has the tallest total stack | **Q2** |
| **stacked bars** | the total printed above the Q2 bar | **58** |

## Multi-series charts (grouped and stacked)

`general.chart` gained two kinds, `grouped` and `stacked`, for several series per category.
Give each row a category key and one numeric column per series (named in `seriesKeys`, or every
numeric column is taken as a series). Both draw a **legend** of the series names, and stacked
bars print each **total** above the stack. The vision model reads all of it — the tallest bar
across groups, the legend series names, the tallest stack, and the printed totals (the four
rows above).

## Two fixes this surfaced

The first pass was **7/8**. Two legibility gaps were found and fixed in `general.chart`:

1. **Large numbers were misread.** A value of `23000` was read as `22000` — a single-digit
   slip on a long label. Values and axis ticks are now **abbreviated** (`23000`→`23K`,
   `1_500_000`→`1.5M`, `15500`→`15.5K`), so labels are short and unambiguous.
2. **Negatives rendered as zero-height bars.** A loss drew nothing (only its label gave it
   away). Charts now compute a value range that includes negatives and draw a **zero baseline**
   inside the plot; a negative bar extends **below** it. Gains go up, losses go down, as a
   reader expects.

Both are covered by `test_chart_fidelity.py`. The renderer stays pure Python — no plotting
dependency — using the 5x7 bitmap font in `analytics/pixfont.py`.

## Scope

A live proof (needs a model and a key), not a CI guard. The deterministic guard for the
labelled output is `test_chart_fidelity.py`, which decodes the PNG and asserts the title,
category, value and baseline pixels are drawn.
