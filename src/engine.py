"""Private-credit / AI-SPV / repo contagion stress engine (Python mirror of the Excel model).

Usage (from the repo root):
  python src/engine.py                                         # run every named scenario on data/inputs.json
  python src/engine.py model/Private_Credit_Contagion_Model.xlsx  # same, reading inputs and scenarios from the workbook
All amounts USD bn. Every formula here has a one-to-one counterpart in the workbook (see Method sheet).
"""
import json, sys, math
import numpy as np
from scipy.stats import norm

try:
    from params import P, SCEN, G, GD, CL, CLK, MB_ALLOC, INS_ALLOC, RATINGS, POOL_W, PD3, TR_AVG, TR_09, CCC0, LESSEE
except ImportError:  # when run from elsewhere
    sys.path.insert(0, __file__.rsplit('/', 1)[0]); from params import *

ROUNDS = 8
SALEABLE = [c[0] for c in CL if c[3] == 1]

# ---------------------------------------------------------------- inputs
def load_json(path):
    d = json.load(open(path))
    return prep(d)

def prep(d):
    ids = d['ids']; B = d['banks']
    f = lambda k: np.array([float(B[i][k] or 0.0) for i in ids])
    inp = {k: f(k) for k in ['cet1', 'rwa', 'req', 'aoci', 'gsib', 'ppnr_q', 'afs_fv', 'htm_ac', 'afs_ul', 'htm_ul', 'strat_eq',
                             'bl_d', 'bl_u', 'ff_d', 'ff_u', 'abf_d', 'abf_u', 'blr_d', 'blr_u', 'srt_bp', 'pb', 'trs', 'ins_fac',
                             'ins_repo', 'cre', 'hqla', 'unins', 'deposits', 'dur_afs', 'stwf', 'mmf_cp', 'mmf_rep_oth', 'repo_ng', 'cb_cap', 'ifs_a', 'ifs_l']}
    inp['ids'] = ids; inp['names'] = [B[i]['name'] for i in ids]
    inp['dg'] = np.array([B[i]['dg'] for i in ids])
    inp['H'] = np.array([[d['holdings'][i][k] for k in CLK] for i in ids])
    inp['X'] = np.array(d['network']['X'])
    bd = d['bdc']
    inp['bdc_names'] = [b['name'] for b in bd]
    for k in ['assets', 'sw', 'de', 'unsec', 'redq']:
        inp['bdc_' + k] = np.array([float(b[k]) for b in bd])
    inp['bdc_pnav'] = np.array([np.nan if b['pnav'] is None else float(b['pnav']) for b in bd])
    inp['bdc_nt'] = np.array([1.0 if b['type'] == 'NT' else 0.0 for b in bd])
    inp['bdc_hy'] = np.array([float(b.get('hy', 1.0 if b['name'] in ('FSK', 'TCPC') else 0.0)) for b in bd])
    inp['cfg'] = d.get('cfg')
    inp['veh'] = d['bdc_veh']; inp['veh_idx'] = np.array([inp['bdc_names'].index(v) for v in d['bdc_veh']])
    for k in ['spv_c', 'spv_o', 'rev_c', 'rev_o']:
        inp[k] = np.array([d['bdc_ead'][k][i] for i in ids])  # (nb, nveh)
    dl = d['deals']
    inp['deals'] = dl
    inp['holds'] = np.array([[x['holds'][i] for i in ids] for x in dl])  # (nd, nb)
    return inp

def default_cfg():
    return dict(G=dict(GD), CL=[list(c) for c in CL], MB=dict(MB_ALLOC), INS=dict(INS_ALLOC), POOL_W=list(POOL_W), PD3=list(PD3),
                TR_AVG={k: list(v) for k, v in TR_AVG.items()}, TR_09={k: list(v) for k, v in TR_09.items()},
                LESSEE={k: v[0] for k, v in LESSEE.items()}, SCEN=list(SCEN), P={r[0]: list(r[4:4 + len(SCEN)]) for r in P})

def scenario(name, cfg=None):
    cfg = cfg or default_cfg()
    j = cfg['SCEN'].index(name)
    return {k: v[j] for k, v in cfg['P'].items()}

# ---------------------------------------------------------------- helpers
def vas(p, z, rho):
    """Vasicek conditional PD; p, z broadcastable."""
    p = np.clip(p, 1e-9, 0.999)
    return norm.cdf((norm.ppf(p) - math.sqrt(rho) * z) / math.sqrt(1 - rho))

def pos(x): return np.maximum(0.0, x)

def tranche(adv, vh, vl, phi):
    """Loss rate on a senior advance `adv` against a pool worth vh (hold) / vl (liquidated)."""
    return phi * pos(adv - vl) / adv + (1 - phi) * pos(adv - vh) / adv

# ---------------------------------------------------------------- engine
def run(inp, p, rounds=ROUNDS, keep=False):
    """p: dict of scenario params (scalars or arrays of shape (N,)). Returns dict of results with leading dim N."""
    cfg = inp.get('cfg') or default_cfg()
    g = cfg['G']; CLc = cfg['CL']; CLK_ = [c[0] for c in CLc]
    N = max([np.size(v) for v in p.values()] + [1])
    S = {k: np.broadcast_to(np.asarray(v, float), (N,)).reshape(N, 1) for k, v in p.items()}  # (N,1)
    nb = len(inp['ids'])
    sw = lambda m: S['sw_' + m]

    # ---- credit pool (CreditEngine sheet)
    w = np.array(cfg['POOL_W']); p3 = np.array(cfg['PD3'])
    pp = np.minimum(0.999, p3[None, :] + S['hid'])                      # (N,5)
    # baseline expected loss already embedded in carrying values -> only the increment over the base case is a loss
    PDg_b = (vas(p3, 0.0, g['rho']) * w).sum(); PDs_b = PDg_b
    def pool(zz, dsx):
        PDg_r = vas(pp, zz, g['rho']); PDs_r = vas(np.minimum(0.999, pp * S['m_sw']), zz, g['rho'])
        PDg = (PDg_r * w).sum(1, keepdims=True); PDs = (PDs_r * w).sum(1, keepdims=True)
        Lg = PDg * S['lgd_gen'] - PDg_b * g['lgd_gen_b']; Ls = PDs * S['lgd_sw'] - PDs_b * g['lgd_sw_b']
        MTMg = (1 - PDg) * dsx / 1e4 * g['dur_s']; MTMs = (1 - PDs) * (dsx + S['ds_sw']) / 1e4 * g['dur_s']
        return PDg, PDs, Lg, Ls, MTMg, MTMs
    PDg, PDs, Lg, Ls, MTMg, MTMs = pool(S['z'], S['ds'])

    # ---- BDC look-through (BDC sheet)
    A, swj, de = inp['bdc_assets'], inp['bdc_sw'], inp['bdc_de']
    EA, DA = 1 / (1 + de), de / (1 + de)
    mark_l = np.where(np.isnan(inp['bdc_pnav']), np.nan, np.minimum(1.0, 1 - (1 - np.nan_to_num(inp['bdc_pnav'])) * EA))
    listed = ~np.isnan(mark_l)
    avg_mark = (np.nan_to_num(mark_l) * A * listed).sum() / (A * listed).sum()
    mark = np.where(listed, np.nan_to_num(mark_l), avg_mark)
    sec = (1 - inp['bdc_unsec']) * DA                                     # secured debt / assets
    already_hy = inp['bdc_hy']
    tr = lambda T: sum(wr * (T[r][0] + T[r][1]) for wr, r in zip(cfg['POOL_W'], RATINGS))
    ccc_new = tr(cfg['TR_AVG']) + S['w_mig'] * (tr(cfg['TR_09']) - tr(cfg['TR_AVG']))           # (N,1)
    mig_hc = pos(ccc_new - g['ccc0']) * (g['adv_perf'] - g['adv_np']) / g['adv_perf']
    sw_sys = (swj * A).sum() / A.sum(); mk_sys = (mark * A).sum() / A.sum()

    def bdc_state(Lg, Ls, MTMg, MTMs, wmk, theta, red_rate, req_mult):
        Vh = 1 - ((1 - swj) * Lg + swj * Ls) - S['gap'] - wmk * (1 - mark)[None, :]
        MTMj = (1 - swj) * MTMg + swj * MTMs
        AC = Vh / DA; navchg = (Vh - 1) / EA
        dgflag = np.maximum(already_hy, ((AC < 1.75) | (navchg < -0.20)).astype(float))   # loses IG
        def_bb = pos(1 - Vh * (1 - mig_hc) - S['bb_cush']) * sec               # fraction of assets to repay
        def_reg = pos(DA - Vh / 1.5)
        honored = np.minimum(np.minimum(1.0, inp['bdc_redq'] * req_mult), red_rate)
        red = inp['bdc_nt'] * EA * honored * (1 - 0.3)
        sales = A * (theta * np.maximum(def_bb, def_reg) + red)                # (N,nbdc) $bn of PCL sold
        cov = ((AC < 1.5) * A).sum(1, keepdims=True) / A.sum()                 # asset share below 150% coverage
        Vh_g = 1 - ((1 - sw_sys) * Lg + sw_sys * Ls) - S['gap'] - wmk * (1 - mk_sys)
        MTM_sys = (1 - sw_sys) * MTMg + sw_sys * MTMs
        return dict(Vh=Vh, MTMj=MTMj, AC=AC, navchg=navchg, dgflag=dgflag, sales=sales, cov=cov, Vh_g=Vh_g, MTM_sys=MTM_sys,
                    nonbank_pcl=S['pc_scale'][:, 0] * sales.sum(1))
    B0 = bdc_state(Lg, Ls, MTMg, MTMs, S['w_mkt'], S['theta_lev'], S['red_rate'], 1.0)
    Vh, AC, navchg, dgflag, bdc_sales, nonbank_pcl, Vh_g = B0['Vh'], B0['AC'], B0['navchg'], B0['dgflag'], B0['sales'], B0['nonbank_pcl'], B0['Vh_g']
    vi = inp['veh_idx']
    ccf_rev = np.maximum(S['ccf_bl'], dgflag[:, vi] * S['ccf_dg'])          # (N,nveh)
    EADspv = inp['spv_o'][None] + S['ccf_bl'][:, :, None] * (inp['spv_c'] - inp['spv_o'])[None]   # (N,nb,nveh)
    EADrev = inp['rev_o'][None] + ccf_rev[:, None, :] * (inp['rev_c'] - inp['rev_o'])[None]
    undrawn_bdc_drawn = (EADspv - inp['spv_o'][None]).sum(2) + (EADrev - inp['rev_o'][None]).sum(2)   # (N,nb)
    Vh_a = 1 - S['abf_loss']

    def m1m3m10(Bs, fs_pcl, fs_abs):
        """Losses that depend on pool values and market discounts on private-credit loans and ABS. fs_* shape (N,1)."""
        Vhv = Bs['Vh'][:, vi]
        Vl = Vhv * (1 - fs_pcl) - Bs['MTMj'][:, vi] - S['c_liq']
        LRspv = tranche(S['a_spv'], Vhv, Vl, S['phi'])
        sv = np.where(sec[vi] > 0, sec[vi], 1.0)[None, :]
        LRrev = np.where(sec[vi][None, :] > 0, tranche(sv, Vhv, Vl, S['phi']), 0.0)
        m1b = (EADspv * LRspv[:, None, :]).sum(2) + (EADrev * LRrev[:, None, :]).sum(2)
        Vl_g = Bs['Vh_g'] * (1 - fs_pcl) - Bs['MTM_sys'] - S['c_liq']
        LRg = tranche(S['a_spv'], Bs['Vh_g'], Vl_g, S['phi'])
        m1g = (inp['blr_d'] + S['ccf_bl'] * inp['blr_u']) * LRg
        m1f = S['fraud'] * (inp['bl_d'] + inp['ff_d'] + inp['abf_d'])
        LRa = tranche(g['a_abf'], Vh_a, Vh_a * (1 - fs_abs) - S['c_liq'], S['phi'])
        m3 = (inp['abf_d'] + S['ccf_abf'] * inp['abf_u']) * LRa
        m10 = inp['trs'] * tranche(g['trs_adv'], Bs['Vh_g'], Vl_g, S['phi'])
        return sw('M1') * (m1b + m1g + m1f), sw('M3') * m3, sw('M10') * m10, LRspv, LRrev, LRg, LRa

    # ---- M2 fund finance
    ltv = g['nav_ltv']
    LRnav = g['tail_share'] * pos(ltv - (1 - np.minimum(0.99, S['dnav'] * g['tail_mult']))) / ltv + (1 - g['tail_share']) * pos(ltv - (1 - S['dnav'])) / ltv
    LRff = (1 - g['nav_share']) * S['lp_dr'] * g['lgd_lp'] + g['nav_share'] * LRnav
    M2 = sw('M2') * (inp['ff_d'] + S['ccf_ff'] * inp['ff_u']) * LRff
    # ---- M4 insurers
    M4 = sw('M4') * (inp['ins_fac'] * S['ccf_ins'] + inp['ins_repo']) * S['pd_ins'] * g['lgd_ins']
    # ---- M5 AI / GPU
    dl = inp['deals']; nd = len(dl)
    LRd = np.zeros((N, nd)); rcf_draw = np.zeros((N, nb))
    Rt = (1 - S['gpu_r']) ** g['t_def']
    for k, x in enumerate(dl):
        if x['cat'] == 'NONE': continue
        p0 = cfg['LESSEE'].get(x['lessee']); p0 = g['pd_unrated'] if p0 is None else p0
        pdc = vas(p0, S['z_ai'], g['rho_ai'])
        if x['cat'] == 'GPU':
            Bt = x['ltv'] * (1 - x['frep'])
            lgd = pos(1 - (1 - g['c_gpu']) * Rt / Bt) * (1 - x['cash'])
            LRd[:, [k]] = pdc * lgd + x['uw'] * S['uw_drop']
        elif x['cat'] == 'RCF':
            LRd[:, [k]] = S['ccf_ai'] * pdc * x['lgd']
            rcf_draw += S['ccf_ai'] * inp['holds'][k][None, :]
        elif x['cat'] == 'DC':
            LRd[:, [k]] = pdc * x['lgd'] + x['uw'] * S['uw_drop'] + x['mtm0'] / 100
        elif x['cat'] == 'UNSEC':
            LRd[:, [k]] = pdc * x['lgd']
        elif x['cat'] == 'MARGIN':
            LRd[:, [k]] = pdc * pos(x['ltv'] - (1 - S['oai_drop']) * (1 - g['c_gpu'])) / x['ltv']
        elif x['cat'] == 'ANTH':
            LRd[:, [k]] = pdc * (x['senior'] * 0.10 + (1 - x['senior']) * 0.70) + S['uw_drop']
    M5 = sw('M5') * (LRd @ inp['holds'])                                     # (N,nb)
    # ---- M6 trading / HFS fundamental MTM
    dp = np.zeros((N, len(CLK_)))
    for k, key in [('IG_CORP', 'dp_IG'), ('HY_CORP', 'dp_HY'), ('LEV_LOANS', 'dp_LEV'), ('CLO', 'dp_CLO'), ('ABS_OTHER', 'dp_ABS'),
                   ('EQUITIES', 'dp_EQ'), ('MUNI', 'dp_MUNI'), ('OTHER_SOV', 'dp_OSOV')]:
        dp[:, CLK_.index(k)] = S[key][:, 0]
    nf = np.array([c[2] for c in CLc]); lam = np.array([c[1] for c in CLc]); cap = np.array([c[4] for c in CLc]); pmax = np.array([c[5] for c in CLc])
    M6 = sw('M6') * ((-dp)[:, None, :] * (inp['H'] * nf)[None]).sum(2) + sw('M6') * inp['strat_eq'] * (-S['dp_EQ'])
    # ---- M7 CRE
    M7 = sw('M7') * inp['cre'] * S['cre_lr']
    # ---- M8 rates
    afs_mtm = inp['aoci'] * inp['afs_fv'] * inp['dur_afs'] * S['dy']
    htm_pool = pos(-inp['htm_ul'] + inp['htm_ac'] * g['dur_htm'] * S['dy']) + (1 - inp['aoci']) * pos(-inp['afs_ul'] + inp['afs_fv'] * inp['dur_afs'] * S['dy'])
    # ---- M9 SRT, M11 prime
    M9 = sw('M9') * S['srt_lost'] * inp['srt_bp'] / 1e4 * inp['rwa']
    M11 = sw('M11') * inp['pb'] * S['pb_pd'] * pos(S['pb_shock'] * g['pb_conc'] - g['pb_margin'])

    rwa_eff = inp['rwa'] * (1 + S['rwa_infl'])
    K0 = inp['cet1'] + S['ppnr_q'] * inp['ppnr_q']
    r0 = inp['cet1'] / inp['rwa']

    def capital(losses):
        K = K0 - (1 - S['tax']) * losses
        return K, K / rwa_eff

    zero = np.zeros((N, 1))
    M1, M3, M10, LRspv0, LRrev0, LRg0, LRa0 = m1m3m10(B0, zero, zero)
    M8_0 = sw('M8') * (afs_mtm + htm_pool * S['htm_forced'])
    fixed = M2 + M4 + M5 + M6 + M7 + M9 + M11                             # unaffected by contagion prices
    L0 = M1 + M2 + M3 + M4 + M5 + M6 + M7 + M8_0 + M9 + M10 + M11
    K, ratio = capital(L0)
    std = dict(M1=M1, M2=M2, M3=M3, M4=M4, M5=M5, M6=M6, M7=M7, M8=M8_0, M9=M9, M10=M10, M11=M11, total=L0, K=K, ratio=ratio)

    # ---- liquidity constants
    draws = sw('M1') * (S['ccf_bl'] * inp['blr_u'] + undrawn_bdc_drawn) + sw('M2') * S['ccf_ff'] * inp['ff_u'] \
        + sw('M3') * S['ccf_abf'] * inp['abf_u'] + sw('M5') * rcf_draw + sw('M4') * S['ccf_ins'] * inp['ins_fac']
    Hs = inp['H'] * np.array([c[3] for c in CLc])                           # saleable holdings (nb,13)
    sale_tot = Hs.sum(1)
    wts = np.where(sale_tot[:, None] > 0, Hs / np.where(sale_tot[:, None] > 0, sale_tot[:, None], 1), 0)
    mb_vec = np.array([cfg['MB'].get(k, 0.0) for k in CLK_]); ins_vec = np.array([cfg['INS'].get(k, 0.0) for k in CLK_])
    pcl_i = CLK_.index('PRIV_CREDIT_LOANS'); abs_i = CLK_.index('ABS_OTHER'); eq_i = CLK_.index('EQUITIES')
    Xs = inp['X'] * g['s_in'] * g['u_ib']
    liq_on, fs_on, ib_on, cb_on = S['liq_on'], S['fs_on'], S['ib_on'], S['cb_on']
    gs = inp['gsib']; nG = gs.sum()
    sig = lambda x: 1 / (1 + np.exp(-x))
    L0n = sig(-g['theta_news'] / g['tau_news'])
    ins_sales = S['ins_run'] * (g['fabr'] + g['fabn_6m'])                   # (N,1), round-0 value (reporting)

    hist = []
    FS = np.zeros((N, len(CLK_)))
    Bprev = B0
    for r in range(1, rounds + 1):
        mda = (ratio < inp['req']).astype(float); mn = (ratio < 0.045).astype(float); insolv = (K < 0).astype(float)
        notch = np.minimum(6, np.minimum(3, np.floor(pos(r0 - ratio) / S['notch_step'])) + mda + 2 * mn)
        ni = notch.astype(int)
        # ---- panic / information contagion: public news at the start of the round -> panic intensity S_r
        news = (S['news0'] + g['w_cov'] * Bprev['cov'] + g['w_notch'] * (notch * gs).sum(1, keepdims=True) / (3 * nG)
                + g['w_mda'] * (mda * gs).sum(1, keepdims=True) / nG + g['w_def'] * np.maximum(insolv, mn).max(1, keepdims=True)
                + g['w_fs'] * FS[:, [pcl_i]] / 0.30)
        Sp = S['panic_on'] * (S['S0'] + (1 - S['S0']) * pos(sig((news - g['theta_news']) / g['tau_news']) - L0n) / (1 - L0n))
        # the street ranks banks by capital headroom: bottom quartile = 'weak' (run targets), top half = flight-to-quality recipients
        hr = ratio - inp['req']
        rk = (hr[:, None, :] < hr[:, :, None]).sum(2) + 1                     # 1 = lowest headroom (RANK ascending)
        weak = np.maximum((rk <= g['n_weak']).astype(float), mn)
        strong = (rk > nb / 2).astype(float) * (1 - mn)
        # ---- credit re-evaluated at panic-worsened factor; marks converge to market-implied
        _, _, Lg_r, Ls_r, MTMg_r, MTMs_r = pool(S['z'] - S['zc'] * Sp, S['ds'] + S['ds_pan'] * Sp)
        Br = bdc_state(Lg_r, Ls_r, MTMg_r, MTMs_r, S['w_mkt'] + (1 - S['w_mkt']) * Sp, S['theta_lev'] + (1 - S['theta_lev']) * Sp,
                       S['red_rate'] + S['red_pan'] * Sp, 1 + S['req_pan'] * Sp)
        trig = np.take_along_axis(np.broadcast_to(inp['dg'], (N, nb, 7)), ni[:, :, None], 2)[:, :, 0]
        o_dep = inp['unins'] * np.minimum(1, S['u_base'] + Sp * S['u_pan_all'] + weak * (Sp * S['u_pan_weak'] + S['u_mda'] * mda) + S['u_notch'] * notch + S['u_fail'] * mn)
        o_wh = inp['stwf'] * np.minimum(1, S['w_base'] + S['w_pan'] * Sp + S['w_notch'] * notch + 0.5 * mda + 1.0 * mn)
        o_cp = inp['mmf_cp'] * np.minimum(1, S['cp_base'] + S['cp_pan'] * Sp + S['cp_notch'] * notch)
        pull_b = S['pull_base'] + S['pull_pan'] * Sp
        o_hc = inp['repo_ng'] * (S['dh'] + S['dh_pan'] * Sp + np.minimum(1, 0.5 * pull_b + 0.25 * notch))   # haircut add-on + non-rollover of inventory repo
        ok = strong
        dshare = inp['deposits'] * ok / np.maximum(1e-9, (inp['deposits'] * ok).sum(1, keepdims=True))
        inflow = liq_on * S['recyc'] * (1 - S['rec_pan'] * Sp) * o_dep.sum(1, keepdims=True) * dshare      # flight-to-quality redeposits
        outflow = liq_on * (trig + o_dep + o_wh + o_cp + o_hc + draws)
        avail = g['usable'] * inp['hqla'] + cb_on * inp['cb_cap'] + inflow
        SF = pos(outflow - avail)
        illiq = (SF > sale_tot * 0.9).astype(float)
        f_htm = np.maximum(S['htm_forced'], (1 - cb_on) * np.minimum(1, outflow / inp['hqla']) * g['theta_sell'])
        dRWA = pos(rwa_eff - K / (inp['req'] + g['del_buf']))
        cap_sales = np.minimum(g['del_cap'] * sale_tot, dRWA)
        bank_sales = np.minimum(sale_tot, SF + cap_sales)                    # cumulative $bn sold
        sales_k = (bank_sales[:, :, None] * wts[None]).sum(1)                # (N,13)
        pull = np.minimum(1, pull_b + 0.5 * notch)
        mb = liq_on * (inp['mmf_rep_oth'] * pull * S['mb_psi']).sum(1, keepdims=True) * mb_vec[None, :]
        ins_r = np.minimum(1.0, S['ins_run'] + S['ins_pan'] * Sp) * (g['fabr'] + g['fabn_6m'])
        nonbank = ins_r * ins_vec[None, :]
        nonbank[:, pcl_i] += Br['nonbank_pcl']
        Stot = fs_on * (sales_k + nonbank + mb)
        FS = np.minimum(cap[None, :], S['dealer_mult'] * (1 + S['dm_pan'] * Sp) * lam[None, :] * Stot / 1e4 + pmax[None, :] * Sp ** g['gamma_pan'])
        M1r, M3r, M10r, LRspv, LRrev, LRg, LRa = m1m3m10(Br, FS[:, [pcl_i]], FS[:, [abs_i]])
        mtm_fs = (FS[:, None, :] * (inp['H'] * nf)[None]).sum(2) + inp['strat_eq'] * FS[:, [eq_i]]
        M8r = sw('M8') * (afs_mtm + htm_pool * np.where(liq_on > 0, f_htm, S['htm_forced']))
        dflt = np.maximum(insolv, np.maximum(mn, illiq * (1 - cb_on)))
        IB = ib_on * S['lgd_ib'] * (dflt @ Xs.T)                             # creditor losses (N,nb)
        Lr = fixed + M1r + M3r + M10r + M8r + mtm_fs + IB
        K, ratio = capital(Lr)
        hist.append(dict(notch=notch, outflow=outflow, SF=SF, illiq=illiq, bank_sales=bank_sales, FS=FS.copy(), mtm_fs=mtm_fs,
                         IB=IB, M1=M1r, M3=M3r, M10=M10r, M8=M8r, L=Lr, K=K, ratio=ratio, dflt=dflt, trig=trig, o_dep=o_dep,
                         o_wh=o_wh, o_cp=o_cp, o_hc=o_hc, inflow=inflow, draws=draws * liq_on, Stot=Stot, f_htm=f_htm,
                         S=Sp, news=news, Vh_g=Br['Vh_g'], cov=Br['cov'], nonbank_pcl=Br['nonbank_pcl']))
        Bprev = Br
    fin = hist[-1]
    status = np.where(fin['K'] < 0, 4, np.where(fin['ratio'] < 0.045, 3, np.where(fin['ratio'] < inp['req'], 2, np.where(fin['SF'] > 0, 1, 0))))
    out = dict(std=std, hist=hist, fin=fin, status=status, PDg=PDg, PDs=PDs, Lg=Lg, Ls=Ls, Vh=Vh, AC=AC, navchg=navchg, dgflag=dgflag,
               bdc_sales=bdc_sales, nonbank_pcl=nonbank_pcl, ccc_new=ccc_new, mig_hc=mig_hc, LRd=LRd, draws=draws, Vh_g=Vh_g,
               LRspv0=LRspv0, LRrev0=LRrev0, LRg0=LRg0, LRa0=LRa0, mark=mark, ins_sales=ins_sales, rwa_eff=rwa_eff)
    return out

# ---------------------------------------------------------------- summaries
def system(inp, o):
    fin = o['fin']; g = inp['gsib'] > 0
    rat = fin['ratio']; req = inp['req']
    n_mda = ((rat < req) & g).sum(1); n_min = ((rat < 0.045) & g).sum(1); n_dflt = (fin['dflt'] > 0).sum(1)
    short = (np.maximum(0, req * o['rwa_eff'] - fin['K'])).sum(1)
    systemic = ((n_mda >= 3) | (((fin['dflt'] > 0) & g).sum(1) >= 1)).astype(float)
    return dict(n_gsib_mda=n_mda, n_gsib_min=n_min, n_default=n_dflt, shortfall=short, systemic=systemic,
                loss_std=o['std']['total'].sum(1), loss_fin=fin['L'].sum(1), fs_sales=fin['Stot'].sum(1))

# ---------------------------------------------------------------- Monte Carlo
def mc_params(n, seed=20261008, cb=1, cfg=None):
    rng = np.random.default_rng(seed)
    e = rng.standard_normal((n, 4))
    z = e[:, 0]; zai = 0.5 * z + math.sqrt(0.75) * e[:, 1]; zl = 0.6 * z + 0.8 * e[:, 2]; dy = 0.01 * e[:, 3]
    return mc_params_from(z, zai, zl, dy, cb, cfg)

def mc_params_from(z, zai, zl, dy, cb=1, cfg=None):
    """Map factor draws to every scenario lever (used by Monte Carlo and Reverse_Stress)."""
    c = lambda x, lo=0, hi=1: np.clip(x, lo, hi)
    nz, nai, nl = c(-z, 0, 3), c(-zai, 0, 3), c(-zl, 0, 3)
    p = scenario('Baseline', cfg)
    p.update(zl=zl, z=z, z_ai=zai, hid=0.031 * c(-z, 0, 2), m_sw=1 + c(nai / 2.5), lgd_gen=0.35 + 0.15 * c(nz / 2.5), lgd_sw=0.50 + 0.20 * c(nz / 2.5),
             ds=250 * nz, ds_sw=120 * nai, gap=0.04 * c(nz / 2.5), w_mkt=c(nl / 2), phi=c(0.25 + 0.25 * (-zl), 0.1, 0.9), c_liq=0.02 + 0.03 * c(nl / 2.5),
             ccf_bl=c(0.10 + 0.3 * nl, 0.1, 0.9), fraud=0.001 + 0.003 * nz, lp_dr=0.015 * nz, dnav=c(0.12 * nz, 0, 0.6), ccf_ff=c(0.1 + 0.2 * nl, 0.1, 0.6),
             abf_loss=0.02 + 0.06 * nz, ccf_abf=c(0.1 + 0.25 * nl, 0.1, 0.75), pd_ins=0.002 + 0.03 * nz ** 1.5, ccf_ins=c(nl / 2),
             gpu_r=c(0.25 + 0.09 * nai, 0.15, 0.65), uw_drop=0.01 + 0.05 * nai, oai_drop=c(0.3 * nai, 0, 0.9), ccf_ai=c(nai / 2),
             dp_IG=-0.025 * nz, dp_HY=-0.08 * nz, dp_LEV=-0.10 * nz, dp_CLO=-0.08 * nz, dp_ABS=-0.06 * nz, dp_EQ=-0.15 * np.maximum(nz, nai),
             dp_MUNI=-0.02 * nz - 4 * np.maximum(dy, 0), dp_OSOV=-3 * np.maximum(dy, 0), cre_lr=0.005 + 0.022 * nz, dy=dy, htm_forced=0.0,
             srt_lost=c(0.2 * nz), pb_pd=0.015 * nl, pb_shock=0.15 * np.maximum(nz, nl), rwa_infl=0.03 * nz, w_mig=c(nz / 2, 0, 1.5),
             bb_cush=c(0.10 - 0.03 * nz, 0.03, 0.10), notch_step=0.03 - 0.004 * nz, theta_lev=c(0.3 + 0.2 * nl, 0.3, 0.9),
             red_rate=c(0.05 + 0.03 * nl, 0.05, 0.15), pc_scale=1 + 0.4 * nl, ins_run=c(0.15 * nz * nl), u_base=0.03 * nl, w_base=c(0.15 * nl),
             cp_base=c(0.17 * nl), dh=c(0.07 * nl, 0, 0.25), pull_base=c(0.25 * nl), mb_psi=c(0.2 * nl, 0, 0.6), cb_on=float(cb), recyc=0.5,
             dealer_mult=1 + 1.4 * nl, lgd_ib=0.05 + 0.12 * nl, ppnr_q=2 * (1 - 0.5 * c(nz / 2)))
    p['notch_step'] = np.maximum(0.015, p['notch_step'])
    return p

def mc_factors(n, seed=20261008, tails='gauss', nu=4.0, pi_c=0.0, mu_z=0.0, rho_ai=0.5, rho_l=0.6, rho_c=0.95):
    """Factor draws. tails='t': common chi-square mixing (multivariate Student-t, unit variance) -> joint extremes.
    pi_c: probability of a crisis regime in which the AI and liquidity factors load rho_c on the credit factor (correlations -> 1)."""
    rng = np.random.default_rng(seed)
    e = rng.standard_normal((n, 4))
    crisis = rng.random(n) < pi_c
    a_ai = np.where(crisis, rho_c, rho_ai); a_l = np.where(crisis, rho_c, rho_l)
    z0 = e[:, 0]; zai = a_ai * z0 + np.sqrt(1 - a_ai ** 2) * e[:, 1]; zl = a_l * z0 + np.sqrt(1 - a_l ** 2) * e[:, 2]; dy = e[:, 3]
    if tails == 't':
        m = np.sqrt((nu - 2) / rng.chisquare(nu, n))
        z0, zai, zl, dy = z0 * m, zai * m, zl * m, dy * m
    return mu_z + z0, zai, zl, 0.01 * dy, crisis

def mc(inp, n=10000, cb=1, seed=20261008, tails='gauss', nu=4.0, pi_c=0.0, mu_z=0.0, panic=None, crisis_S0=0.20, overrides=None):
    """Monte Carlo through the full engine. panic: dict(panic_on, S0, news0) or None (= panic off)."""
    z, zai, zl, dy, crisis = mc_factors(n, seed, tails, nu, pi_c, mu_z)
    p = mc_params_from(z, zai, zl, dy, cb, inp.get('cfg'))
    if panic is None:
        p['panic_on'] = 0.0
    else:
        p['panic_on'] = float(panic.get('panic_on', 1.0)); p['news0'] = panic.get('news0', 0.05)
        p['S0'] = np.minimum(1.0, panic.get('S0', 0.10) + crisis_S0 * crisis)
    for k, v in (overrides or {}).items():
        p[k] = v(p) if callable(v) else v
    o = run(inp, p)
    sy = system(inp, o); sy['crisis'] = crisis
    return p, o, sy

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'data' / 'inputs.json')
    inp = load_json(src) if src.endswith('.json') else __import__('xlsx_io').read_inputs(src)
    cfg = inp.get('cfg') or default_cfg()
    for s in cfg['SCEN']:
        o = run(inp, scenario(s, cfg)); sy = system(inp, o)
        print(f"{s:24s} std loss {sy['loss_std'][0]:7.1f}  final {sy['loss_fin'][0]:7.1f}  GSIB<MDA {sy['n_gsib_mda'][0]}  <min {sy['n_gsib_min'][0]}  dflt {sy['n_default'][0]}  short {sy['shortfall'][0]:6.1f}  FSvol {sy['fs_sales'][0]:6.0f}")
