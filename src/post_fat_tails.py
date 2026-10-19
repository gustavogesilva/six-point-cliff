# Executed inside post.py (shares its namespace: wb, w, hdr, clear, fonts, formats, inp, ids, nb, THR, dsh, os, json, np).
# Writes the Fat_Tails sheet from data/results/fat_tail_results.json (produced by src/fat_tail_runs.py on the same inputs).
from scipy.stats import norm as _norm
ft = wb['Fat_Tails']; clear(ft, 1)
_fp = ROOT / 'data' / 'results' / 'fat_tail_results.json'
_fp = _fp if _fp.exists() else None
w(ft, 'A1', 'Fat tails and panic: how likely is a bank failure?', F_T)
w(ft, 'A2', 'Failure = at least one G-SIB below the 4.5% CET1 minimum (resolution territory) after all contagion rounds. Horizon ~3 years (pool PDs are 3-year). '
            '1-year and 3-month columns are formulas assuming a constant hazard: 1-(1-p)^(1/3) and 1-(1-p)^(1/12). 20,000 draws per row (ladder, triggers), 10,000 (sensitivities); '
            'standard error ~0.2pp at 8%. Computed by src/fat_tail_runs.py on the same inputs as this workbook (MC_Summary re-runs L4 at 10,000 draws: differences are sampling noise).', F_NOTE)
if _fp is None:
    w(ft, 'A4', 'data/results/fat_tail_results.json not found: run  python src/fat_tail_runs.py  then src/post.py again.', F_B)
else:
    FTR = json.load(open(_fp))
    COLS = ['P(G-SIB < 4.5%), 3-yr, backstop ON', '1-yr', '3-month', 'Backstop OFF, 3-yr', '1-yr', '3-month',
            'P(systemic) ON', 'P(any default) ON', 'P(>=2 G-SIBs < 4.5%) ON', '99th pct loss ON ($bn)', 'Mean loss ON ($bn)']
    def block(r, title, first, rows, src, notes=None):
        w(ft, f'A{r}', title, F_B, fill=FILL_SUB)
        hdr(ft, r + 1, 1, [first] + COLS + (['How it is applied'] if notes else []))
        for k, name in enumerate(rows):
            rr = r + 2 + k; on = src[f'1|{name}']; off = src[f'0|{name}']
            w(ft, f'A{rr}', name)
            w(ft, f'B{rr}', on['gmin'], F_B, PCT2); w(ft, f'C{rr}', f'=1-(1-B{rr})^(1/3)', F_N, PCT2); w(ft, f'D{rr}', f'=1-(1-B{rr})^(1/12)', F_N, PCT2)
            w(ft, f'E{rr}', off['gmin'], F_B, PCT2); w(ft, f'F{rr}', f'=1-(1-E{rr})^(1/3)', F_N, PCT2); w(ft, f'G{rr}', f'=1-(1-E{rr})^(1/12)', F_N, PCT2)
            for c, key, fmt in [('H', 'sys', PCT2), ('I', 'dflt', PCT2), ('J', 'g2', PCT2), ('K', 'p99', NUM), ('L', 'mean', NUM)]:
                w(ft, f'{c}{rr}', on[key], F_N, fmt)
            if notes: w(ft, f'M{rr}', notes.get(name, ''), F_NOTE)
        return r + 2 + len(rows)
    LAD = [k.split('|', 1)[1] for k in FTR['ladder'] if k.startswith('1|')]
    TRG = [k.split('|', 1)[1] for k in FTR['triggers'] if k.startswith('1|')]
    TN = {'None (today)': 'L4 setting, nothing extra',
          'T1 Largest semi-liquid funds break gates (honour 20%)': 'news0 +0.15; honoured redemptions >= 20% of NAV per round',
          'T2 Private-credit marks cut 10 points': 'valuation gap +10 points on every private-credit pool',
          'T3 Non-govt repo seizes (haircuts +15, MMF pull +50%)': 'repo haircut add-on +15 pts; MMF non-govt repo pull +50 pts',
          'T4 A PE-owned insurer fails (FA repo + facilities lost)': 'news0 +0.35; insurer PD = 100%; insurer run = 100%',
          'T5 A G-SIB fails for reasons outside the model': 'news0 +1.0 (panic saturates from round 1); the failed bank itself is not forced into default',
          'T6 T1 + T2 + T3 together': 'all of T1, T2, T3'}
    r = block(4, 'Probability ladder: what each ingredient adds (each row adds to the one above)', 'Step', LAD, FTR['ladder'])
    LADEND = r - 1
    r = block(r + 2, 'Conditional on an observable trigger (L4 setting: fat tails + crisis regime + panic + conditioned on today)', 'Trigger (what you would see)', TRG, FTR['triggers'], TN)
    TRGEND = r - 1
    # sensitivities
    r += 2
    w(ft, f'A{r}', 'Sensitivity of the L4 result to the judgment parameters (backstop ON, 10,000 draws)', F_B, fill=FILL_SUB)
    hdr(ft, r + 1, 1, ['Parameter = value', 'P(G-SIB < 4.5%), 3-yr', '1-yr', 'P(systemic), 3-yr', 'Meaning'])
    SM = {'theta_news': 'news level at which panic takes off (lower = jumpier street)', 'gamma_pan': 'curvature of the panic discount (higher = only extreme panic reprices)',
          'w_mda': 'weight of G-SIB MDA breaches in the news index', 'n_weak': 'number of banks the street runs on',
          'nu': 'Student-t degrees of freedom (lower = fatter tails)', 'u_pan_weak': 'extra deposit run-off at the weakest banks at full panic',
          'S0': 'panic floor today (0 = calm, 1 = full panic)'}
    for k, (key, v) in enumerate(FTR['sens'].items()):
        rr = r + 2 + k; par = key.split('=')[0]
        w(ft, f'A{rr}', key); w(ft, f'B{rr}', v['gmin'], F_B, PCT2); w(ft, f'C{rr}', f'=1-(1-B{rr})^(1/3)', F_N, PCT2)
        w(ft, f'D{rr}', v['sys'], F_N, PCT2); w(ft, f'E{rr}', SM.get(par, ''), F_NOTE)
    r = r + 2 + len(FTR['sens'])
    _u = [FTR['sens'].get(f'u_pan_weak={v} (no backstop)', {}).get('gmin') for v in (0.0, 0.2, 0.6)]
    w(ft, f'A{r}', 'n_weak and u_pan_weak do not move the result with the backstop ON: the central bank funds the run, so failures are solvency-driven. '
                   + ('Without the backstop they matter: u_pan_weak 0 / 0.2 / 0.6 gives P(G-SIB < 4.5%) = ' + ' / '.join(f'{x:.1%}' for x in _u) + '.' if None not in _u else ''), F_NOTE)
    # excluding State Street (its result rests on treating its call-report business-credit line as junk back-leverage)
    r += 2
    w(ft, f'A{r}', 'Excluding State Street: its result rests on treating its ~$22bn call-report business-credit line as junk-pool back-leverage (conservative).', F_B, fill=FILL_SUB)
    hdr(ft, r + 1, 1, ['Setting', 'P(any G-SIB < 4.5%), ON, 3-yr', 'P(G-SIB other than STT < 4.5%), ON, 3-yr', '1-yr', 'Same, backstop OFF, 3-yr', '1-yr', 'P(>=2 non-STT G-SIBs < 4.5%), OFF'])
    for k, (lab, sec, key) in enumerate([('L0 Gaussian, no panic', 'ladder', LAD[0]), ('L4 today (fat tails + crisis regime + panic)', 'ladder', LAD[-1]),
                                         ('T6 gates + marks -10 + repo seizes', 'triggers', TRG[-1])]):
        rr = r + 2 + k; on = FTR[sec][f'1|{key}']; off = FTR[sec][f'0|{key}']
        w(ft, f'A{rr}', lab); w(ft, f'B{rr}', on['gmin'], F_N, PCT2); w(ft, f'C{rr}', on['exstt'], F_B, PCT2); w(ft, f'D{rr}', f'=1-(1-C{rr})^(1/3)', F_N, PCT2)
        w(ft, f'E{rr}', off['exstt'], F_B, PCT2); w(ft, f'F{rr}', f'=1-(1-E{rr})^(1/3)', F_N, PCT2); w(ft, f'G{rr}', off['ex2'], F_N, PCT2)
    r = r + 5
    # per institution
    r += 2
    w(ft, f'A{r}', 'Per institution: P(CET1 < 4.5%) over ~3 years', F_B, fill=FILL_SUB)
    hdr(ft, r + 1, 1, ['Id', 'Institution', 'L0 Gaussian, ON', 'L4 today, ON', 'L4 today, OFF', 'T6 stacked, ON', 'T6 stacked, OFF', 'L4 today ON, 1-yr'])
    L0k = '1|' + LAD[0]; L4k = '1|' + LAD[-1]; L4o = '0|' + LAD[-1]; T6k = '1|' + TRG[-1]; T6o = '0|' + TRG[-1]
    for i, bid in enumerate(ids):
        rr = r + 2 + i
        w(ft, f'A{rr}', bid); w(ft, f'B{rr}', inp['names'][i])
        for c, (sec, key) in zip('CDEFG', [('ladder', L0k), ('ladder', L4k), ('ladder', L4o), ('triggers', T6k), ('triggers', T6o)]):
            w(ft, f'{c}{rr}', FTR[sec][key]['bank_min'][bid], F_N, PCT2)
        w(ft, f'H{rr}', f'=1-(1-D{rr})^(1/3)', F_N, PCT2)
    r = r + 2 + nb + 1
    # what would have to be true for 99%
    _c = [t for t in THR if t[0] == 1][0]; zmin, mark = _c[3]
    _o1, _s1 = [(o_, s_) for cb_, p_, o_, s_ in rows if cb_ == 1][0]
    _m1 = _o1['Vh_g'][:, 0]; _n1 = _s1['n_gsib_mda']; _L1 = _s1['loss_fin']
    _p0 = E.mc_params_from(zs, zs, zs, np.zeros(len(zs)), 1, cfg); _p0['ppnr_q'] = 0.0; _p0['panic_on'] = 0.0
    _o0 = E.run(inp, _p0); _s0 = E.system(inp, _o0)
    _lst = ~np.isnan(inp['bdc_pnav']); _mkb = np.minimum(1, 1 - (1 - inp['bdc_pnav'][_lst]) / (1 + inp['bdc_de'][_lst]))
    _mk = float((_mkb * inp['bdc_assets'][_lst]).sum() / inp['bdc_assets'][_lst].sum())
    _j = int(np.argmax(_n1 >= 3)); _j3 = int(np.argmax(_s0['n_gsib_mda'] >= 3)); _jm = int(np.argmax(_s0['n_gsib_min'] >= 1))
    _cliff = (f'Panic cliff (Reverse_Stress, backstop ON, panic at Baseline settings): G-SIBs below MDA go from {_n1[_j - 1]} at a pool mark of {_m1[_j - 1]:.0%} '
              f'(losses ${_L1[_j - 1]:,.0f}bn) to {_n1[_j]} at {_m1[_j]:.0%} (losses ${_L1[_j]:,.0f}bn). With the panic channel switched off, three G-SIBs are below MDA at a mark of '
              f'{_o0["Vh_g"][_j3, 0]:.0%} and the first G-SIB goes below 4.5% at {_o0["Vh_g"][_jm, 0]:.0%}. Listed BDC prices imply a mark of {_mk:.0%} today (BDC!C42).')
    _gsx = (inp['gsib'] > 0) & np.array([b_ != 'STT' for b_ in ids])
    _ex = []
    for cb_, p_, o_, s_ in rows:
        hit = np.where(((o_['fin']['ratio'] < 0.045) & _gsx).any(1))[0]
        if len(hit):
            k_ = hit[0]; nm = [inp['names'][i] for i in range(nb) if _gsx[i] and o_['fin']['ratio'][k_, i] < 0.045]
            _ex.append(f"z = {zs[k_]:.2f} (pool mark {o_['Vh_g'][k_, 0]:.0%}; {', '.join(nm)}) with the backstop {'ON' if cb_ else 'OFF'}")
    _exstt = 'Excluding State Street, the first G-SIB falls below 4.5% at ' + '; at '.join(_ex) + '.' if _ex else 'Excluding State Street, no G-SIB falls below 4.5% on the grid.'
    w(ft, f'A{r}', 'What would have to be true for a 99% probability?', F_B, fill=FILL_SUB)
    lines = [
        f'Highest conditional probability in the model: T6 with no backstop, {FTR["triggers"][T6o]["gmin"]:.0%} over ~3 years. Even stacking every trigger leaves failure the minority outcome.',
        (f'Deterministic path (Reverse_Stress, backstop ON): the first G-SIB falls below 4.5% when the joint credit / AI / liquidity factor reaches z = {zmin:.2f}, '
         f'generic private-credit pool marked at {mark:.0%} of carrying value. Probability of a factor at least that bad under a normal: {_norm.cdf(zmin):.2%}; '
         f'under the fat-tailed, today-conditioned factor (Student-t nu = 4, mean -0.3): {__import__("scipy").stats.t.cdf((zmin + 0.3) / np.sqrt(0.5), 4):.2%}.') if zmin is not None else 'Reverse stress: no G-SIB falls below 4.5% on the grid.',
        _cliff,
        _exstt,
        'A 99% call is therefore equivalent to saying that loss is already locked in: either private-credit pools are already worth roughly the mark above, '
        'or a G-SIB is already concealing a capital hole outside the model (T5). A central bank that will not lend only moves the odds to the backstop-OFF column. '
        'Neither is visible in current filings or market prices.',
        'Market check, 19 Oct 2026 (Yahoo Finance; fall from the 3-month high): Blue Owl -29%, Blackstone -28%, KKR -25%, Ares -24%, Apollo -22%, FS KKR -20%, OBDC -17%, '
        'BDC index (BIZD) -13%, CoreWeave -42%; State Street -15%, KRE -11%, JPMorgan -8%; leveraged loans (BKLN) -2%, high yield (HYG) -4%, S&P 500 -1%. '
        'VIX 17.8 (20.0 close on 16 Oct). High-yield spread 315bp on 8 Oct, 331bp on 16 Oct (FRED).',
        'Reading: the stress sits in the equity of private-credit managers, BDCs and banks (word on the street, panic floor S0 ~ 0.15), not yet in broad credit or volatility (no correlation-to-1 phase). '
        'The signals that would move the model toward the T-rows: semi-liquid fund gates, a BDC breaching 150% coverage, a 10-point private-credit mark-down, tri-party haircut increases, a PE-owned insurer downgrade.',
    ]
    for k, t in enumerate(lines): w(ft, f'A{r + 1 + k}', t, F_N)
    ft.column_dimensions['A'].width = 52
    for k in range(2, 13): ft.column_dimensions[CLT(k)].width = 13
    ft.column_dimensions['M'].width = 70
    ch = BarChart(); ch.type = 'bar'; ch.title = 'P(>=1 G-SIB below 4.5%), ~3 years'; ch.x_axis.title = None; ch.y_axis.numFmt = '0%'
    ch.add_data(Reference(ft, min_col=2, min_row=5, max_row=LADEND), titles_from_data=True)
    ch.add_data(Reference(ft, min_col=5, min_row=5, max_row=LADEND), titles_from_data=True)
    ch.set_categories(Reference(ft, min_col=1, min_row=6, max_row=LADEND)); ch.height = 7; ch.width = 16
    ft.add_chart(ch, 'O4')
    ch2 = BarChart(); ch2.type = 'bar'; ch2.title = 'Given a trigger: P(>=1 G-SIB below 4.5%), ~3 years'; ch2.y_axis.numFmt = '0%'
    ch2.add_data(Reference(ft, min_col=2, min_row=LADEND + 4, max_row=TRGEND), titles_from_data=True)
    ch2.add_data(Reference(ft, min_col=5, min_row=LADEND + 4, max_row=TRGEND), titles_from_data=True)
    ch2.set_categories(Reference(ft, min_col=1, min_row=LADEND + 5, max_row=TRGEND)); ch2.height = 8; ch2.width = 16
    ft.add_chart(ch2, 'O20')

# Dashboard: horizon conversion of the headline MC probability (MC_Summary row 8 = P(>=1 G-SIB below 4.5%))
w(dsh, 'H19', 'P(>=1 G-SIB below 4.5%) by horizon (constant hazard)', F_B, fill=FILL_SUB)
for k, (lab, ex) in enumerate([('1 year', '1/3'), ('3 months', '1/12')]):
    w(dsh, f'H{20 + k}', lab)
    w(dsh, f'L{20 + k}', f'=1-(1-MC_Summary!B8)^({ex})', Font(name=AR, size=10, bold=True), PCT2)
    w(dsh, f'M{20 + k}', f'=1-(1-MC_Summary!C8)^({ex})', Font(name=AR, size=10, bold=True), PCT2)
