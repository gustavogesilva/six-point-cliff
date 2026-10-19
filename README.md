# The Six-Point Cliff

This repo holds the model behind the [Proteo Markets](https://proteomarkets.substack.com) post [*The Six-Point Cliff That Could Bring Us Back To 2008*](https://proteomarkets.substack.com/p/the-six-point-cliff-that-could-bring), published on 19 October 2026. The model asks how a scare in private credit would reach the banks that lend to it, and how likely it is that a large bank ends up below its legal capital minimum.

It has two halves that do the same arithmetic. The Excel workbook in `model/` has live formulas you can click through. The Python engine in `src/` runs the same formulas thousands of times for the Monte Carlo, and a Checks sheet in the workbook confirms the two agree.

![G-SIBs below their capital buffer as private-credit marks fall](post/fig/fig2_cliff.png)

## Results as of 19 October 2026

- One risk at a time, at the severity people currently worry about, no G-SIB falls below its capital buffer.
- With panic switched on, the number of G-SIBs below their buffers jumps from 1 to 10 when private-credit loan marks move from 83 to 82. Losses across the 24 banks go from $107bn to $390bn on that one-point move. Listed BDC prices put the mark at about 88 today.
- The probability that at least one G-SIB falls below the 4.5% CET1 minimum within about three years is 7.6% (2.6% a year). A normal-distribution model with no panic gives 1.0%.
- State Street appears in every simulation where a G-SIB breaches the minimum. That comes from treating its $22bn call-report line of loans to business-credit intermediaries as junk-pool lending. Treated as investment-grade fund lending instead, its probability drops to 0.3% and the overall number to 2.3%.

These are probabilities inside the model, under its assumptions. They are not forecasts and nothing here is investment advice.

## What's in the repo

```
model/
  Private_Credit_Contagion_Model.xlsx   the workbook (23 sheets, live formulas)
src/
  engine.py           the model in Python: 11 standalone risk modules, 8 contagion rounds, Monte Carlo
  params.py           scenario table, global constants, price-impact parameters, credit tables
  layout.py           column layout of the Inputs_Banks sheet
  xlsx_io.py          reads every input and scenario back from the workbook
  build_xlsx.py       writes the workbook with its formulas from data/inputs.json and params.py
  post.py             recalculates the workbook and fills the value sheets (PyCheck, Monte Carlo, reverse stress)
  post_fat_tails.py   the Fat_Tails sheet (run by post.py)
  fat_tail_runs.py    probability ladder, trigger probabilities and sensitivities
  post_runs.py        every model number quoted in the post
  verify.py           checks Excel against Python in all ten scenarios
  recalc.py           headless LibreOffice recalculation
data/
  inputs.json         per-bank, per-BDC and per-deal inputs, with a source for every field
  results/            output of the scripts above (JSON)
post/
  post.md             the article as drafted (published version on Substack, linked above)
  fig/                charts and tables as published (1456 px wide)
  charts.py, tables.py, build.py, fetch_prices.py   the scripts that make them
```

## How the model works

The model covers 24 institutions: 13 US banks, 10 from Europe, Japan and Canada, and Jefferies. Each one gets losses from 11 separate channels. These are lending to private-credit vehicles (with a look-through to the loans behind them), fund finance, structured lending, PE-owned insurers, AI and GPU deals, trading books, commercial property, rate losses, lost risk-transfer relief, written total return swaps and prime brokerage.

The banks are then connected through funding and asset markets over eight rounds. Capital losses lead to downgrades. Downgrades trigger contractual outflows and deposit, wholesale and repo run-off. Shortfalls force asset sales, the sales move prices, and the new prices re-mark everyone's holdings. When a bank defaults, its creditors take interbank losses.

Panic sits on top of that loop. Each round the model reads the public news: BDC coverage breaches, the discount on private-credit loans, bank downgrades and buffer breaches, any failure. It turns that into a panic level between 0 and 1, and the panic level pushes on every channel at once. It deepens the credit factor, widens spreads and forces marks to market. It increases fund selling, redemptions and runs on the weakest banks, and it applies a common discount to every risky asset class.

The Monte Carlo draws credit, AI, liquidity and rate factors from a Student-t distribution (four degrees of freedom) with a 10% crisis regime in which correlations go to 0.95. It then runs each draw through the full engine. The Method sheet in the workbook gives every equation.

## Running it

You need Python 3.10 or later. LibreOffice is only needed to rebuild or verify the workbook.

```bash
pip install -r requirements.txt

python src/engine.py              # run the ten named scenarios on data/inputs.json
python src/post_runs.py           # numbers in the post -> data/results/post_runs.json (several minutes)
python src/fat_tail_runs.py       # Fat_Tails results -> data/results/fat_tail_results.json (several minutes)

python src/build_xlsx.py          # rebuild model/Private_Credit_Contagion_Model.xlsx
python src/post.py                # recalculate it and fill the value sheets (about 5 minutes)
python src/verify.py              # Excel vs Python in every scenario (about 15 minutes)
```

On Windows, point the scripts at LibreOffice with `set SOFFICE=C:\Program Files\LibreOffice\program\soffice.exe`.

To redraw the post's images:

```bash
python post/fetch_prices.py       # Yahoo Finance prices into data/prices/ (not committed)
python post/charts.py loop cliff ladder banks market
pip install playwright && playwright install chromium
python post/tables.py
python post/build.py              # post.md -> post.html with the images embedded
```

The published market chart used intraday prices on 19 October. A rerun uses that day's close, so the bars can differ by a fraction of a point.

## Using the workbook

Pick a scenario in the Dashboard's C4 cell, or edit the yellow Custom column on the Scenarios sheet. The `sw_M1` to `sw_M11` rows switch the risk modules on and off, and `fs_on`, `ib_on`, `liq_on` and `panic_on` do the same for the contagion channels. Every bank input sits on Inputs_Banks, Holdings, BDC, BDC_EAD or AI_Deals, and the Sources sheet gives its source. Orange cells are estimates.

Excel recalculates the formula sheets as soon as you change something. The Monte Carlo, reverse-stress and Fat_Tails sheets hold values written by Python. To refresh them after you change inputs, save the file and run `python src/post.py path/to/your.xlsx`.

## Data

US bank CET1 and risk-weighted assets are at 30 September 2026, from the third-quarter releases of the 12 banks that had reported by 19 October. First Citizens reports on 23 October and stays at 30 June. Everything else on the US side comes from the 30 June 2026 FFIEC call reports and second-quarter 10-Qs. Non-US banks use their latest reports before October, mostly first-half 2026. BDC data comes from second-quarter 10-Qs, and listed BDC price-to-NAV ratios are rolled forward to 19 October prices.

Several inputs are estimates and are flagged as such: bank shares of BDC facilities and AI deals, some liquidity items and the non-disclosed private-credit books. The price-impact coefficients, run-off speeds, panic parameters and Monte Carlo lever mapping are judgment calls. All of them are editable on the Scenarios, Globals and Holdings sheets, and the Fat_Tails sheet shows how much the result moves when the main ones change.
