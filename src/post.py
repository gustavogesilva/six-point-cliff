"""Fill the value sheets of the workbook from the Python engine.

Usage (from the repo root):  python src/post.py [workbook.xlsx]
Recalculates the workbook, reads every input back from it, runs the engine and writes PyCheck, Standalone_Grid,
Reverse_Stress, MC_Summary, MC_Distribution and Fat_Tails (from data/results/fat_tail_results.json), then recalculates again.
Needs LibreOffice; set RECALC_SCRIPT to use a recalculation script other than src/recalc.py.
"""
import json, subprocess, sys, shutil
from pathlib import Path
import numpy as np
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter as CLT
from openpyxl.chart import BarChart, LineChart, Reference
import engine as E, xlsx_io as X

import os
ROOT = Path(__file__).resolve().parents[1]
RECALC = os.environ.get('RECALC_SCRIPT', str(ROOT / 'src' / 'recalc.py'))  # LibreOffice recalculation helper
PATH = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'model' / 'Private_Credit_Contagion_Model.xlsx')
AR = 'Arial'
F_N = Font(name=AR, size=10); F_B = Font(name=AR, size=10, bold=True); F_T = Font(name=AR, size=14, bold=True)
F_H = Font(name=AR, size=10, bold=True, color='FFFFFF'); F_NOTE = Font(name=AR, size=9, italic=True, color='595959')
FILL_H = PatternFill('solid', fgColor='1F3864'); FILL_SUB = PatternFill('solid', fgColor='D9E1F2')
NUM = '#,##0.0;(#,##0.0);"-"'; PCT = '0.0%;(0.0%);"-"'; PCT2 = '0.00%;(0.00%);"-"'; INT = '0;(0);"-"'; NUM2 = '#,##0.00;(#,##0.00);"-"'
MODS = ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8', 'M9', 'M10', 'M11']
MODN = {'M1': 'Back-leverage look-through', 'M2': 'Fund finance', 'M3': 'ABF / structured entities', 'M4': 'PE-owned insurers', 'M5': 'AI / GPU / data centres',
        'M6': 'Trading & HFS MTM', 'M7': 'CRE', 'M8': 'Rates (AFS + forced HTM sales)', 'M9': 'SRT relief lost', 'M10': 'Written sub-IG TRS', 'M11': 'Prime / margin gap'}

def recalc(p):
    out = subprocess.run(['python3', RECALC, p, '240'], capture_output=True, text=True).stdout
    return json.loads(out)

def w(ws, ref, v, font=F_N, fmt=None, fill=None):
    c = ws[ref]; c.value = v; c.font = font
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    return c

def hdr(ws, row, col, labels):
    for k, l in enumerate(labels):
        c = ws.cell(row=row, column=col + k, value=l); c.font = F_H; c.fill = FILL_H
        c.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
    ws.row_dimensions[row].height = 40

def clear(ws, from_row=3):
    for row in ws.iter_rows(min_row=from_row):
        for c in row: c.value = None

r = recalc(PATH); print('recalc 1', r.get('status'), r.get('total_errors'))
inp = X.read_inputs(PATH); cfg = inp['cfg']; ids = inp['ids']; nb = len(ids); gs = inp['gsib'] > 0
SC = cfg['SCEN']

# ------------------------------------------------ all scenarios
res = {}
for s in SC:
    o = E.run(inp, E.scenario(s, cfg)); res[s] = (o, E.system(inp, o))
wb = load_workbook(PATH)
py = wb['PyCheck']; clear(py, 1)
w(py, 'A1', 'Python engine results for every scenario (values written by post.py; used by Checks to verify the Excel formulas)', F_T)
NSC = len(SC); C1, C2, C3 = 3, 4 + NSC, 5 + 2 * NSC   # must match the Checks formulas in build_xlsx.py
hdr(py, 5, 1, ['Id', 'Institution'] + SC + [''] + SC + [''] + SC)
w(py, f'{CLT(C1)}4', 'CET1 ratio final', F_B, fill=FILL_SUB); w(py, f'{CLT(C2)}4', 'Standalone loss ($bn)', F_B, fill=FILL_SUB); w(py, f'{CLT(C3)}4', 'Final loss ($bn)', F_B, fill=FILL_SUB)
for i, bid in enumerate(ids):
    w(py, f'A{6 + i}', bid); w(py, f'B{6 + i}', inp['names'][i])
    for j, s in enumerate(SC):
        o, sy = res[s]
        w(py, f'{CLT(C1 + j)}{6 + i}', float(o['fin']['ratio'][0, i]), fmt=PCT2)
        w(py, f'{CLT(C2 + j)}{6 + i}', float(o['std']['total'][0, i]), fmt=NUM)
        w(py, f'{CLT(C3 + j)}{6 + i}', float(o['fin']['L'][0, i]), fmt=NUM)
w(py, 'A31', 'System', F_B, fill=FILL_SUB)
labs = [('G-SIBs below MDA', 'n_gsib_mda', INT), ('G-SIBs below minimum', 'n_gsib_min', INT), ('Defaults / resolutions', 'n_default', INT),
        ('Standalone loss ($bn)', 'loss_std', NUM), ('Final loss ($bn)', 'loss_fin', NUM), ('Shortfall to MDA ($bn)', 'shortfall', NUM),
        ('Forced sales ($bn)', 'fs_sales', NUM), ('Systemic (1/0)', 'systemic', INT)]
for k, (lab, key, fmt) in enumerate(labs):
    w(py, f'B{32 + k}', lab)
    for j, s in enumerate(SC): w(py, f'{CLT(3 + j)}{32 + k}', float(res[s][1][key][0]), fmt=fmt)
for k in range(1, 40): py.column_dimensions[CLT(k)].width = 11
py.column_dimensions['B'].width = 24

# ------------------------------------------------ standalone module grid (each module alone, no contagion)
sg = wb['Standalone_Grid']; clear(sg, 1)
w(sg, 'A1', 'Each risk on its own: module losses with every other module and all contagion channels switched off (USD bn, pre-tax)', F_T)
w(sg, 'A2', 'Severity = the parameter set of the named scenario. Bottom rows: CET1 impact (pp of RWA) and the number of G-SIBs pushed below MDA by that module alone.', F_NOTE)
row = 4
GRID = {}
for sev in ['Software/AI repricing', 'GPU obsolescence', 'Credit 2009', 'Rerating cascade', '2008-combined', 'Panic cascade']:
    w(sg, f'A{row}', f'Severity: {sev}', F_B, fill=FILL_SUB)
    hdr(sg, row + 1, 1, ['Id', 'Institution'] + [f'{m} {MODN[m]}' for m in MODS] + ['All modules (no contagion)', 'Full model incl. contagion'])
    base = E.scenario(sev, cfg)
    cols = {}
    for m in MODS:
        p = dict(base); p.update({f'sw_{x}': 0.0 for x in MODS}); p[f'sw_{m}'] = 1.0; p.update(fs_on=0.0, ib_on=0.0, liq_on=0.0)
        o = E.run(inp, p); cols[m] = o['std'][m][0]
    p = dict(base); p.update(fs_on=0.0, ib_on=0.0, liq_on=0.0); oall = E.run(inp, p)
    ofull = res[sev][0]
    GRID[sev] = cols
    for i, bid in enumerate(ids):
        rr = row + 2 + i
        w(sg, f'A{rr}', bid); w(sg, f'B{rr}', inp['names'][i])
        for k, m in enumerate(MODS): w(sg, f'{CLT(3 + k)}{rr}', float(cols[m][i]), fmt=NUM)
        w(sg, f'{CLT(3 + len(MODS))}{rr}', float(oall['std']['total'][0, i]), fmt=NUM)
        w(sg, f'{CLT(4 + len(MODS))}{rr}', float(ofull['fin']['L'][0, i]), fmt=NUM)
    rt = row + 2 + nb
    w(sg, f'B{rt}', 'Total ($bn)', F_B); w(sg, f'B{rt + 1}', 'Avg CET1 impact (pp, simple avg)', F_B); w(sg, f'B{rt + 2}', 'G-SIBs below MDA from this alone', F_B)
    allcols = [cols[m] for m in MODS] + [oall['std']['total'][0], ofull['fin']['L'][0]]
    for k, v in enumerate(allcols):
        cl = CLT(3 + k)
        w(sg, f'{cl}{rt}', float(v.sum()), F_B, NUM)
        w(sg, f'{cl}{rt + 1}', float((v / inp['rwa']).mean() * 100), F_B, NUM2)
        ratio = (inp['cet1'] - v) / inp['rwa']
        w(sg, f'{cl}{rt + 2}', int(((ratio < inp['req']) & gs).sum()), F_B, INT)
    row = rt + 5
for k in range(1, 16): sg.column_dimensions[CLT(k)].width = 13
sg.column_dimensions['A'].width = 7; sg.column_dimensions['B'].width = 26

# ------------------------------------------------ reverse stress along the joint factor
rs = wb['Reverse_Stress']; clear(rs, 1)
w(rs, 'A1', 'Reverse stress: how bad does the common factor have to get before the system breaks?', F_T)
w(rs, 'A2', 'All levers move together with one factor z (credit, AI and liquidity factors set equal to z, rates unchanged), using the Monte Carlo mapping functions (see MC_Summary), with no PPNR credit (instantaneous) and the panic channel on at Baseline settings (S0 = 0.10). Generic pool value is the hold value of a typical private-credit loan book as % of carrying value (the mark).', F_NOTE)
zs = np.round(np.arange(0.0, -3.001, -0.0625), 4)
rows = []
for cb in (1, 0):
    p = E.mc_params_from(zs, zs, zs, np.zeros(len(zs)), cb, cfg); p['ppnr_q'] = 0.0   # instantaneous: no earnings credit
    o = E.run(inp, p); sy = E.system(inp, o)
    rows.append((cb, p, o, sy))
hdr(rs, 4, 1, ['z (joint factor)', 'Prob. of worse (one-sided)', 'Pool 3-yr PD', 'Generic pool value (mark)', 'Pool value, liquidated',
               'Backstop', 'Total loss ($bn)', 'G-SIBs < MDA', 'G-SIBs < min', 'Defaults', 'Shortfall to MDA ($bn)', 'Forced sales ($bn)', 'Systemic'] + ids)
rr = 5
from scipy.stats import norm
for cb, p, o, sy in rows:
    for k, z in enumerate(zs):
        vl = float(o['Vh_g'][k, 0] * (1 - o['fin']['FS'][k, E.CLK.index('PRIV_CREDIT_LOANS')]))
        vals = [float(z), float(norm.cdf(z)), float(o['PDg'][k, 0]), float(o['Vh_g'][k, 0]), vl, 'on' if cb else 'off',
                float(sy['loss_fin'][k]), int(sy['n_gsib_mda'][k]), int(sy['n_gsib_min'][k]), int(sy['n_default'][k]), float(sy['shortfall'][k]),
                float(sy['fs_sales'][k]), 'YES' if sy['systemic'][k] else 'no'] + [float(x) for x in o['fin']['ratio'][k]]
        fm = [NUM2, PCT2, PCT, PCT, PCT, None, NUM, INT, INT, INT, NUM, NUM, None] + [PCT] * nb
        for c, (v, f) in enumerate(zip(vals, fm)): w(rs, f'{CLT(1 + c)}{rr}', v, fmt=f)
        rr += 1
    rr += 1
# thresholds
thr = []
for cb, p, o, sy in rows:
    def first(mask):
        idx = np.where(mask)[0]
        return (float(zs[idx[0]]), float(o['Vh_g'][idx[0], 0])) if len(idx) else (None, None)
    thr.append((cb, first(sy['n_gsib_mda'] >= 1), first(sy['systemic'] > 0), first(sy['n_gsib_min'] >= 1), first(sy['n_default'] >= 1)))
w(rs, f'A{rr + 1}', 'Thresholds (first z on the grid where the event occurs; mark = generic pool hold value)', F_B, fill=FILL_SUB)
hdr(rs, rr + 2, 1, ['Backstop', 'First G-SIB below MDA: z', 'mark', 'Systemic: z', 'mark', 'First G-SIB below minimum: z', 'mark', 'First default: z', 'mark'])
for k, (cb, a, b, c, d) in enumerate(thr):
    vals = ['on' if cb else 'off', a[0], a[1], b[0], b[1], c[0], c[1], d[0], d[1]]
    for cc, v in enumerate(vals): w(rs, f'{CLT(1 + cc)}{rr + 3 + k}', v, fmt=(NUM2 if cc % 2 == 1 else PCT) if cc else None)
THR = thr
dsh = wb['Dashboard']
w(dsh, 'H13', 'REVERSE STRESS (joint factor, no earnings credit; see Reverse_Stress)', F_B, fill=FILL_SUB)
w(dsh, 'L13', 'z', F_B); w(dsh, 'M13', 'Pool mark', F_B)
for k, (lab, col) in enumerate([('First G-SIB below MDA', 'B'), ('Systemic (>=3 G-SIBs below MDA)', 'D'), ('First G-SIB below 4.5% minimum', 'F'), ('First default / resolution', 'H')]):
    w(dsh, f'H{14 + k}', lab)
    w(dsh, f'L{14 + k}', f'=Reverse_Stress!{col}{rr + 3}', Font(name=AR, size=10, bold=True, color='008000'), NUM2)
    w(dsh, f'M{14 + k}', f'=Reverse_Stress!{CLT(ord(col) - 64 + 1)}{rr + 3}', Font(name=AR, size=10, bold=True, color='008000'), PCT)
w(dsh, 'H18', 'Backstop ON row shown; OFF row on Reverse_Stress.', F_NOTE)
for k in range(1, 14 + nb): rs.column_dimensions[CLT(k)].width = 11
ch = LineChart(); ch.title = 'G-SIBs below MDA vs joint stress factor (backstop on)'; ch.y_axis.title = 'count'; ch.x_axis.title = 'z'
ch.add_data(Reference(rs, min_col=8, min_row=4, max_row=4 + len(zs)), titles_from_data=True)
ch.add_data(Reference(rs, min_col=9, min_row=4, max_row=4 + len(zs)), titles_from_data=True)
ch.set_categories(Reference(rs, min_col=1, min_row=5, max_row=4 + len(zs))); ch.height = 8; ch.width = 18
rs.add_chart(ch, f'B{rr + 7}')

# ------------------------------------------------ Monte Carlo
N = 10000
BASE = dict(tails='t', nu=4, pi_c=0.10, mu_z=-0.3, panic=dict(S0=0.15, news0=0.05))   # same setting as fat_tail_runs.py (L4)
mcres, mcg = {}, {}
for cb in (1, 0):
    mcres[cb] = E.mc(inp, N, cb=cb, **BASE)
    mcg[cb] = E.mc(inp, N, cb=cb)   # first version: Gaussian factors, no panic (comparison)
ms = wb['MC_Summary']; clear(ms, 1)
w(ms, 'A1', f'Monte Carlo: {N:,} joint draws (seed 20261008), full engine incl. {E.ROUNDS} contagion rounds with panic / information contagion; ~3-year horizon', F_T)
w(ms, 'A2', 'Factors: z (credit), z_AI = 0.5 z + 0.87 e1, z_liq = 0.6 z + 0.8 e2, dy = 1% x e3, all sharing one chi-square mixing variable (multivariate Student-t, nu = 4, unit variance: extremes arrive together). Crisis regime with probability 10%: AI and liquidity loadings 0.95 (correlations -> 1) and panic floor S0 + 0.20. Mean of z shifted -0.3 and S0 = 0.15 to condition on today. Every scenario lever is a deterministic function of the factors (table below). PPNR credited for 2 quarters, haircut up to 50% as z falls to -2. Columns D-E = first version (Gaussian, no panic) for comparison. Probabilities are model-conditional, not forecasts; 1-year and 3-month equivalents on Fat_Tails.', F_NOTE)
hdr(ms, 4, 1, ['System metric', 'Backstop ON', 'Backstop OFF', 'Gaussian, no panic: ON', 'Gaussian, no panic: OFF'])
def met(sy):
    L = sy['loss_fin']
    return [sy['systemic'].mean(), (sy['n_gsib_mda'] >= 1).mean(), (sy['n_gsib_mda'] >= 3).mean(), (sy['n_gsib_min'] >= 1).mean(), (sy['n_default'] >= 1).mean(),
            L.mean(), np.percentile(L, 50), np.percentile(L, 95), np.percentile(L, 99), np.percentile(L, 99.9),
            np.percentile(sy['shortfall'], 99), np.percentile(sy['shortfall'], 99.9), np.percentile(sy['n_gsib_mda'], 99), sy['n_gsib_mda'].max()]
mlabs = [('P(systemic: >=3 G-SIBs < MDA or any G-SIB default)', PCT2), ('P(>=1 G-SIB below MDA)', PCT2), ('P(>=3 G-SIBs below MDA)', PCT2),
         ('P(>=1 G-SIB below 4.5% minimum)', PCT2), ('P(any institution in default / resolution)', PCT2), ('Mean total loss ($bn)', NUM),
         ('Median total loss ($bn)', NUM), ('95th pct total loss ($bn)', NUM), ('99th pct total loss ($bn)', NUM), ('99.9th pct total loss ($bn)', NUM),
         ('99th pct shortfall to MDA ($bn)', NUM), ('99.9th pct shortfall to MDA ($bn)', NUM), ('99th pct # G-SIBs below MDA', INT), ('Max # G-SIBs below MDA', INT)]
M1v, M0v = met(mcres[1][2]), met(mcres[0][2]); G1v, G0v = met(mcg[1][2]), met(mcg[0][2])
for k, (lab, fmt) in enumerate(mlabs):
    w(ms, f'A{5 + k}', lab); w(ms, f'B{5 + k}', float(M1v[k]), F_B, fmt); w(ms, f'C{5 + k}', float(M0v[k]), F_B, fmt)
    w(ms, f'D{5 + k}', float(G1v[k]), F_N, fmt); w(ms, f'E{5 + k}', float(G0v[k]), F_N, fmt)
r0 = 5 + len(mlabs) + 2
w(ms, f'A{r0}', 'Per institution', F_B, fill=FILL_SUB)
hdr(ms, r0 + 1, 1, ['Id', 'Institution', 'P(MDA breach) ON', 'P(<4.5%) ON', 'P(default) ON', 'Mean CET1 ratio ON', '5th pct CET1 ON', '1st pct CET1 ON',
                    '99th pct loss ON ($bn)', 'P(MDA breach) OFF', 'P(<4.5%) OFF', 'P(default) OFF', '1st pct CET1 OFF', '99th pct loss OFF ($bn)'])
PB = {}
for i, bid in enumerate(ids):
    rr = r0 + 2 + i
    vals = [bid, inp['names'][i]]
    for cb in (1, 0):
        p, o, sy = mcres[cb]; rat = o['fin']['ratio'][:, i]; L = o['fin']['L'][:, i]
        if cb:
            vals += [(rat < inp['req'][i]).mean(), (rat < 0.045).mean(), (o['fin']['dflt'][:, i] > 0).mean(), rat.mean(), np.percentile(rat, 5), np.percentile(rat, 1), np.percentile(L, 99)]
        else:
            vals += [(rat < inp['req'][i]).mean(), (rat < 0.045).mean(), (o['fin']['dflt'][:, i] > 0).mean(), np.percentile(rat, 1), np.percentile(L, 99)]
    PB[bid] = vals
    fm = [None, None, PCT2, PCT2, PCT2, PCT, PCT, PCT, NUM, PCT2, PCT2, PCT2, PCT, NUM]
    for c, (v, f) in enumerate(zip(vals, fm)): w(ms, f'{CLT(1 + c)}{rr}', v if isinstance(v, str) else float(v), fmt=f)
# tail attribution
r1 = r0 + 2 + nb + 2
w(ms, f'A{r1}', 'What drives the tail? Mean standalone loss by module, all draws vs systemic draws (backstop ON, $bn, all banks)', F_B, fill=FILL_SUB)
hdr(ms, r1 + 1, 1, ['Module', 'Mean, all draws', 'Mean, systemic draws', 'Mean, worst 1% of draws', 'Share of standalone loss in worst 1%'])
p, o, sy = mcres[1]; sysm = sy['systemic'] > 0; worst = sy['loss_fin'] >= np.percentile(sy['loss_fin'], 99)
tot_w = o['std']['total'][worst].sum(1).mean()
for k, m in enumerate(MODS):
    v = o['std'][m].sum(1)
    vals = [f'{m} {MODN[m]}', v.mean(), v[sysm].mean() if sysm.any() else 0, v[worst].mean(), v[worst].mean() / tot_w]
    for c, (vv, f) in enumerate(zip(vals, [None, NUM, NUM, NUM, PCT])): w(ms, f'{CLT(1 + c)}{r1 + 2 + k}', vv if isinstance(vv, str) else float(vv), fmt=f)
ctg = (o['fin']['L'] - o['std']['total']).sum(1)
w(ms, f'A{r1 + 2 + len(MODS)}', 'Contagion add-on (fire sales, runs, interbank, re-marks)')
for c, vv in enumerate([ctg.mean(), ctg[sysm].mean() if sysm.any() else 0, ctg[worst].mean()]): w(ms, f'{CLT(2 + c)}{r1 + 2 + len(MODS)}', float(vv), fmt=NUM)
# mapping table
r2 = r1 + 4 + len(MODS)
w(ms, f'A{r2}', 'Lever mapping used in the Monte Carlo (nz = max(0,-z), nai = max(0,-z_AI), nl = max(0,-z_liq); c() = clip)', F_B, fill=FILL_SUB)
import inspect
src = inspect.getsource(E.mc_params_from)
for k, line in enumerate([l for l in src.splitlines() if '=' in l and not l.strip().startswith('#')][:60]):
    w(ms, f'A{r2 + 1 + k}', line.strip(), F_NOTE)
ms.column_dimensions['A'].width = 58; ms.column_dimensions['B'].width = 16
for k in range(3, 15): ms.column_dimensions[CLT(k)].width = 13

md = wb['MC_Distribution']; clear(md, 1)
w(md, 'A1', 'Monte Carlo distributions (backstop ON unless stated)', F_T)
L1 = mcres[1][2]['loss_fin']; L0 = mcres[0][2]['loss_fin']
edges = [0, 25, 50, 75, 100, 150, 200, 300, 400, 500, 750, 1000, 1500, 1e9]
hdr(md, 3, 1, ['Total loss bucket ($bn)', 'Frequency ON', 'Frequency OFF'])
for k in range(len(edges) - 1):
    lab = f'{edges[k]:.0f}-{edges[k + 1]:.0f}' if edges[k + 1] < 1e8 else f'>{edges[k]:.0f}'
    w(md, f'A{4 + k}', lab); w(md, f'B{4 + k}', float(((L1 >= edges[k]) & (L1 < edges[k + 1])).mean()), fmt=PCT2)
    w(md, f'C{4 + k}', float(((L0 >= edges[k]) & (L0 < edges[k + 1])).mean()), fmt=PCT2)
hdr(md, 3, 5, ['# G-SIBs below MDA', 'Frequency ON', 'Frequency OFF'])
for k in range(0, 19):
    w(md, f'E{4 + k}', k); w(md, f'F{4 + k}', float((mcres[1][2]['n_gsib_mda'] == k).mean()), fmt=PCT2)
    w(md, f'G{4 + k}', float((mcres[0][2]['n_gsib_mda'] == k).mean()), fmt=PCT2)
ch = BarChart(); ch.title = 'Distribution of total losses (backstop ON / OFF)'; ch.add_data(Reference(md, min_col=2, max_col=3, min_row=3, max_row=3 + len(edges) - 1), titles_from_data=True)
ch.set_categories(Reference(md, min_col=1, min_row=4, max_row=3 + len(edges) - 1)); ch.height = 8; ch.width = 18; md.add_chart(ch, 'I3')
hdr(md, 26, 1, ['Draw', 'z credit', 'z AI', 'z liquidity', 'dy', 'Pool 3-yr PD', 'Total loss ($bn)', 'G-SIBs < MDA', 'G-SIBs < min', 'Defaults', 'Systemic', 'Crisis regime', 'Panic S, final round'])
p, o, sy = mcres[1]
for k in range(1000):
    vals = [k + 1, p['z'][k], p['z_ai'][k], p['zl'][k], p['dy'][k], o['PDg'][k, 0], sy['loss_fin'][k], sy['n_gsib_mda'][k], sy['n_gsib_min'][k], sy['n_default'][k], sy['systemic'][k],
            sy['crisis'][k], o['fin']['S'][k, 0]]
    for c, (v, f) in enumerate(zip(vals, [INT, NUM2, NUM2, NUM2, PCT2, PCT, NUM, INT, INT, INT, INT, INT, PCT])): w(md, f'{CLT(1 + c)}{27 + k}', float(v), fmt=f)
for k in range(1, 14): md.column_dimensions[CLT(k)].width = 13

# ------------------------------------------------ fat tails: ladder, trigger-conditional probabilities, sensitivities
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'post_fat_tails.py')).read())

wb.save(PATH)
r = recalc(PATH); print('recalc 2', r.get('status'), r.get('total_errors'), r.get('error_summary'))
json.dump(dict(thr=THR, mc_on=[float(x) for x in M1v], mc_off=[float(x) for x in M0v], pb={k: [v if isinstance(v, str) else float(v) for v in vals] for k, vals in PB.items()},
               scen={s: {k: float(res[s][1][k][0]) for k in ['n_gsib_mda', 'n_gsib_min', 'n_default', 'loss_std', 'loss_fin', 'shortfall', 'fs_sales', 'systemic']} for s in SC},
               ratios={s: dict(zip(ids, [float(x) for x in res[s][0]['fin']['ratio'][0]])) for s in SC},
               grid={sev: {m: float(GRID[sev][m].sum()) for m in MODS} for sev in GRID}), open(ROOT / 'data' / 'results' / 'summary.json', 'w'), indent=1)
print('done')
