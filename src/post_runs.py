"""Every model number quoted in the post (inputs as of 19 Oct 2026): scenarios, reverse stress, probability ladder, triggers.

Usage (from the repo root):  python src/post_runs.py [N]     (N = draws per row, default 20000)
Writes data/results/post_runs.json, which post/charts.py and post/tables.py read.
"""
import json, sys
from pathlib import Path
import numpy as np, engine as E
ROOT = Path(__file__).resolve().parents[1]
inp = E.load_json(ROOT / 'data' / 'inputs.json'); ids = inp['ids']; gs = inp['gsib'] > 0; cfg = E.default_cfg()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
ex = np.array([b != 'STT' for b in ids])
out = {'scen': {}, 'rev': {}, 'ladder': {}, 'trig': {}}

# named scenarios, panic off / on
for s in ['Baseline', 'Rerating cascade', 'Panic cascade', 'Credit 2009', 'Repo run', 'Rates shock', '2008-combined']:
    for pan in (0, 1):
        p = E.scenario(s, cfg); p['panic_on'] = float(pan)
        o = E.run(inp, p); sy = E.system(inp, o); r = o['fin']['ratio'][0]
        out['scen'][f'{s}|{pan}'] = dict(std=float(sy['loss_std'][0]), fin=float(sy['loss_fin'][0]), mda=int(sy['n_gsib_mda'][0]),
                                         below=[b for b, x, g in zip(ids, r, gs) if x < 0.045 and g],
                                         dflt=[b for b, x in zip(ids, o['fin']['dflt'][0]) if x > 0],
                                         S=[round(float(h['S'][0, 0]), 2) for h in o['hist']])

# reverse stress along the joint factor, backstop on, no earnings credit; panic on (Baseline S0) vs off
zs = np.round(np.arange(0.0, -3.001, -0.0625), 4)
for pan in (0, 1):
    for cb in (1, 0):
        p = E.mc_params_from(zs, zs, zs, np.zeros(len(zs)), cb, cfg); p['ppnr_q'] = 0.0; p['panic_on'] = float(pan)
        o = E.run(inp, p); sy = E.system(inp, o); r = o['fin']['ratio']
        out['rev'][f'{pan}|{cb}'] = dict(z=zs.tolist(), mark=o['Vh_g'][:, 0].tolist(), loss=sy['loss_fin'].tolist(), mda=sy['n_gsib_mda'].tolist(),
                                       gmin=sy['n_gsib_min'].tolist(),
                                       first_min=[[b for b, x, g in zip(ids, rr, gs) if x < 0.045 and g] for rr in r])

BASE = dict(tails='t', nu=4, pi_c=0.10, mu_z=-0.3, panic=dict(S0=0.15, news0=0.05))
def summ(o, sy):
    r = o['fin']['ratio']; bm = (r < 0.045) & gs
    return dict(gmin=float(bm.any(1).mean()), exstt=float((bm & ex).any(1).mean()), sys=float(sy['systemic'].mean()),
                mda=float((sy['n_gsib_mda'] >= 1).mean()), p99=float(np.percentile(sy['loss_fin'], 99)), mean=float(sy['loss_fin'].mean()),
                bank_min={b: float((r[:, i] < 0.045).mean()) for i, b in enumerate(ids)})
LAD = [('L0', dict(tails='gauss', panic=None)), ('L1', dict(tails='t', nu=4, panic=None)), ('L2', dict(tails='t', nu=4, pi_c=0.10, panic=None)),
       ('L3', dict(tails='t', nu=4, pi_c=0.10, panic=dict(S0=0.10, news0=0.05))), ('L4', BASE)]
TRIG = {
 'T1': dict(news0=lambda p: p['news0'] + 0.15, red_rate=lambda p: np.maximum(p['red_rate'], 0.20)),
 'T2': dict(gap=lambda p: p['gap'] + 0.10),
 'T3': dict(dh=lambda p: p['dh'] + 0.15, pull_base=lambda p: np.minimum(1, p['pull_base'] + 0.5)),
 'T4': dict(news0=lambda p: p['news0'] + 0.35, pd_ins=1.0, ins_run=1.0),
 'T5': dict(news0=lambda p: p['news0'] + 1.0),
 'T6': dict(news0=lambda p: p['news0'] + 0.15, red_rate=lambda p: np.maximum(p['red_rate'], 0.20), gap=lambda p: p['gap'] + 0.10,
            dh=lambda p: p['dh'] + 0.15, pull_base=lambda p: np.minimum(1, p['pull_base'] + 0.5)),
}
for cb in (1, 0):
    for name, kw in LAD:
        p, o, sy = E.mc(inp, N, cb=cb, **kw); out['ladder'][f'{cb}|{name}'] = summ(o, sy); print(cb, name, out['ladder'][f'{cb}|{name}']['gmin'], flush=True)
    for name, ov in TRIG.items():
        p, o, sy = E.mc(inp, N, cb=cb, overrides=ov, **BASE); out['trig'][f'{cb}|{name}'] = summ(o, sy); print(cb, name, out['trig'][f'{cb}|{name}']['gmin'], flush=True)
json.dump(out, open(ROOT / 'data' / 'results' / 'post_runs.json', 'w'), indent=1)
print('done')
