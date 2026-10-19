"""Probability ladder, trigger-conditional probabilities and sensitivities for the Fat_Tails sheet.

Usage (from the repo root):  python src/fat_tail_runs.py [N] [NS]
N  = draws per ladder / trigger row (default 20000), NS = draws per sensitivity row (default 10000).
Writes data/results/fat_tail_results.json, which src/post.py puts on the Fat_Tails sheet.
"""
import json, sys
from pathlib import Path
import numpy as np
import engine as E

ROOT = Path(__file__).resolve().parents[1]
inp = E.load_json(ROOT / 'data' / 'inputs.json'); ids = inp['ids']; gs = inp['gsib'] > 0
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
NS = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
ex = np.array([b != 'STT' for b in ids])
BASE = dict(tails='t', nu=4, pi_c=0.10, mu_z=-0.3, panic=dict(S0=0.15, news0=0.05))


def summ(o, sy):
    fin = o['fin']; r = fin['ratio']; bm = (r < 0.045) & gs
    return dict(sys=float(sy['systemic'].mean()), mda=float((sy['n_gsib_mda'] >= 1).mean()), gmin=float(bm.any(1).mean()),
                dflt=float((sy['n_default'] >= 1).mean()), g2=float((sy['n_gsib_min'] >= 2).mean()),
                exstt=float((bm & ex).any(1).mean()), ex2=float(((bm & ex).sum(1) >= 2).mean()),
                p99=float(np.percentile(sy['loss_fin'], 99)), mean=float(sy['loss_fin'].mean()),
                bank_min={b: float((r[:, i] < 0.045).mean()) for i, b in enumerate(ids)},
                bank_mda={b: float((r[:, i] < inp['req'][i]).mean()) for i, b in enumerate(ids)})


TRIG = {
 'None (today)': {},
 'T1 Largest semi-liquid funds break gates (honour 20%)': dict(news0=lambda p: p['news0'] + 0.15, red_rate=lambda p: np.maximum(p['red_rate'], 0.20)),
 'T2 Private-credit marks cut 10 points': dict(gap=lambda p: p['gap'] + 0.10),
 'T3 Non-govt repo seizes (haircuts +15, MMF pull +50%)': dict(dh=lambda p: p['dh'] + 0.15, pull_base=lambda p: np.minimum(1, p['pull_base'] + 0.5)),
 'T4 A PE-owned insurer fails (FA repo + facilities lost)': dict(news0=lambda p: p['news0'] + 0.35, pd_ins=1.0, ins_run=1.0),
 'T5 A G-SIB fails for reasons outside the model': dict(news0=lambda p: p['news0'] + 1.0),
 'T6 T1 + T2 + T3 together': dict(news0=lambda p: p['news0'] + 0.15, red_rate=lambda p: np.maximum(p['red_rate'], 0.20), gap=lambda p: p['gap'] + 0.10,
                                  dh=lambda p: p['dh'] + 0.15, pull_base=lambda p: np.minimum(1, p['pull_base'] + 0.5)),
}
LAD = [('L0 Gaussian factors, no panic', dict(tails='gauss', panic=None)),
       ('L1 + fat tails (Student-t, nu=4)', dict(tails='t', nu=4, panic=None)),
       ('L2 + crisis regime (correlations to 0.95, 10%)', dict(tails='t', nu=4, pi_c=0.10, panic=None)),
       ('L3 + panic / information contagion', dict(tails='t', nu=4, pi_c=0.10, panic=dict(S0=0.10, news0=0.05))),
       ('L4 + conditioned on today (credit factor -0.3, panic 0.15)', BASE)]

res = {'N': N, 'NS': NS, 'ladder': {}, 'triggers': {}, 'sens': {}}
for cb in (1, 0):
    for name, kw in LAD:
        p, o, sy = E.mc(inp, N, cb=cb, **kw); res['ladder'][f'{cb}|{name}'] = summ(o, sy)
        print(cb, name, round(res['ladder'][f'{cb}|{name}']['gmin'], 4), flush=True)
    for name, ov in TRIG.items():
        p, o, sy = E.mc(inp, N, cb=cb, overrides=ov, **BASE); res['triggers'][f'{cb}|{name}'] = summ(o, sy)
        print(cb, name, round(res['triggers'][f'{cb}|{name}']['gmin'], 4), flush=True)


def with_global(key, val):
    d = E.default_cfg(); d['G'][key] = val; inp2 = dict(inp); inp2['cfg'] = d; return inp2


# sensitivity of the L4 result to the judgment parameters (backstop on unless stated)
for key, vals in [('theta_news', [0.30, 0.45, 0.60]), ('gamma_pan', [1.0, 1.5, 2.5]), ('w_mda', [0.75, 1.5, 2.25]), ('n_weak', [3, 6, 9])]:
    for v in vals:
        p, o, sy = E.mc(with_global(key, v), NS, cb=1, **BASE); res['sens'][f'{key}={v}'] = summ(o, sy)
for nu in (3, 4, 8, 30):
    kw = dict(BASE); kw['nu'] = nu
    p, o, sy = E.mc(inp, NS, cb=1, **kw); res['sens'][f'nu={nu}'] = summ(o, sy)
for upw in (0.10, 0.20, 0.30):
    p, o, sy = E.mc(inp, NS, cb=1, overrides=dict(u_pan_weak=upw), **BASE); res['sens'][f'u_pan_weak={upw}'] = summ(o, sy)
for upw in (0.0, 0.20, 0.60):
    p, o, sy = E.mc(inp, NS, cb=0, overrides=dict(u_pan_weak=upw), **BASE); res['sens'][f'u_pan_weak={upw} (no backstop)'] = summ(o, sy)
for s0 in (0.05, 0.15, 0.30, 0.50):
    kw = dict(BASE); kw['panic'] = dict(S0=s0, news0=0.05)
    p, o, sy = E.mc(inp, NS, cb=1, **kw); res['sens'][f'S0={s0}'] = summ(o, sy)
print('sensitivities done', flush=True)

(ROOT / 'data' / 'results').mkdir(parents=True, exist_ok=True)
json.dump(res, open(ROOT / 'data' / 'results' / 'fat_tail_results.json', 'w'), indent=1)
print('done')
