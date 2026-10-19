"""Build the Excel stress model (live formulas) from data/inputs.json + params.py.

Usage (from the repo root):  python src/build_xlsx.py [output.xlsx]
Then run src/post.py to recalculate and fill the Monte Carlo / reverse-stress / Fat_Tails value sheets.
"""
import json, sys
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as CLT
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment
from openpyxl.chart import BarChart, Reference, Series
from params import P, SCEN, G, CL, MB_ALLOC, INS_ALLOC, RATINGS, POOL_W, PD3, TR_AVG, TR_09, LESSEE

ROOT = Path(__file__).resolve().parents[1]
OUT = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'model' / 'Private_Credit_Contagion_Model.xlsx')
D = json.load(open(ROOT / 'data' / 'inputs.json'))
IDS = D['ids']; NB = len(IDS); B = D['banks']; SRC = D['src']
CLK = [c[0] for c in CL]; NK = len(CLK)
VEH = D['bdc_veh']; NV = len(VEH); BDC = D['bdc']; NBD = len(BDC); DEALS = D['deals']; ND = len(DEALS)
ROUNDS = 8

# ---------------------------------------------------------------- styles
AR = 'Arial'
F_IN = Font(name=AR, size=10, color='0000FF'); F_CALC = Font(name=AR, size=10, color='000000')
F_LINK = Font(name=AR, size=10, color='008000'); F_HDR = Font(name=AR, size=10, bold=True, color='FFFFFF')
F_B = Font(name=AR, size=10, bold=True); F_T = Font(name=AR, size=14, bold=True); F_N = Font(name=AR, size=10)
F_NOTE = Font(name=AR, size=9, italic=True, color='595959')
FILL_H = PatternFill('solid', fgColor='1F3864'); FILL_EST = PatternFill('solid', fgColor='FCE4D6')
FILL_Y = PatternFill('solid', fgColor='FFFF00'); FILL_SUB = PatternFill('solid', fgColor='D9E1F2'); FILL_G = PatternFill('solid', fgColor='EDEDED')
NUM = '#,##0.0;(#,##0.0);"-"'; NUM2 = '#,##0.00;(#,##0.00);"-"'; NUM3 = '0.000;(0.000);"-"'; PCT = '0.0%;(0.0%);"-"'; PCT2 = '0.00%;(0.00%);"-"'; INT = '0;(0);"-"'
thin = Side(style='thin', color='BFBFBF')

wb = Workbook()
def sheet(name):
    ws = wb.create_sheet(name); ws.sheet_properties.tabColor = None; return ws
def put(ws, ref, v, font=F_CALC, fmt=None, fill=None, bold=False, wrap=False):
    c = ws[ref]; c.value = v; c.font = Font(name=AR, size=10, bold=bold, color=font.color) if bold else font
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    if wrap: c.alignment = Alignment(wrap_text=True, vertical='top')
    return c
def hdr(ws, row, col, labels, widths=None):
    for k, l in enumerate(labels):
        c = ws.cell(row=row, column=col + k, value=l); c.font = F_HDR; c.fill = FILL_H
        c.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
    ws.row_dimensions[row].height = 42
def title(ws, t, sub=None):
    put(ws, 'A1', t, F_T)
    if sub: put(ws, 'A2', sub, F_NOTE)
def name(n, ref):
    wb.defined_names[n] = DefinedName(n, attr_text=ref)
def widths(ws, d):
    for k, v in d.items(): ws.column_dimensions[k].width = v

# ================================================================ Dashboard (created early so selector exists)
wb.remove(wb.active)
ws_readme = sheet('README'); ws_dash = sheet('Dashboard'); ws_sc = sheet('Scenarios'); ws_gl = sheet('Globals')
ws_ib = sheet('Inputs_Banks'); ws_h = sheet('Holdings'); ws_bdc = sheet('BDC'); ws_ead = sheet('BDC_EAD'); ws_ai = sheet('AI_Deals')
ws_ce = sheet('CreditEngine'); ws_m = sheet('Modules'); ws_c = sheet('Contagion'); ws_n = sheet('Network'); ws_r = sheet('Results')
ws_sg = sheet('Standalone_Grid'); ws_rs = sheet('Reverse_Stress'); ws_mcs = sheet('MC_Summary'); ws_mcd = sheet('MC_Distribution'); ws_ft = sheet('Fat_Tails')
ws_py = sheet('PyCheck'); ws_ck = sheet('Checks'); ws_src = sheet('Sources'); ws_me = sheet('Method')

put(ws_dash, 'B4', 'Active scenario', F_B); put(ws_dash, 'C4', '2008-combined', F_IN, fill=FILL_Y)
name('sel_scen', 'Dashboard!$C$4')
NSC = len(SCEN); SC_L = CLT(4 + NSC); SC_A = CLT(5 + NSC); SC_B = CLT(6 + NSC)
dv = DataValidation(type='list', formula1=f'=Scenarios!$E$4:${SC_L}$4', allow_blank=False); ws_dash.add_data_validation(dv); dv.add('C4')

# ================================================================ Globals
title(ws_gl, 'Global constants (not scenario-dependent)', 'Blue = input. Each constant is a named range g_<key> used in formulas.')
hdr(ws_gl, 4, 1, ['Key', 'Value', 'Description / basis'])
for k, (key, val, desc) in enumerate(G):
    r = 5 + k
    put(ws_gl, f'A{r}', key, F_N); put(ws_gl, f'B{r}', val, F_IN, NUM3); put(ws_gl, f'C{r}', desc, F_N)
    name('g_' + key, f'Globals!$B${r}')
widths(ws_gl, {'A': 14, 'B': 10, 'C': 110})

# ================================================================ Scenarios
title(ws_sc, 'Scenario parameters', f'Columns E-{SC_L} = scenario values (blue inputs; Custom in yellow is free to edit). Column {SC_A} = active value used by every formula (named p_<key>). Select the scenario on Dashboard!C4.')
hdr(ws_sc, 4, 1, ['Key', 'Group', 'Description', 'Unit'] + SCEN + ['ACTIVE', 'Basis / source'])
SROW = {}
for k, row in enumerate(P):
    r = 5 + k; key = row[0]; SROW[key] = r
    put(ws_sc, f'A{r}', key, F_N); put(ws_sc, f'B{r}', row[1], F_N); put(ws_sc, f'C{r}', row[2], F_N); put(ws_sc, f'D{r}', row[3], F_N)
    fmt = NUM3 if row[3] in ('frac', 'dec', 'x', 'z', 'pp') else (INT if row[3] in ('bp', 'q', '0/1') else NUM3)
    for j in range(len(SCEN)):
        put(ws_sc, f'{CLT(5 + j)}{r}', row[4 + j], F_IN, fmt, FILL_Y if SCEN[j] == 'Custom' else None)
    put(ws_sc, f'{SC_A}{r}', f'=INDEX($E{r}:${SC_L}{r},1,MATCH(sel_scen,$E$4:${SC_L}$4,0))', F_CALC, fmt, FILL_SUB)
    put(ws_sc, f'{SC_B}{r}', row[4 + len(SCEN)], F_NOTE)
    name('p_' + key, f'Scenarios!${SC_A}${r}')
ws_sc.freeze_panes = 'E5'
widths(ws_sc, {'A': 12, 'B': 12, 'C': 62, 'D': 6, **{CLT(5 + j): 11 for j in range(NSC + 1)}, SC_B: 90})

# ================================================================ Inputs_Banks
from layout import FIELDS
COL = {f[0]: CLT(1 + k) for k, f in enumerate(FIELDS)}
R0 = 6  # first bank row everywhere
title(ws_ib, 'Per-bank inputs (USD bn; CET1 and RWA of US banks at 30-Sep-2026, other items 30-Jun-2026 unless noted)', 'Blue = sourced input; orange fill = estimate / proxy (see Sources sheet for every cell); black = formula. FX: EUR 1.1417, GBP 1.3259, JPY 1/162.61, CAD 1/1.4205.')
hdr(ws_ib, 5, 1, [f[1] for f in FIELDS])
def bc(key, i, absrow=False): return f"Inputs_Banks!${COL[key]}${R0 + i}"
EADCOL = {i: CLT(3 + k) for k, i in enumerate(IDS)}   # bank columns in BDC_EAD / AI_Deals / Network
for i, bid in enumerate(IDS):
    r = R0 + i; b = B[bid]
    for key, h, fmt, kind in FIELDS:
        ref = f'{COL[key]}{r}'
        if kind == 'in':
            if key.startswith('dg') and key[2:].isdigit(): v = b['dg'][int(key[2:])]; s = SRC[bid].get('dg', '')
            else: v = b.get(key); s = SRC[bid].get(key, '')
            c = put(ws_ib, ref, v, F_IN, fmt)
            if isinstance(s, str) and s.startswith('EST'): c.fill = FILL_EST
        else:
            ec = EADCOL[bid]
            f = {'bdc_o': f'=SUM(BDC_EAD!{ec}$31:{ec}$52)+SUM(BDC_EAD!{ec}$81:{ec}$102)',
                 'bdc_c': f'=SUM(BDC_EAD!{ec}$6:{ec}$27)+SUM(BDC_EAD!{ec}$56:{ec}$77)',
                 'blr_d': f'=MAX(0,{COL["bl_d"]}{r}-{COL["bdc_o"]}{r})',
                 'blr_u': f'=MAX(0,{COL["bl_u"]}{r}-({COL["bdc_c"]}{r}-{COL["bdc_o"]}{r}))',
                 'repo_ng': f'={COL["repo_liab"]}{r}*{COL["ng_share"]}{r}',
                 'r0': f'={COL["cet1"]}{r}/{COL["rwa"]}{r}',
                 'sale_tot': f'=Holdings!$P{r}'}[key]
            put(ws_ib, ref, f, F_LINK if key in ('bdc_o', 'bdc_c', 'sale_tot') else F_CALC, fmt)
ws_ib.freeze_panes = 'C6'
widths(ws_ib, {CLT(k + 1): (8 if k == 0 else 18 if k == 1 else 11) for k in range(len(FIELDS))})

# ================================================================ Holdings
title(ws_h, 'Holdings by asset class (USD bn) and fire-sale parameters', 'Rows 31-39: price-impact lambda (bp of price per $bn sold, before dealer multiplier), capital-relevant net fraction, saleable flag, discount cap, fundamental price decline (scenario), non-bank seller allocation, panic discount at full panic (S = 1; correlation-to-1 repricing of every risky class).')
hdr(ws_h, 5, 1, ['Id', 'Institution'] + CLK + ['Saleable total'] + ['w ' + k for k in CLK])
for i, bid in enumerate(IDS):
    r = R0 + i
    put(ws_h, f'A{r}', bid, F_N); put(ws_h, f'B{r}', B[bid]['name'], F_N)
    for k, key in enumerate(CLK):
        v = D['holdings'][bid][key]; s = D['hsrc'][bid].get(key, '')
        c = put(ws_h, f'{CLT(3 + k)}{r}', v, F_IN, NUM)
        if 'estimate' in s or s == '': c.fill = FILL_EST
    put(ws_h, f'P{r}', f'=SUMPRODUCT(C{r}:O{r},$C$33:$O$33)', F_CALC, NUM)
    for k in range(NK):
        cl = CLT(3 + k)
        put(ws_h, f'{CLT(17 + k)}{r}', f'=IF($P{r}>0,{cl}{r}*{cl}$33/$P{r},0)', F_CALC, NUM3)
labels = [(31, 'Lambda (bp per $bn)', 1, NUM2), (32, 'Net fraction hitting capital', 2, PCT), (33, 'Saleable (1/0)', 3, INT), (34, 'Cap on fire-sale discount', 4, PCT)]
for (r, lab, idx, fmt) in labels:
    put(ws_h, f'B{r}', lab, F_B)
    for k, c in enumerate(CL): put(ws_h, f'{CLT(3 + k)}{r}', c[idx], F_IN, fmt)
put(ws_h, 'B35', 'Fundamental price decline (scenario)', F_B)
DPMAP = {'IG_CORP': 'dp_IG', 'HY_CORP': 'dp_HY', 'LEV_LOANS': 'dp_LEV', 'CLO': 'dp_CLO', 'ABS_OTHER': 'dp_ABS', 'EQUITIES': 'dp_EQ', 'MUNI': 'dp_MUNI', 'OTHER_SOV': 'dp_OSOV'}
for k, key in enumerate(CLK):
    put(ws_h, f'{CLT(3 + k)}35', f'=-p_{DPMAP[key]}' if key in DPMAP else 0, F_CALC if key in DPMAP else F_IN, PCT)
put(ws_h, 'B36', 'Matched-book client sale allocation', F_B); put(ws_h, 'B37', 'Insurer sale allocation', F_B)
put(ws_h, 'B38', 'Non-bank sales ($bn, round-invariant)', F_B)
for k, key in enumerate(CLK):
    cl = CLT(3 + k)
    put(ws_h, f'{cl}36', MB_ALLOC.get(key, 0.0), F_IN, PCT); put(ws_h, f'{cl}37', INS_ALLOC.get(key, 0.0), F_IN, PCT)
    put(ws_h, f'{cl}38', f'=CE_ins_sales*{cl}37' + ('+CE_nonbank_pcl' if key == 'PRIV_CREDIT_LOANS' else ''), F_CALC, NUM)
put(ws_h, 'B39', 'Panic discount at full panic (S = 1)', F_B)
for k, c in enumerate(CL): put(ws_h, f'{CLT(3 + k)}39', c[5], F_IN, PCT)
for k, c in enumerate(CL): put(ws_h, f'{CLT(3 + k)}40', c[6], F_NOTE)
put(ws_h, 'B40', 'Basis', F_B)
put(ws_h, 'B29' if False else 'A41', 'Matched-book allocation = NY Fed tri-party collateral mix 10-Sep-2026 (equities 48%, IG 25%, ABS 13%, HY 11%, munis 3%); insurer allocation = judgment.', F_NOTE)
ws_h.freeze_panes = 'C6'; widths(ws_h, {'A': 7, 'B': 30, **{CLT(3 + k): 10 for k in range(NK * 2 + 1)}})

# ================================================================ CreditEngine
ce = ws_ce
title(ce, 'Credit engine: look-through pool (bank -> IG intermediary -> junk loans), rating migration, fund finance',
      'Vasicek one-factor 3-yr conditional PD: PD(z) = N[(N^-1(PD3 + hidden) - sqrt(rho) z) / sqrt(1-rho)]. Only the increase over the base case (z=0, base LGD) is a loss: carrying values already embed base expected loss.')
hdr(ce, 5, 1, ['Rating', 'Pool weight', 'PD 3-yr (S&P avg)', 'PD + hidden', 'PD(z) generic', 'PD(z) software', 'PD base (z=0)', 'T avg ->CCC', 'T avg ->D', 'T 2009 ->CCC', 'T 2009 ->D'])
for k, rt in enumerate(RATINGS):
    r = 6 + k
    put(ce, f'A{r}', rt, F_N); put(ce, f'B{r}', POOL_W[k], F_IN, PCT); put(ce, f'C{r}', PD3[k], F_IN, PCT2)
    put(ce, f'D{r}', f'=MIN(0.999,C{r}+p_hid)', F_CALC, PCT2)
    put(ce, f'E{r}', f'=NORMSDIST((NORMSINV(D{r})-SQRT(g_rho)*p_z)/SQRT(1-g_rho))', F_CALC, PCT2)
    put(ce, f'F{r}', f'=NORMSDIST((NORMSINV(MIN(0.999,D{r}*p_m_sw))-SQRT(g_rho)*p_z)/SQRT(1-g_rho))', F_CALC, PCT2)
    put(ce, f'G{r}', f'=NORMSDIST(NORMSINV(C{r})/SQRT(1-g_rho))', F_CALC, PCT2)
    for j, v in enumerate(TR_AVG[rt] + TR_09[rt]): put(ce, f'{CLT(8 + j)}{r}', v, F_IN, PCT)
put(ce, 'A12', 'Sources: pool weights = Fitch private-credit rating distribution Q3-25 via FSB May-26; PD 3-yr = S&P 2024 study Table 26; transitions = S&P 1981-2024 (NR-adj) and Moody\'s 2009.', F_NOTE)
CEN = [  # name, label, formula, fmt
 ('CE_PDg', 'Pool PD 3-yr, generic', '=SUMPRODUCT(B6:B10,E6:E10)', PCT),
 ('CE_PDs', 'Pool PD 3-yr, software', '=SUMPRODUCT(B6:B10,F6:F10)', PCT),
 ('CE_PDb', 'Pool PD 3-yr, base case (embedded in marks)', '=SUMPRODUCT(B6:B10,G6:G10)', PCT),
 ('CE_Lg', 'Incremental credit loss, generic', '=CE_PDg*p_lgd_gen-CE_PDb*g_lgd_gen_b', PCT),
 ('CE_Ls', 'Incremental credit loss, software', '=CE_PDs*p_lgd_sw-CE_PDb*g_lgd_sw_b', PCT),
 ('CE_MTMg', 'Spread MTM on performing, generic', '=(1-CE_PDg)*p_ds/10000*g_dur_s', PCT),
 ('CE_MTMs', 'Spread MTM on performing, software', '=(1-CE_PDs)*(p_ds+p_ds_sw)/10000*g_dur_s', PCT),
 ('CE_sw_sys', 'System software share (asset-weighted BDC)', '=SUMPRODUCT(BDC!C6:C39,BDC!D6:D39)/SUM(BDC!C6:C39)', PCT),
 ('CE_mk_sys', 'System market-implied mark (asset-weighted BDC)', '=SUMPRODUCT(BDC!C6:C39,BDC!M6:M39)/SUM(BDC!C6:C39)', PCT),
 ('CE_Vh_g', 'Generic pool value, hold / workout', '=1-((1-CE_sw_sys)*CE_Lg+CE_sw_sys*CE_Ls)-p_gap-p_w_mkt*(1-CE_mk_sys)', PCT),
 ('CE_MTM_sys', 'Generic pool spread MTM', '=(1-CE_sw_sys)*CE_MTMg+CE_sw_sys*CE_MTMs', PCT),
 ('CE_Vh_a', 'ABF / SE pool value, hold', '=1-p_abf_loss', PCT),
 ('CE_Vl_g0', 'Generic pool value, liquidated (no fire-sale)', '=CE_Vh_g-CE_MTM_sys-p_c_liq', PCT),
 ('CE_LRg0', 'Loss rate on generic SPV back-leverage (standalone)', '=p_phi*MAX(0,p_a_spv-CE_Vl_g0)/p_a_spv+(1-p_phi)*MAX(0,p_a_spv-CE_Vh_g)/p_a_spv', PCT),
 ('CE_LRa0', 'Loss rate on ABF / SE warehouses (standalone)', '=p_phi*MAX(0,g_a_abf-(CE_Vh_a-p_c_liq))/g_a_abf+(1-p_phi)*MAX(0,g_a_abf-CE_Vh_a)/g_a_abf', PCT),
 ('CE_LRtrs0', 'Loss rate on written sub-IG TRS (standalone)', '=p_phi*MAX(0,g_trs_adv-CE_Vl_g0)/g_trs_adv+(1-p_phi)*MAX(0,g_trs_adv-CE_Vh_g)/g_trs_adv', PCT),
 ('CE_ccc_avg', 'Pool share to CCC/D in 1 yr, average matrix', '=SUMPRODUCT(B6:B10,H6:H10)+SUMPRODUCT(B6:B10,I6:I10)', PCT),
 ('CE_ccc_09', 'Pool share to CCC/D in 1 yr, 2009 matrix', '=SUMPRODUCT(B6:B10,J6:J10)+SUMPRODUCT(B6:B10,K6:K10)', PCT),
 ('CE_ccc_new', 'Pool share to CCC/D, scenario', '=CE_ccc_avg+p_w_mig*(CE_ccc_09-CE_ccc_avg)', PCT),
 ('CE_mig_hc', 'Borrowing-base haircut from migration', '=MAX(0,CE_ccc_new-g_ccc0)*(g_adv_perf-g_adv_np)/g_adv_perf', PCT),
 ('CE_LRnav', 'Loss rate, NAV loans', '=g_tail_share*MAX(0,g_nav_ltv-(1-MIN(0.99,p_dnav*g_tail_mult)))/g_nav_ltv+(1-g_tail_share)*MAX(0,g_nav_ltv-(1-p_dnav))/g_nav_ltv', PCT2),
 ('CE_LRff', 'Loss rate, fund finance (sub lines + NAV)', '=(1-g_nav_share)*p_lp_dr*g_lgd_lp+g_nav_share*CE_LRnav', PCT2),
 ('CE_nonbank_pcl', 'Private-credit loans sold by non-banks ($bn)', '=p_pc_scale*SUM(BDC!Y6:Y39)', NUM),
 ('CE_ins_sales', 'Insurer forced sales ($bn)', '=p_ins_run*(g_fabr+g_fabn_6m)', NUM),
]
hdr(ce, 14, 1, ['Name', 'Item', 'Value'])
for k, (nm, lab, f, fmt) in enumerate(CEN):
    r = 15 + k
    put(ce, f'A{r}', nm, F_N); put(ce, f'B{r}', lab, F_N); put(ce, f'C{r}', f, F_CALC, fmt); name(nm, f'CreditEngine!$C${r}')
r = 15 + len(CEN) + 1
put(ce, f'A{r}', 'AI lessee 3-yr PDs (S&P Table 26, 3-yr column)', F_B)
hdr(ce, r + 1, 1, ['Key', 'PD 3-yr', 'Basis'])
LROW0 = r + 2
for k, (key, (pv, desc)) in enumerate(LESSEE.items()):
    rr = LROW0 + k
    put(ce, f'A{rr}', key, F_N); put(ce, f'B{rr}', '=g_pd_unrated' if pv is None else pv, F_IN if pv is not None else F_LINK, PCT2); put(ce, f'C{rr}', desc, F_N)
LROW1 = LROW0 + len(LESSEE) - 1
name('rng_lessee_key', f'CreditEngine!$A${LROW0}:$A${LROW1}'); name('rng_lessee_pd', f'CreditEngine!$B${LROW0}:$B${LROW1}')
widths(ce, {'A': 16, 'B': 48, 'C': 14, 'D': 12, 'E': 13, 'F': 13, 'G': 13, 'H': 11, 'I': 11, 'J': 11, 'K': 11})

# ================================================================ BDC
title(ws_bdc, 'BDC look-through: IG-rated intermediaries holding junk loans (34 vehicles, $381bn)',
      'Inputs from Q2-26 10-Qs; P/NAV 6-Oct-26. Pool value per BDC blends generic/software losses, valuation gap and market-implied mark. Revolver lenders are senior to unsecured notes: loss only if pool < secured debt/assets.')
BH = ['BDC', 'Type', 'Investments FV ($bn)', 'Software share', 'Gross D/E', 'P/NAV 6-Oct-26', 'Unsecured share of debt', 'Q3 redemption requests',
      'Non-traded (1/0)', 'Equity / assets', 'Debt / assets', 'Market-implied mark (listed)', 'Mark used', 'Overmark applied', 'Pool value, hold',
      'Spread MTM', 'Secured debt / assets', 'Asset coverage after loss', 'NAV change', 'Already HY (1/0)', 'Loses IG (1/0)',
      'Borrowing-base deficiency (% assets)', '150% coverage deficiency (% assets)', 'Redemption sales (% assets)', 'Forced sales ($bn)',
      'Pool value, liquidated (no FS)', 'Loss rate SPV (standalone)', 'Loss rate revolver (standalone)', 'helper mark x assets', 'helper listed assets']
hdr(ws_bdc, 5, 1, BH)
for j, b in enumerate(BDC):
    r = 6 + j
    put(ws_bdc, f'A{r}', b['name'], F_N); put(ws_bdc, f'B{r}', b['type'], F_IN); put(ws_bdc, f'C{r}', b['assets'], F_IN, NUM2)
    put(ws_bdc, f'D{r}', b['sw'], F_IN, PCT); put(ws_bdc, f'E{r}', b['de'], F_IN, NUM2)
    put(ws_bdc, f'F{r}', b['pnav'], F_IN, NUM2); put(ws_bdc, f'G{r}', b['unsec'], F_IN, PCT)
    if b['name'] in ('PSEC', 'NHPIF', 'ASCF', 'HTGC', 'OCSL', 'BBDC', 'KBDC', 'HPS CCS', 'APCF', 'TCPC', 'NHPIF-A'): ws_bdc[f'G{r}'].fill = FILL_EST
    put(ws_bdc, f'H{r}', b['redq'], F_IN, PCT)
    f = {'I': f'=IF(B{r}="NT",1,0)', 'J': f'=1/(1+E{r})', 'K': f'=E{r}/(1+E{r})',
         'L': f'=IF(F{r}="","",MIN(1,1-(1-F{r})*J{r}))', 'M': f'=IF(L{r}="",$C$42,L{r})', 'N': f'=p_w_mkt*(1-M{r})',
         'O': f'=1-((1-D{r})*CE_Lg+D{r}*CE_Ls)-p_gap-N{r}', 'P': f'=(1-D{r})*CE_MTMg+D{r}*CE_MTMs', 'Q': f'=(1-G{r})*K{r}',
         'R': f'=O{r}/K{r}', 'S': f'=(O{r}-1)/J{r}', 'U': f'=MAX(T{r},IF(OR(R{r}<1.75,S{r}<-0.2),1,0))',
         'V': f'=MAX(0,1-O{r}*(1-CE_mig_hc)-p_bb_cush)*Q{r}', 'W': f'=MAX(0,K{r}-O{r}/1.5)', 'X': f'=I{r}*J{r}*MIN(H{r},p_red_rate)*(1-0.3)',
         'Y': f'=C{r}*(p_theta_lev*MAX(V{r},W{r})+X{r})', 'Z': f'=O{r}-P{r}-p_c_liq',
         'AA': f'=p_phi*MAX(0,p_a_spv-Z{r})/p_a_spv+(1-p_phi)*MAX(0,p_a_spv-O{r})/p_a_spv',
         'AB': f'=IF(Q{r}>0,p_phi*MAX(0,Q{r}-Z{r})/Q{r}+(1-p_phi)*MAX(0,Q{r}-O{r})/Q{r},0)',
         'AC': f'=IF(L{r}="",0,L{r}*C{r})', 'AD': f'=IF(L{r}="",0,C{r})'}
    fm = {'I': INT, 'J': PCT, 'K': PCT, 'L': PCT, 'M': PCT, 'N': PCT, 'O': PCT, 'P': PCT, 'Q': PCT, 'R': NUM2, 'S': PCT, 'U': INT, 'V': PCT, 'W': PCT,
          'X': PCT, 'Y': NUM2, 'Z': PCT, 'AA': PCT, 'AB': PCT, 'AC': NUM2, 'AD': NUM2}
    for col, ff in f.items(): put(ws_bdc, f'{col}{r}', ff, F_CALC, fm[col])
    put(ws_bdc, f'T{r}', b.get('hy', 1 if b['name'] in ('FSK', 'TCPC') else 0), F_IN, INT)
put(ws_bdc, 'B42', 'Listed asset-weighted mark (applied to non-traded)', F_B); put(ws_bdc, 'C42', '=SUM(AC6:AC39)/SUM(AD6:AD39)', F_CALC, PCT)
put(ws_bdc, 'B43', 'Total forced sales by BDCs ($bn)', F_B); put(ws_bdc, 'C43', '=SUM(Y6:Y39)', F_CALC, NUM)
put(ws_bdc, 'B44', 'BDCs losing IG (count)', F_B); put(ws_bdc, 'C44', '=SUM(U6:U39)', F_CALC, INT)
put(ws_bdc, 'B45', 'BDCs below 150% coverage (count)', F_B); put(ws_bdc, 'C45', '=COUNTIF(R6:R39,"<1.5")', F_CALC, INT)
put(ws_bdc, 'B46', 'Asset share below 150% coverage (panic news input)', F_B); put(ws_bdc, 'C46', '=SUMPRODUCT((R6:R39<1.5)*C6:C39)/SUM(C6:C39)', F_CALC, PCT)
put(ws_bdc, 'A48', 'Sources: Q2-26 10-Qs, P/NAV 6-Oct-26; unsecured share = 10-Q debt notes (orange = 50% assumed where not computed); FSK / TCPC already below IG (Moody\'s Ba1 / Fitch BB+; KBRA BB+).', F_NOTE)
ws_bdc.freeze_panes = 'B6'; widths(ws_bdc, {'A': 10, **{CLT(k): 11 for k in range(2, 31)}})

# ================================================================ BDC_EAD
title(ws_ead, 'Bank exposure to named BDC facilities (USD bn): estimated lender shares and stressed EAD',
      'Rows = facility vehicle, columns = bank. Blocks: SPV commitments, SPV outstanding, revolver commitments, revolver outstanding (inputs); stressed EAD (formulas). Lender amounts are equal-split estimates where syndicate shares are not disclosed.')
BLK = {'spv_c': 6, 'spv_o': 31, 'rev_c': 56, 'rev_o': 81, 'EADspv': 106, 'EADrev': 131}
LBL = {'spv_c': 'SPV commitments', 'spv_o': 'SPV outstanding', 'rev_c': 'Revolver commitments', 'rev_o': 'Revolver outstanding',
       'EADspv': 'Stressed EAD, SPV = outstanding + CCF x undrawn', 'EADrev': 'Stressed EAD, revolver (100% drawn if BDC loses IG)'}
for blk, r0 in BLK.items():
    put(ws_ead, f'A{r0 - 1}', LBL[blk], F_B, fill=FILL_SUB)
    for k, bid in enumerate(IDS): put(ws_ead, f'{EADCOL[bid]}{r0 - 1}', bid, F_B, fill=FILL_SUB)
    for v, veh in enumerate(VEH):
        r = r0 + v
        put(ws_ead, f'A{r}', veh, F_N)
        if blk in ('spv_c', 'spv_o', 'rev_c', 'rev_o'):
            put(ws_ead, f'B{r}', f'=MATCH(A{r},BDC!$A$6:$A$39,0)', F_CALC, INT)
            for bid in IDS:
                put(ws_ead, f'{EADCOL[bid]}{r}', D['bdc_ead'][blk][bid][v], F_IN, NUM2).fill = FILL_EST
        elif blk == 'EADspv':
            for bid in IDS:
                cl = EADCOL[bid]
                put(ws_ead, f'{cl}{r}', f'={cl}{31 + v}+p_ccf_bl*({cl}{6 + v}-{cl}{31 + v})', F_CALC, NUM2)
            put(ws_ead, f'AB{r}', f'=INDEX(BDC!$AA$6:$AA$39,$B{6 + v})', F_LINK, PCT)   # LRspv0
            put(ws_ead, f'AC{r}', f'=INDEX(BDC!$AB$6:$AB$39,$B{6 + v})', F_LINK, PCT)   # LRrev0
        else:
            put(ws_ead, f'AB{r}', f'=MAX(p_ccf_bl,INDEX(BDC!$U$6:$U$39,$B{6 + v})*p_ccf_dg)', F_CALC, PCT)
            for bid in IDS:
                cl = EADCOL[bid]
                put(ws_ead, f'{cl}{r}', f'={cl}{81 + v}+$AB{r}*({cl}{56 + v}-{cl}{81 + v})', F_CALC, NUM2)
put(ws_ead, 'AB105', 'LR SPV (std)', F_B); put(ws_ead, 'AC105', 'LR revolver (std)', F_B); put(ws_ead, 'AB130', 'Revolver CCF', F_B)
put(ws_ead, 'A154', 'Undrawn BDC commitments drawn in stress ($bn)', F_B)
for bid in IDS:
    cl = EADCOL[bid]
    put(ws_ead, f'{cl}154', f'=SUM({cl}106:{cl}127)-SUM({cl}31:{cl}52)+SUM({cl}131:{cl}152)-SUM({cl}81:{cl}102)', F_CALC, NUM2)
ws_ead.freeze_panes = 'C6'; widths(ws_ead, {'A': 10, 'B': 6, **{EADCOL[b]: 8 for b in IDS}, 'AB': 12, 'AC': 12})

# ================================================================ AI_Deals
title(ws_ai, 'AI / GPU / data-centre deals: per-deal loss rate and estimated bank holds (USD bn)',
      'GPU loans: LGD = max(0, 1 - (1 - liquidation cost) x collateral(t) / balance(t)), collateral(t) = (1 - annual decline)^t, balance(t) = LTV x (1 - share repaid). Holds are deal-role estimates (pre-sell-down), not disclosed positions.')
AH = ['#', 'Deal', 'Category', 'Lessee key', 'PD 3-yr', 'PD | AI factor', 'LTV / cost', 'Share repaid by t', 'Cash-collat. share', 'LGD (non-GPU)',
      'In syndication (1/0)', 'Senior backstopped share', 'MTM already quoted (pts)', 'Balance(t) / cost', 'Collateral(t) / cost', 'LGD GPU', 'Loss rate', 'RCF (1/0)', 'Size ($bn)']
hdr(ws_ai, 5, 1, AH + IDS + ['Rating / lessee', 'Model note'])
AIB = {bid: CLT(len(AH) + 1 + k) for k, bid in enumerate(IDS)}
AR0 = 6; AR1 = AR0 + ND - 1
for k, x in enumerate(DEALS):
    r = AR0 + k
    put(ws_ai, f'A{r}', x['idx'], F_N); put(ws_ai, f'B{r}', x['deal'], F_N); put(ws_ai, f'C{r}', x['cat'], F_IN); put(ws_ai, f'D{r}', x['lessee'], F_IN)
    put(ws_ai, f'E{r}', f'=IF(C{r}="NONE",0,IFERROR(INDEX(rng_lessee_pd,MATCH(D{r},rng_lessee_key,0)),g_pd_unrated))', F_CALC, PCT2)
    put(ws_ai, f'F{r}', f'=IF(E{r}<=0,0,NORMSDIST((NORMSINV(E{r})-SQRT(g_rho_ai)*p_z_ai)/SQRT(1-g_rho_ai)))', F_CALC, PCT2)
    for col, key, fmt in [('G', 'ltv', PCT), ('H', 'frep', PCT), ('I', 'cash', PCT), ('J', 'lgd', PCT), ('K', 'uw', INT), ('L', 'senior', PCT), ('M', 'mtm0', NUM)]:
        v = x[key] if x[key] is not None else 0
        c = put(ws_ai, f'{col}{r}', v, F_IN, fmt)
        if x['cat'] != 'NONE' and key in ('ltv', 'frep', 'lgd', 'senior'): c.fill = FILL_EST
    put(ws_ai, f'N{r}', f'=G{r}*(1-H{r})', F_CALC, PCT); put(ws_ai, f'O{r}', f'=(1-p_gpu_r)^g_t_def', F_CALC, PCT)
    put(ws_ai, f'P{r}', f'=IF(N{r}>0,MAX(0,1-(1-g_c_gpu)*O{r}/N{r})*(1-I{r}),0)', F_CALC, PCT)
    put(ws_ai, f'Q{r}', f'=IF(C{r}="GPU",F{r}*P{r}+K{r}*p_uw_drop,IF(C{r}="RCF",p_ccf_ai*F{r}*J{r},IF(C{r}="DC",F{r}*J{r}+K{r}*p_uw_drop+M{r}/100,'
                        f'IF(C{r}="UNSEC",F{r}*J{r},IF(C{r}="MARGIN",F{r}*MAX(0,G{r}-(1-p_oai_drop)*(1-g_c_gpu))/G{r},IF(C{r}="ANTH",F{r}*(L{r}*0.1+(1-L{r})*0.7)+p_uw_drop,0))))))', F_CALC, PCT)
    put(ws_ai, f'R{r}', f'=IF(C{r}="RCF",1,0)', F_CALC, INT); put(ws_ai, f'S{r}', x['size'], F_IN, NUM)
    for bid in IDS:
        c = put(ws_ai, f'{AIB[bid]}{r}', x['holds'][bid], F_IN, NUM2)
        if x['holds'][bid]: c.fill = FILL_EST
    put(ws_ai, f'{CLT(len(AH) + NB + 1)}{r}', x['rating'], F_NOTE); put(ws_ai, f'{CLT(len(AH) + NB + 2)}{r}', x['note'], F_NOTE)
r = AR1 + 2
put(ws_ai, f'B{r}', 'Total holds by bank ($bn)', F_B)
for bid in IDS: put(ws_ai, f'{AIB[bid]}{r}', f'=SUM({AIB[bid]}{AR0}:{AIB[bid]}{AR1})', F_CALC, NUM)
put(ws_ai, f'B{r + 1}', 'Category codes: GPU = GPU-collateralised loan; DC = data-centre real estate / construction; RCF = revolver (drawn in stress); UNSEC = unsecured corporate bridge; MARGIN = share-backed margin loan; ANTH = $60bn Anthropic package (senior Broadcom-backstopped LGD 10%, junior LGD 70%); NONE = no bank hold attributed.', F_NOTE)
ws_ai.freeze_panes = 'C6'; widths(ws_ai, {'A': 4, 'B': 40, **{CLT(k): 10 for k in range(3, len(AH) + NB + 1)}, CLT(len(AH) + NB + 1): 40, CLT(len(AH) + NB + 2): 60})

# ================================================================ Network
title(ws_n, 'Interbank network: max-entropy (RAS) matrix, transposed (rows = debtor, columns = creditor), USD bn',
      'Row/column totals reproduce intra-financial-system liabilities/assets (OFR Bank Systemic Risk Monitor, FR Y-15 Q2-26 for US G-SIBs; Basel end-2024 x 1.0389 for others; 3% of assets estimate for regionals, 15% for Jefferies). Loss to creditor i = lgd_ib x s_in x u_ib x sum_j X[i,j] x default_j.')
for k, bid in enumerate(IDS):
    put(ws_n, f'{EADCOL[bid]}5', bid, F_B, fill=FILL_SUB); put(ws_n, f'A{R0 + k}', bid, F_B, fill=FILL_SUB)
X = D['network']['X']
for j, dj in enumerate(IDS):          # debtor row
    for i, ci in enumerate(IDS):      # creditor column
        put(ws_n, f'{EADCOL[ci]}{R0 + j}', X[i][j], F_IN, NUM)
put(ws_n, f'A{R0 + NB}', 'Creditor total', F_B); put(ws_n, f'AB5', 'Debtor total', F_B)
for bid in IDS: put(ws_n, f'{EADCOL[bid]}{R0 + NB}', f'=SUM({EADCOL[bid]}{R0}:{EADCOL[bid]}{R0 + NB - 1})', F_CALC, NUM)
for j in range(NB):
    put(ws_n, f'AB{R0 + j}', f'=SUM(C{R0 + j}:Z{R0 + j})', F_CALC, NUM)
    put(ws_n, f'AD{R0 + j}', f'=INDEX($C$30:$Z$30,1,{j + 1})', F_CALC, NUM)
put(ws_n, 'AD5', 'Creditor total (as column)', F_B)
widths(ws_n, {'A': 8, **{EADCOL[b]: 8 for b in IDS}, 'AB': 12})

# ================================================================ Modules (standalone)
def ib(key, i): return f'Inputs_Banks!${COL[key]}{R0 + i}'
title(ws_m, 'Standalone module losses by bank (USD bn, pre-tax) - each module can be switched off in Scenarios (sw_M*)',
      'M1 back-leverage look-through | M2 fund finance | M3 ABF / structured entities | M4 PE-owned insurers | M5 AI / GPU | M6 trading & HFS MTM | M7 CRE | M8 rates (AFS + forced HTM sales) | M9 SRT relief loss | M10 written sub-IG TRS | M11 prime / margin gap risk.')
MH = ['Id', 'Institution', 'M1a named BDC facilities', 'M1b generic back-leverage', 'M1c collateral fraud', 'M1 back-leverage', 'M2 fund finance',
      'M3 ABF / SE', 'M4 insurers', 'M5 AI / GPU', 'M6 trading / HFS', 'M7 CRE', 'AFS MTM (rates)', 'HTM / opt-out AFS loss pool', 'M8 rates',
      'M9 SRT', 'M10 TRS', 'M11 prime', 'Total standalone loss', 'Contagion-invariant losses', 'Capital base (CET1 + PPNR credit)',
      'Stressed RWA', 'CET1 after standalone', 'CET1 ratio after standalone', 'Committed lines drawn ($bn, liquidity)', 'AI RCF draws ($bn)']
hdr(ws_m, 5, 1, MH)
for i, bid in enumerate(IDS):
    r = R0 + i; ec = EADCOL[bid]; ac = AIB[bid]; hr = R0 + i
    F = {
     'A': bid, 'B': B[bid]['name'],
     'C': f'=SUMPRODUCT(BDC_EAD!{ec}$106:{ec}$127,BDC_EAD!$AB$106:$AB$127)+SUMPRODUCT(BDC_EAD!{ec}$131:{ec}$152,BDC_EAD!$AC$106:$AC$127)',
     'D': f'=({ib("blr_d", i)}+p_ccf_bl*{ib("blr_u", i)})*CE_LRg0',
     'E': f'=p_fraud*({ib("bl_d", i)}+{ib("ff_d", i)}+{ib("abf_d", i)})',
     'F': f'=p_sw_M1*(C{r}+D{r}+E{r})',
     'G': f'=p_sw_M2*({ib("ff_d", i)}+p_ccf_ff*{ib("ff_u", i)})*CE_LRff',
     'H': f'=p_sw_M3*({ib("abf_d", i)}+p_ccf_abf*{ib("abf_u", i)})*CE_LRa0',
     'I': f'=p_sw_M4*({ib("ins_fac", i)}*p_ccf_ins+{ib("ins_repo", i)})*p_pd_ins*g_lgd_ins',
     'J': f'=p_sw_M5*SUMPRODUCT(AI_Deals!{ac}${AR0}:{ac}${AR1},AI_Deals!$Q${AR0}:$Q${AR1})',
     'K': f'=p_sw_M6*(SUMPRODUCT(Holdings!$C{hr}:$O{hr},Holdings!$C$32:$O$32,Holdings!$C$35:$O$35)+{ib("strat_eq", i)}*(-p_dp_EQ))',
     'L': f'=p_sw_M7*{ib("cre", i)}*p_cre_lr',
     'M': f'={ib("aoci", i)}*{ib("afs_fv", i)}*{ib("dur_afs", i)}*p_dy',
     'N': f'=MAX(0,-{ib("htm_ul", i)}+{ib("htm_ac", i)}*g_dur_htm*p_dy)+(1-{ib("aoci", i)})*MAX(0,-{ib("afs_ul", i)}+{ib("afs_fv", i)}*{ib("dur_afs", i)}*p_dy)',
     'O': f'=p_sw_M8*(M{r}+N{r}*p_htm_forced)',
     'P': f'=p_sw_M9*p_srt_lost*{ib("srt_bp", i)}/10000*{ib("rwa", i)}',
     'Q': f'=p_sw_M10*{ib("trs", i)}*CE_LRtrs0',
     'R': f'=p_sw_M11*{ib("pb", i)}*p_pb_pd*MAX(0,p_pb_shock*g_pb_conc-g_pb_margin)',
     'S': f'=F{r}+G{r}+H{r}+I{r}+J{r}+K{r}+L{r}+O{r}+P{r}+Q{r}+R{r}',
     'T': f'=G{r}+I{r}+J{r}+K{r}+L{r}+P{r}+R{r}',
     'U': f'={ib("cet1", i)}+p_ppnr_q*{ib("ppnr_q", i)}',
     'V': f'={ib("rwa", i)}*(1+p_rwa_infl)',
     'W': f'=U{r}-(1-p_tax)*S{r}', 'X': f'=W{r}/V{r}',
     'Z': f'=p_ccf_ai*SUMPRODUCT(AI_Deals!{ac}${AR0}:{ac}${AR1},AI_Deals!$R${AR0}:$R${AR1})',
     'Y': f'=p_sw_M1*(p_ccf_bl*{ib("blr_u", i)}+BDC_EAD!{ec}$154)+p_sw_M2*p_ccf_ff*{ib("ff_u", i)}+p_sw_M3*p_ccf_abf*{ib("abf_u", i)}+p_sw_M5*Z{r}+p_sw_M4*p_ccf_ins*{ib("ins_fac", i)}',
    }
    for col, f in F.items():
        put(ws_m, f'{col}{r}', f, F_N if col in 'AB' else F_CALC, None if col in 'AB' else (PCT2 if col == 'X' else NUM))
rt = R0 + NB
put(ws_m, f'B{rt}', 'Total', F_B)
for k in range(3, 27):
    cl = CLT(k)
    if cl != 'X': put(ws_m, f'{cl}{rt}', f'=SUM({cl}{R0}:{cl}{rt - 1})', F_CALC, NUM, bold=True)
ws_m.freeze_panes = 'C6'; widths(ws_m, {'A': 7, 'B': 17, **{CLT(k): 11 for k in range(3, 27)}})

# ================================================================ Contagion
cg = ws_c
title(cg, f'Contagion rounds: news -> panic -> runs & repo -> forced sales -> prices -> marks -> interbank defaults ({ROUNDS} rounds, cumulative)',
      'Each block starts from capital at the end of the previous block. Public news at the start of a round sets panic intensity S (cols CC-CD), which raises run, redemption and haircut rates, '
      'pushes marks to market-implied levels, worsens the credit factor and adds a panic discount to every risky asset class (correlations go to 1). Sales and price impacts are cumulative totals.')
CHK_ = [('id', 'Id'), ('K0', 'CET1 start ($bn)'), ('rs', 'CET1 ratio start'), ('mda', 'MDA breach'), ('mn', 'Below min'), ('ins', 'Insolvent'),
        ('notch', 'Notches'), ('hr', 'Headroom to MDA (pp)'), ('rank', 'Headroom rank (1 = weakest)'), ('weak', 'Run target (1/0)'),
        ('strong', 'Flight-to-quality recipient (1/0)'), ('trig', 'Contractual trigger outflow'), ('o_dep', 'Deposit run-off'),
        ('o_wh', 'Wholesale non-rollover'), ('o_cp', 'MMF CP/CD non-rollover'), ('o_hc', 'Repo haircut + inventory non-rollover'),
        ('draws', 'Committed-line draws'), ('okdep', 'Recipient deposits'), ('inflow', 'Flight-to-quality inflow'), ('outflow', 'Total outflow'),
        ('avail', 'Liquidity available'), ('SF', 'Liquidity shortfall'), ('illiq', 'Illiquid (1/0)'), ('f_htm', 'HTM sale fraction'),
        ('dRWA', 'RWA to shed'), ('cap_sales', 'Capital-driven sales'), ('bank_sales', 'Bank asset sales')] + \
       [('sold_' + k, 'Sold ' + k) for k in CLK] + \
       [('pull', 'MMF pull share'), ('mb', 'Matched-book client sales'), ('dflt', 'Default / resolution (1/0)'), ('IB', 'Interbank loss'),
        ('M1r', 'M1 at round prices'), ('M3r', 'M3 at round prices'), ('M10r', 'M10 at round prices'), ('M8r', 'M8 incl. run-driven HTM sales'),
        ('mtm', 'Market-discount MTM on holdings'), ('Lr', 'Total loss'), ('K', 'CET1 end ($bn)'), ('ratio', 'CET1 ratio end'), ('anyd', 'Start-of-round default (helper)')]
CC = {k: CLT(1 + j) for j, (k, _) in enumerate(CHK_)}
SK = {k: CC['sold_' + k] for k in CLK}
# right-hand tables
VT = {'veh': 'BA', 'Vh': 'BB', 'MTM': 'BC', 'sec': 'BD', 'Vl': 'BE', 'LRspv': 'BF', 'LRrev': 'BG'}
BT_KEYS = ['name', 'Vh', 'MTM', 'AC', 'covA', 'def_bb', 'def_reg', 'honored', 'red', 'sales']
BT = {k: CLT(61 + j) for j, k in enumerate(BT_KEYS)}            # BI..BR
PT = {'rating': 'BT', 'PDg': 'BU', 'PDs': 'BV'}
SYSK = ['cov_prev', 'fs_prev', 'news', 'S', 'z_eff', 'ds_eff', 'wmk', 'theta_eff', 'red_eff', 'req_mult', 'pull_b', 'recyc_eff', 'dm_eff', 'ins_r',
        'PDg', 'PDs', 'Lg', 'Ls', 'MTMg', 'MTMs', 'Vh_g', 'MTM_sys', 'Vl_g', 'LRg', 'LRa', 'LRtrs', 'cov', 'nonbank_pcl']
SYSL = {'cov_prev': 'News in: BDC asset share <150% coverage (prev. round)', 'fs_prev': 'News in: private-credit market discount (prev. round)',
        'news': 'News index', 'S': 'PANIC INTENSITY S (0-1)', 'z_eff': 'Credit factor after credit crunch', 'ds_eff': 'Spread widening (bp)',
        'wmk': 'Weight on market-implied marks', 'theta_eff': 'BDC deleveraging by sales', 'red_eff': 'Honoured redemptions cap',
        'req_mult': 'Redemption-request multiple', 'pull_b': 'MMF pull, all dealers', 'recyc_eff': 'Flight-to-quality redeposit share',
        'dm_eff': 'Dealer-capacity multiplier', 'ins_r': 'Insurer forced sales ($bn)', 'PDg': 'Pool PD 3-yr generic', 'PDs': 'Pool PD 3-yr software',
        'Lg': 'Incremental loss generic', 'Ls': 'Incremental loss software', 'MTMg': 'Spread MTM generic', 'MTMs': 'Spread MTM software',
        'Vh_g': 'Generic pool value, hold', 'MTM_sys': 'Generic pool spread MTM', 'Vl_g': 'Generic pool value, liquidated',
        'LRg': 'LR generic back-leverage', 'LRa': 'LR ABF warehouses', 'LRtrs': 'LR written TRS', 'cov': 'BDC asset share <150% coverage (this round)',
        'nonbank_pcl': 'Private-credit loans sold by non-banks ($bn)'}
BLOCK = 40
def base(rnd): return 5 + (rnd - 1) * BLOCK
def sysref(rnd, key): return f'$CD${base(rnd) + 2 + SYSK.index(key)}'
GS_RNG = 'Inputs_Banks!$D$6:$D$29'
for rnd in range(1, ROUNDS + 1):
    b0 = base(rnd); h = b0 + 1; f0 = b0 + 2; f1 = f0 + NB - 1; rs = f1 + 1; rf = f1 + 2
    S_ = sysref(rnd, 'S')
    def sr(k): return sysref(rnd, k)
    put(cg, f'A{b0}', f'ROUND {rnd}', F_B, fill=FILL_SUB)
    hdr(cg, h, 1, [lab for _, lab in CHK_])
    hdr(cg, h, 53, ['Vehicle', 'Pool value hold', 'Spread MTM', 'Secured/assets', 'Pool value liquidated', 'LR SPV', 'LR revolver'])
    hdr(cg, h, 61, ['BDC', 'Pool value hold', 'Spread MTM', 'Asset coverage', 'Assets <150% ($bn)', 'Borrowing-base deficiency', '150% deficiency',
                    'Honoured redemptions', 'Redemption sales (% assets)', 'Forced sales ($bn)'])
    hdr(cg, h, 72, ['Rating', 'PD generic', 'PD software'])
    hdr(cg, h, 81, ['System item', 'Value'])
    # ---- system cells
    nG = 'SUM(' + GS_RNG + ')'
    L0n = '(1/(1+EXP(g_theta_news/g_tau_news)))'
    pcl_col = SK['PRIV_CREDIT_LOANS']; abs_col = SK['ABS_OTHER']; eq_col = SK['EQUITIES']
    SYSF = {
     'cov_prev': '=BDC!$C$46' if rnd == 1 else f'={sysref(rnd - 1, "cov")}',
     'fs_prev': '=0' if rnd == 1 else f'=${pcl_col}${base(rnd - 1) + 2 + NB + 1}',
     'news': f'=p_news0+g_w_cov*{sr("cov_prev")}+g_w_notch*SUMPRODUCT(${CC["notch"]}${f0}:${CC["notch"]}${f1},{GS_RNG})/(3*{nG})'
             f'+g_w_mda*SUMPRODUCT(${CC["mda"]}${f0}:${CC["mda"]}${f1},{GS_RNG})/{nG}+g_w_def*MAX(${CC["anyd"]}${f0}:${CC["anyd"]}${f1})+g_w_fs*{sr("fs_prev")}/0.3',
     'S': f'=p_panic_on*(p_S0+(1-p_S0)*MAX(0,1/(1+EXP(-({sr("news")}-g_theta_news)/g_tau_news))-{L0n})/(1-{L0n}))',
     'z_eff': f'=p_z-p_zc*{S_}', 'ds_eff': f'=p_ds+p_ds_pan*{S_}', 'wmk': f'=p_w_mkt+(1-p_w_mkt)*{S_}',
     'theta_eff': f'=p_theta_lev+(1-p_theta_lev)*{S_}', 'red_eff': f'=p_red_rate+p_red_pan*{S_}', 'req_mult': f'=1+p_req_pan*{S_}',
     'pull_b': f'=p_pull_base+p_pull_pan*{S_}', 'recyc_eff': f'=p_recyc*(1-p_rec_pan*{S_})', 'dm_eff': f'=p_dealer_mult*(1+p_dm_pan*{S_})',
     'ins_r': f'=MIN(1,p_ins_run+p_ins_pan*{S_})*(g_fabr+g_fabn_6m)',
     'PDg': f'=SUMPRODUCT(CreditEngine!$B$6:$B$10,${PT["PDg"]}${f0}:${PT["PDg"]}${f0 + 4})',
     'PDs': f'=SUMPRODUCT(CreditEngine!$B$6:$B$10,${PT["PDs"]}${f0}:${PT["PDs"]}${f0 + 4})',
     'Lg': f'={sr("PDg")}*p_lgd_gen-CE_PDb*g_lgd_gen_b', 'Ls': f'={sr("PDs")}*p_lgd_sw-CE_PDb*g_lgd_sw_b',
     'MTMg': f'=(1-{sr("PDg")})*{sr("ds_eff")}/10000*g_dur_s', 'MTMs': f'=(1-{sr("PDs")})*({sr("ds_eff")}+p_ds_sw)/10000*g_dur_s',
     'Vh_g': f'=1-((1-CE_sw_sys)*{sr("Lg")}+CE_sw_sys*{sr("Ls")})-p_gap-{sr("wmk")}*(1-CE_mk_sys)',
     'MTM_sys': f'=(1-CE_sw_sys)*{sr("MTMg")}+CE_sw_sys*{sr("MTMs")}',
     'Vl_g': f'={sr("Vh_g")}*(1-${pcl_col}${rf})-{sr("MTM_sys")}-p_c_liq',
     'LRg': f'=p_phi*MAX(0,p_a_spv-{sr("Vl_g")})/p_a_spv+(1-p_phi)*MAX(0,p_a_spv-{sr("Vh_g")})/p_a_spv',
     'LRa': f'=p_phi*MAX(0,g_a_abf-(CE_Vh_a*(1-${abs_col}${rf})-p_c_liq))/g_a_abf+(1-p_phi)*MAX(0,g_a_abf-CE_Vh_a)/g_a_abf',
     'LRtrs': f'=p_phi*MAX(0,g_trs_adv-{sr("Vl_g")})/g_trs_adv+(1-p_phi)*MAX(0,g_trs_adv-{sr("Vh_g")})/g_trs_adv',
     'cov': f'=SUM(${BT["covA"]}${f0}:${BT["covA"]}${f0 + NBD - 1})/SUM(BDC!$C$6:$C$39)',
     'nonbank_pcl': f'=p_pc_scale*SUM(${BT["sales"]}${f0}:${BT["sales"]}${f0 + NBD - 1})',
    }
    for j, key in enumerate(SYSK):
        r = f0 + j
        put(cg, f'CC{r}', SYSL[key], F_B if key == 'S' else F_N)
        fmt = NUM if key in ('ds_eff', 'ins_r', 'nonbank_pcl') else (NUM2 if key in ('z_eff', 'req_mult', 'dm_eff', 'news') else PCT)
        put(cg, f'CD{r}', SYSF[key], F_CALC, fmt, FILL_Y if key == 'S' else None, bold=(key == 'S'))
    # ---- pool table
    for k in range(5):
        r = f0 + k
        put(cg, f'{PT["rating"]}{r}', RATINGS[k], F_N)
        put(cg, f'{PT["PDg"]}{r}', f'=NORMSDIST((NORMSINV(CreditEngine!$D${6 + k})-SQRT(g_rho)*{sr("z_eff")})/SQRT(1-g_rho))', F_CALC, PCT)
        put(cg, f'{PT["PDs"]}{r}', f'=NORMSDIST((NORMSINV(MIN(0.999,CreditEngine!$D${6 + k}*p_m_sw))-SQRT(g_rho)*{sr("z_eff")})/SQRT(1-g_rho))', F_CALC, PCT)
    # ---- BDC table (34 rows)
    for j in range(NBD):
        r = f0 + j; br = 6 + j
        F = {'name': f'=BDC!$A${br}',
             'Vh': f'=1-((1-BDC!$D${br})*{sr("Lg")}+BDC!$D${br}*{sr("Ls")})-p_gap-{sr("wmk")}*(1-BDC!$M${br})',
             'MTM': f'=(1-BDC!$D${br})*{sr("MTMg")}+BDC!$D${br}*{sr("MTMs")}',
             'AC': f'={BT["Vh"]}{r}/BDC!$K${br}', 'covA': f'=IF({BT["AC"]}{r}<1.5,BDC!$C${br},0)',
             'def_bb': f'=MAX(0,1-{BT["Vh"]}{r}*(1-CE_mig_hc)-p_bb_cush)*BDC!$Q${br}', 'def_reg': f'=MAX(0,BDC!$K${br}-{BT["Vh"]}{r}/1.5)',
             'honored': f'=MIN(MIN(1,BDC!$H${br}*{sr("req_mult")}),{sr("red_eff")})',
             'red': f'=BDC!$I${br}*BDC!$J${br}*{BT["honored"]}{r}*(1-0.3)',
             'sales': f'=BDC!$C${br}*({sr("theta_eff")}*MAX({BT["def_bb"]}{r},{BT["def_reg"]}{r})+{BT["red"]}{r})'}
        fm = {'name': None, 'Vh': PCT, 'MTM': PCT, 'AC': NUM2, 'covA': NUM, 'def_bb': PCT, 'def_reg': PCT, 'honored': PCT, 'red': PCT, 'sales': NUM2}
        for key, f in F.items(): put(cg, f'{BT[key]}{r}', f, F_LINK if key == 'name' else F_CALC, fm[key])
    # ---- bank rows
    for i, bid in enumerate(IDS):
        r = f0 + i; m = R0 + i
        prevK = f'Modules!$W{m}' if rnd == 1 else f'{CC["K"]}{base(rnd - 1) + 2 + i}'
        prevR = f'Modules!$X{m}' if rnd == 1 else f'{CC["ratio"]}{base(rnd - 1) + 2 + i}'
        dgr = f'Inputs_Banks!${COL["dg0"]}{m}:${COL["dg6"]}{m}'
        c = lambda k: f'{CC[k]}{r}'
        rng = lambda k: f'${CC[k]}${f0}:${CC[k]}${f1}'
        F = {
         'id': bid, 'K0': f'={prevK}', 'rs': f'={prevR}', 'mda': f'=IF({c("rs")}<{ib("req", i)},1,0)', 'mn': f'=IF({c("rs")}<0.045,1,0)',
         'ins': f'=IF({c("K0")}<0,1,0)',
         'notch': f'=MIN(6,MIN(3,INT(MAX(0,{ib("r0", i)}-{c("rs")})/p_notch_step))+{c("mda")}+2*{c("mn")})',
         'hr': f'={c("rs")}-{ib("req", i)}', 'rank': f'=RANK({c("hr")},{rng("hr")},1)',
         'weak': f'=MAX(IF({c("rank")}<=g_n_weak,1,0),{c("mn")})', 'strong': f'=IF({c("rank")}>{NB / 2},1,0)*(1-{c("mn")})',
         'trig': f'=INDEX({dgr},1,{c("notch")}+1)',
         'o_dep': f'={ib("unins", i)}*MIN(1,p_u_base+{S_}*p_u_pan_all+{c("weak")}*({S_}*p_u_pan_weak+p_u_mda*{c("mda")})+p_u_notch*{c("notch")}+p_u_fail*{c("mn")})',
         'o_wh': f'={ib("stwf", i)}*MIN(1,p_w_base+p_w_pan*{S_}+p_w_notch*{c("notch")}+0.5*{c("mda")}+1*{c("mn")})',
         'o_cp': f'={ib("mmf_cp", i)}*MIN(1,p_cp_base+p_cp_pan*{S_}+p_cp_notch*{c("notch")})',
         'o_hc': f'={ib("repo_ng", i)}*(p_dh+p_dh_pan*{S_}+MIN(1,0.5*{sr("pull_b")}+0.25*{c("notch")}))',
         'draws': f'=Modules!$Y{m}', 'okdep': f'={ib("deposits", i)}*{c("strong")}',
         'inflow': f'=p_liq_on*{sr("recyc_eff")}*SUM({rng("o_dep")})*{c("okdep")}/MAX(0.000000001,SUM({rng("okdep")}))',
         'outflow': f'=p_liq_on*({c("trig")}+{c("o_dep")}+{c("o_wh")}+{c("o_cp")}+{c("o_hc")}+{c("draws")})',
         'avail': f'=g_usable*{ib("hqla", i)}+p_cb_on*{ib("cb_cap", i)}+{c("inflow")}',
         'SF': f'=MAX(0,{c("outflow")}-{c("avail")})', 'illiq': f'=IF({c("SF")}>0.9*{ib("sale_tot", i)},1,0)',
         'f_htm': f'=MAX(p_htm_forced,(1-p_cb_on)*MIN(1,{c("outflow")}/{ib("hqla", i)})*g_theta_sell)',
         'dRWA': f'=MAX(0,Modules!$V{m}-{c("K0")}/({ib("req", i)}+g_del_buf))',
         'cap_sales': f'=MIN(g_del_cap*{ib("sale_tot", i)},{c("dRWA")})', 'bank_sales': f'=MIN({ib("sale_tot", i)},{c("SF")}+{c("cap_sales")})',
        }
        for j, k in enumerate(CLK):
            F['sold_' + k] = f'=${CC["bank_sales"]}{r}*Holdings!{CLT(17 + j)}{m}'
        F.update({
         'pull': f'=MIN(1,{sr("pull_b")}+0.5*{c("notch")})', 'mb': f'=p_liq_on*{ib("mmf_rep_oth", i)}*{c("pull")}*p_mb_psi',
         'dflt': f'=MAX({c("ins")},{c("mn")},{c("illiq")}*(1-p_cb_on))',
         'IB': f'=p_ib_on*p_lgd_ib*g_s_in*g_u_ib*SUMPRODUCT(Network!{EADCOL[bid]}$6:{EADCOL[bid]}$29,{rng("dflt")})',
         'M1r': f'=p_sw_M1*(SUMPRODUCT(BDC_EAD!{EADCOL[bid]}$106:{EADCOL[bid]}$127,${VT["LRspv"]}${f0}:${VT["LRspv"]}${f0 + NV - 1})'
                f'+SUMPRODUCT(BDC_EAD!{EADCOL[bid]}$131:{EADCOL[bid]}$152,${VT["LRrev"]}${f0}:${VT["LRrev"]}${f0 + NV - 1})'
                f'+({ib("blr_d", i)}+p_ccf_bl*{ib("blr_u", i)})*{sr("LRg")}+Modules!$E{m})',
         'M3r': f'=p_sw_M3*({ib("abf_d", i)}+p_ccf_abf*{ib("abf_u", i)})*{sr("LRa")}',
         'M10r': f'=p_sw_M10*{ib("trs", i)}*{sr("LRtrs")}',
         'M8r': f'=p_sw_M8*(Modules!$M{m}+Modules!$N{m}*IF(p_liq_on>0,{c("f_htm")},p_htm_forced))',
         'mtm': f'=SUMPRODUCT(Holdings!$C{m}:$O{m},Holdings!$C$32:$O$32,${SK[CLK[0]]}${rf}:${SK[CLK[-1]]}${rf})+{ib("strat_eq", i)}*${eq_col}${rf}',
         'Lr': f'=Modules!$T{m}+{c("M1r")}+{c("M3r")}+{c("M10r")}+{c("M8r")}+{c("mtm")}+{c("IB")}',
         'K': f'=Modules!$U{m}-(1-p_tax)*{c("Lr")}', 'ratio': f'={c("K")}/Modules!$V{m}', 'anyd': f'=MAX({c("ins")},{c("mn")})',
        })
        fmts = {'rs': PCT2, 'mda': INT, 'mn': INT, 'ins': INT, 'notch': INT, 'hr': PCT2, 'rank': INT, 'weak': INT, 'strong': INT, 'illiq': INT,
                'f_htm': PCT, 'pull': PCT, 'dflt': INT, 'ratio': PCT2, 'anyd': INT}
        for key, f in F.items(): put(cg, f'{CC[key]}{r}', f, F_N if key == 'id' else F_CALC, None if key == 'id' else fmts.get(key, NUM))
    put(cg, f'{CC["bank_sales"]}{rs}', 'Total sold ($bn)', F_B); put(cg, f'{CC["bank_sales"]}{rf}', 'Market discount', F_B)
    for j, k in enumerate(CLK):
        cl = SK[k]; hc = CLT(3 + j)
        put(cg, f'{cl}{rs}', f'=p_fs_on*(SUM({cl}{f0}:{cl}{f1})+{sr("ins_r")}*Holdings!{hc}$37' + (f'+{sr("nonbank_pcl")}' if k == 'PRIV_CREDIT_LOANS' else '')
            + f'+Holdings!{hc}$36*SUM(${CC["mb"]}${f0}:${CC["mb"]}${f1}))', F_CALC, NUM, bold=True)
        put(cg, f'{cl}{rf}', f'=MIN(Holdings!{hc}$34,{sr("dm_eff")}*Holdings!{hc}$31*{cl}{rs}/10000+Holdings!{hc}$39*{S_}^g_gamma_pan)', F_CALC, PCT, bold=True)
    pclr = f'${pcl_col}${rf}'
    for v, veh in enumerate(VEH):
        r = f0 + v
        put(cg, f'{VT["veh"]}{r}', veh, F_N)
        put(cg, f'{VT["Vh"]}{r}', f'=INDEX(${BT["Vh"]}${f0}:${BT["Vh"]}${f0 + NBD - 1},BDC_EAD!$B{6 + v})', F_CALC, PCT)
        put(cg, f'{VT["MTM"]}{r}', f'=INDEX(${BT["MTM"]}${f0}:${BT["MTM"]}${f0 + NBD - 1},BDC_EAD!$B{6 + v})', F_CALC, PCT)
        put(cg, f'{VT["sec"]}{r}', f'=INDEX(BDC!$Q$6:$Q$39,BDC_EAD!$B{6 + v})', F_LINK, PCT)
        put(cg, f'{VT["Vl"]}{r}', f'={VT["Vh"]}{r}*(1-{pclr})-{VT["MTM"]}{r}-p_c_liq', F_CALC, PCT)
        put(cg, f'{VT["LRspv"]}{r}', f'=p_phi*MAX(0,p_a_spv-{VT["Vl"]}{r})/p_a_spv+(1-p_phi)*MAX(0,p_a_spv-{VT["Vh"]}{r})/p_a_spv', F_CALC, PCT)
        put(cg, f'{VT["LRrev"]}{r}', f'=IF({VT["sec"]}{r}>0,p_phi*MAX(0,{VT["sec"]}{r}-{VT["Vl"]}{r})/{VT["sec"]}{r}+(1-p_phi)*MAX(0,{VT["sec"]}{r}-{VT["Vh"]}{r})/{VT["sec"]}{r},0)', F_CALC, PCT)
cg.freeze_panes = 'B5'; widths(cg, {'A': 7, **{CLT(k): 10 for k in range(2, 83)}, 'CC': 44, 'CD': 11})
LAST = base(ROUNDS) + 2   # first bank row of last block
LSYS = lambda key: sysref(ROUNDS, key).replace('$', '')

# ================================================================ Results
rr = ws_r
title(rr, 'Results for the active scenario (USD bn; ratios = CET1 / stressed RWA)', 'Green = link to Modules / Contagion. Status: Insolvent (CET1<0) > Below minimum (<4.5%) > MDA breach (<requirement) > Needs liquidity (shortfall after HQLA and backstop) > OK.')
RH = ['Id', 'Institution', 'G-SIB', 'CET1 ratio now', 'Requirement (MDA)', 'Standalone loss', 'CET1 ratio after standalone', 'Final loss (after contagion)',
      'CET1 ratio final', 'Contagion add-on', 'Headroom to MDA ($bn)', 'Status', 'Notches (final round)', 'Liquidity outflow', 'Liquidity shortfall',
      'Market-discount MTM', 'Interbank loss', 'Back-leverage re-mark at round prices', 'Rates incl. run-driven HTM sales', 'Loss % CET1', 'Run target in final round']
hdr(rr, 5, 1, RH)
for i, bid in enumerate(IDS):
    r = R0 + i; m = R0 + i; c = LAST + i
    cc = lambda k: f'Contagion!{CC[k]}{c}'
    F = {'A': bid, 'B': B[bid]['name'], 'C': f'={ib("gsib", i)}', 'D': f'={ib("r0", i)}', 'E': f'={ib("req", i)}', 'F': f'=Modules!S{m}',
         'G': f'=Modules!X{m}', 'H': f'={cc("Lr")}', 'I': f'={cc("ratio")}', 'J': f'=H{r}-F{r}', 'K': f'={cc("K")}-E{r}*Modules!V{m}',
         'L': f'=IF({cc("K")}<0,"Insolvent",IF(I{r}<0.045,"Below minimum",IF(I{r}<E{r},"MDA breach",IF({cc("SF")}>0,"Needs liquidity","OK"))))',
         'M': f'={cc("notch")}', 'N': f'={cc("outflow")}', 'O': f'={cc("SF")}', 'P': f'={cc("mtm")}', 'Q': f'={cc("IB")}',
         'R': f'={cc("M1r")}-Modules!F{m}', 'S': f'={cc("M8r")}', 'T': f'=H{r}/{ib("cet1", i)}', 'U': f'={cc("weak")}'}
    fm = {'C': INT, 'D': PCT2, 'E': PCT2, 'G': PCT2, 'I': PCT2, 'M': INT, 'T': PCT, 'U': INT}
    for col, f in F.items(): put(rr, f'{col}{r}', f, F_N if col in 'AB' else (F_LINK if col in 'CDEFGHIMNOPQSU' else F_CALC), None if col in 'ABL' else fm.get(col, NUM))
rt = R0 + NB
put(rr, f'B{rt}', 'Total', F_B)
for col in 'FHJNOPQRS': put(rr, f'{col}{rt}', f'=SUM({col}{R0}:{col}{rt - 1})', F_CALC, NUM, bold=True)
SYS = [('Standalone loss, all banks ($bn)', f'=SUM(F{R0}:F{rt - 1})', NUM), ('Final loss, all banks ($bn)', f'=SUM(H{R0}:H{rt - 1})', NUM),
       ('Contagion amplification (final / standalone)', f'=IF(B{rt + 3}>0,B{rt + 4}/B{rt + 3},0)', NUM2),
       ('G-SIBs below MDA', f'=SUMPRODUCT((I{R0}:I{rt - 1}<E{R0}:E{rt - 1})*C{R0}:C{rt - 1})', INT),
       ('G-SIBs below 4.5% minimum', f'=SUMPRODUCT((I{R0}:I{rt - 1}<0.045)*C{R0}:C{rt - 1})', INT),
       ('Institutions in default / resolution', f'=SUM(Contagion!{CC["dflt"]}{LAST}:{CC["dflt"]}{LAST + NB - 1})', INT),
       ('Capital shortfall to MDA, all banks ($bn)', f'=SUMPRODUCT((K{R0}:K{rt - 1}<0)*-K{R0}:K{rt - 1})', NUM),
       ('Liquidity shortfall, all banks ($bn)', f'=SUM(O{R0}:O{rt - 1})', NUM),
       ('SYSTEMIC (>=3 G-SIBs below MDA or any G-SIB in default)', f'=IF(OR(B{rt + 6}>=3,SUMPRODUCT(Contagion!{CC["dflt"]}{LAST}:{CC["dflt"]}{LAST + NB - 1},Inputs_Banks!D6:D29)>=1),"YES","no")', None),
       ('Total forced sales, all sellers ($bn)', f'=SUM(Contagion!{SK[CLK[0]]}{LAST + NB}:{SK[CLK[-1]]}{LAST + NB})', NUM),
       ('BDCs losing IG / below 150% coverage (standalone)', '=BDC!C44&" / "&BDC!C45', None),
       ('Generic private-credit pool value, final round (hold)', f'=Contagion!{LSYS("Vh_g")}', PCT),
       ('Pool 3-yr PD, generic / software (final round)', f'=TEXT(Contagion!{LSYS("PDg")},"0.0%")&" / "&TEXT(Contagion!{LSYS("PDs")},"0.0%")', None),
       ('PANIC INTENSITY S, final round (0-1)', f'=Contagion!{LSYS("S")}', PCT),
       ('Panic path, rounds 1..' + str(ROUNDS), '=' + '&" > "&'.join(f'TEXT(Contagion!{sysref(k, "S").replace("$", "")},"0%")' for k in range(1, ROUNDS + 1)), None)]
put(rr, f'A{rt + 2}', 'SYSTEM', F_B, fill=FILL_SUB)
for k, (lab, f, fmt) in enumerate(SYS):
    put(rr, f'A{rt + 3 + k}', lab, F_N); put(rr, f'B{rt + 3 + k}', f, F_CALC, fmt, bold=True)
SYSROW = rt + 3
put(rr, f'D{rt + 2}', 'Market discount by asset class (final round)', F_B, fill=FILL_SUB)
for j, k in enumerate(CLK):
    put(rr, f'D{rt + 3 + j}', k, F_N); put(rr, f'E{rt + 3 + j}', f'=Contagion!{SK[k]}{LAST + NB + 1}', F_LINK, PCT)
    put(rr, f'F{rt + 3 + j}', f'=Contagion!{SK[k]}{LAST + NB}', F_LINK, NUM)
put(rr, f'F{rt + 2}', 'Sold ($bn)', F_B)
put(rr, f'H{rt + 2}', 'Standalone loss by module (all banks, $bn)', F_B, fill=FILL_SUB)
for k, (col, lab) in enumerate([('F', 'M1 back-leverage'), ('G', 'M2 fund finance'), ('H', 'M3 ABF / SE'), ('I', 'M4 insurers'), ('J', 'M5 AI / GPU'),
                                ('K', 'M6 trading / HFS'), ('L', 'M7 CRE'), ('O', 'M8 rates'), ('P', 'M9 SRT'), ('Q', 'M10 TRS'), ('R', 'M11 prime')]):
    put(rr, f'H{rt + 3 + k}', lab, F_N); put(rr, f'I{rt + 3 + k}', f'=Modules!{col}{R0 + NB}', F_LINK, NUM)
rr.freeze_panes = 'C6'; widths(rr, {'A': 46, 'B': 17, **{CLT(k): 12 for k in range(3, 22)}, 'L': 15})
rr.column_dimensions['A'].width = 9

# ================================================================ Dashboard
d = ws_dash
title(d, 'Private credit, AI-SPV and repo contagion stress model - 24 banks', f'As of 19 Oct 2026. Pick a scenario in C4 (or edit the Custom column on Scenarios). USD bn.')
put(d, 'E4', '<- choose: ' + ', '.join(SCEN), F_NOTE)
put(d, 'B6', 'SYSTEM', F_B, fill=FILL_SUB)
for k, (lab, f, fmt) in enumerate(SYS):
    put(d, f'B{7 + k}', lab, F_N); put(d, f'F{7 + k}', f'=Results!B{SYSROW + k}', F_LINK, fmt, bold=True)
put(d, 'H6', 'MONTE CARLO, 3-yr horizon: fat tails + panic, conditioned on today (see MC_Summary, Fat_Tails)', F_B, fill=FILL_SUB)
DT = 10 + len(SYS)   # per-bank table header row
DH = ['Id', 'Institution', 'CET1 now', 'Req.', 'After standalone', 'Final', 'Status', 'Standalone loss', 'Final loss', 'Liquidity shortfall', 'Notches']
hdr(d, DT, 2, DH)
for i, bid in enumerate(IDS):
    r = DT + 1 + i; s = R0 + i
    for k, (col, src, fmt) in enumerate([('B', 'A', None), ('C', 'B', None), ('D', 'D', PCT), ('E', 'E', PCT), ('F', 'G', PCT), ('G', 'I', PCT), ('H', 'L', None),
                                         ('I', 'F', NUM), ('J', 'H', NUM), ('K', 'O', NUM), ('L', 'M', INT)]):
        put(d, f'{col}{r}', f'=Results!{src}{s}', F_LINK, fmt)
ch = BarChart(); ch.type = 'col'; ch.title = 'CET1 ratio: now, after standalone, after contagion vs requirement'; ch.y_axis.title = 'CET1 / RWA'
ch.y_axis.numFmt = '0%'; ch.height = 9; ch.width = 26
cats = Reference(d, min_col=2, min_row=DT + 1, max_row=DT + NB)
for col in (4, 6, 7, 5):
    ch.add_data(Reference(d, min_col=col, min_row=DT, max_row=DT + NB), titles_from_data=True)
ch.set_categories(cats); d.add_chart(ch, f'N{DT}')
widths(d, {'A': 2, 'B': 14, 'C': 20, **{CLT(k): 11 for k in range(4, 13)}, 'H': 15})

# ================================================================ Checks
ck = ws_ck
title(ck, 'Model checks', 'All should read OK after recalculation.')
hdr(ck, 4, 1, ['Check', 'Value', 'Tolerance', 'Result'])
CHK = [
 ('Network: creditor totals proportional to IFS assets (sum of abs share diffs)', '=SUMPRODUCT(ABS(Network!AD6:AD29/SUM(Network!AD6:AD29)-Inputs_Banks!AY6:AY29/SUM(Inputs_Banks!AY6:AY29)))', 0.000001),
 ('Named-BDC facility commitments attributed to the 24 banks ($bn, info; total $118bn incl. other lenders)', '=SUM(Inputs_Banks!X6:X29)', None),
 ('AI holds attributed to the 24 banks ($bn, info; role-based estimates)', f'=SUM(AI_Deals!{AIB[IDS[0]]}{AR1 + 2}:{AIB[IDS[-1]]}{AR1 + 2})', None),
 ('Credit pool weights sum to 100%', '=SUM(CreditEngine!B6:B10)-1', 0.000001),
 ('Holdings allocation weights sum to 1 per bank with saleable assets', '=SUMPRODUCT((Holdings!P6:P29>0)*1)-SUM(Holdings!Q6:AC29)', 0.000001),
 ('Excel vs Python engine: sum of |CET1 ratio final| differences, active scenario', f'=SUMPRODUCT(ABS(Results!I6:I29-INDEX(PyCheck!C6:{CLT(2 + NSC)}29,0,MATCH(sel_scen,PyCheck!C5:{CLT(2 + NSC)}5,0))))', 0.0001),
 ('Excel vs Python engine: sum of |standalone loss| differences, active scenario ($bn)', f'=SUMPRODUCT(ABS(Results!F6:F29-INDEX(PyCheck!{CLT(4 + NSC)}6:{CLT(3 + 2 * NSC)}29,0,MATCH(sel_scen,PyCheck!{CLT(4 + NSC)}5:{CLT(3 + 2 * NSC)}5,0))))', 0.001),
]
for k, (lab, f, tol) in enumerate(CHK):
    r = 5 + k
    put(ck, f'A{r}', lab, F_N); put(ck, f'B{r}', f, F_CALC, NUM3)
    if tol is not None:
        put(ck, f'C{r}', tol, F_IN, NUM3)
        put(ck, f'D{r}', f'=IF(ABS(B{r})<=C{r},"OK","CHECK")', F_CALC)
    else:
        put(ck, f'D{r}', 'info', F_NOTE)
widths(ck, {'A': 80, 'B': 14, 'C': 10, 'D': 10})

# ================================================================ Sources
title(ws_src, 'Sources and estimate flags for every bank input', 'EST = estimate / proxy.')
hdr(ws_src, 4, 1, ['Bank', 'Field', 'Value', 'Estimate?', 'Source / basis'])
r = 5
for bid in IDS:
    for key, h, fmt, kind in FIELDS:
        if kind != 'in' or key in ('id', 'name', 'ccy'): continue
        if key.startswith('dg') and key[2:].isdigit():
            if key != 'dg1': continue
            v = B[bid]['dg']; s = SRC[bid].get('dg', ''); key = 'dg0..dg6'; v = ', '.join(f'{x:.2f}' for x in v)
        else:
            v = B[bid].get(key); s = SRC[bid].get(key, '')
        put(ws_src, f'A{r}', bid, F_N); put(ws_src, f'B{r}', key, F_N); put(ws_src, f'C{r}', v, F_N, NUM2 if isinstance(v, float) else None)
        put(ws_src, f'D{r}', 'EST' if str(s).startswith('EST') else '', F_N); put(ws_src, f'E{r}', s, F_NOTE)
        r += 1
widths(ws_src, {'A': 8, 'B': 14, 'C': 12, 'D': 8, 'E': 140})


# ================================================================ Dashboard MC links + README + Method
for k in range(5):
    put(d, f'H{7 + k}', f'=MC_Summary!A{5 + k}', F_LINK); put(d, f'L{7 + k}', f'=MC_Summary!B{5 + k}', F_LINK, PCT2, bold=True)
    put(d, f'M{7 + k}', f'=MC_Summary!C{5 + k}', F_LINK, PCT2, bold=True)
put(d, 'L6', 'Backstop ON', F_B); put(d, 'M6', 'Backstop OFF', F_B)
put(d, f'B{DT - 2}', 'Legend: blue = input, black = formula, green = link to another sheet, orange fill = estimate / proxy, yellow = choose / edit. USD bn. Ratios = CET1 / stressed RWA.', F_NOTE)

README = [
 ('Private credit, AI-SPV and repo contagion stress model', 'T'),
 ('Built for the Proteo Markets post The Six-Point Cliff. 24 institutions (13 US, 10 non-US, Jefferies). USD bn. Inputs as of 19 Oct 2026: CET1 and RWA of the 12 US banks that had reported at 30-Sep-2026, other balance-sheet items at 30-Jun-2026 unless noted; listed BDC P/NAV at 19-Oct-2026 prices.', ''),
 ('What it does', 'H'),
 ('1. Models each risk on its own (11 modules, Modules sheet), per bank, from filings: back-leverage to private-credit intermediaries with a look-through to the junk loans they hold (M1, BDC + BDC_EAD + CreditEngine), fund finance (M2), structured-entity / ABF lending (M3), PE-owned insurers (M4), AI / GPU / data-centre SPVs with chip obsolescence (M5, AI_Deals), trading and HFS marks (M6), CRE (M7), rates incl. forced HTM sales (M8), loss of SRT relief (M9), written sub-IG TRS (M10), prime / margin gap risk (M11).', ''),
 ('2. Connects banks through the repo and funding markets (Contagion sheet, 8 rounds): capital loss -> rating notches -> contractual triggers, deposit / wholesale / MMF CP run-off, repo haircut add-ons and non-rollover of inventory repo -> liquidity shortfall -> forced asset sales; MMF withdrawal of private-collateral repo -> matched-book clients forced to sell; BDC / private-credit funds and insurers sell into the same markets -> price impact by asset class -> re-marks of every bank\'s holdings and of private-credit pools behind back-leverage -> interbank losses when a bank defaults (max-entropy network).', ''),
 ('2b. Panic / information contagion: every round the street reads public news (BDC coverage breaches, private-credit price discount, G-SIB downgrades and MDA breaches, any failure) and sets a panic intensity S (0-1). S pushes the credit factor down (credit crunch), widens spreads, moves private-credit marks to market, makes funds sell and redeem, triggers runs on the weakest-ranked banks and in wholesale / CP / repo funding, and applies a common panic discount to every risky asset class at once (correlations -> 1). Flight-to-quality deposits go to the strongest half.', ''),
 ('3. Rerating tests: rating migration of the underlying loans (S&P average vs Moody\'s 2009 matrices) cuts borrowing bases and forces BDC sales; BDCs losing IG draw their bank revolvers in full; bank downgrades drive runs.', ''),
 ('4. Monte Carlo (10,000 joint draws, Student-t fat tails with a crisis regime in which correlations go to 0.95, panic on, conditioned on today), probability ladder and trigger-conditional probabilities (Fat_Tails), reverse stress and an each-module-alone grid, computed by engine.py (Python mirror of these formulas) and written to MC_Summary, MC_Distribution, Reverse_Stress and Standalone_Grid as values. Checks proves the Excel formulas reproduce the Python engine for the active scenario.', ''),
 ('How to use', 'H'),
 ('Dashboard!C4: pick a scenario. Scenarios sheet: edit the yellow Custom column (or any blue value); sw_M1..sw_M11 switch modules off; fs_on / ib_on / liq_on switch contagion channels off. Every bank input is on Inputs_Banks / Holdings / BDC / BDC_EAD / AI_Deals with its source on Sources.', ''),
 ('To refresh Monte Carlo / reverse stress after changing inputs: save in Excel, then run  python engine.py Private_Credit_Contagion_Model.xlsx  (prints all scenarios)  or  python post.py <file>  (rewrites the value sheets). post.py needs LibreOffice for its recalculation step.', ''),
 ('Sheet map', 'H'),
 ('Dashboard - selector, system KPIs, per-bank table, chart | Scenarios - all levers by scenario, active column | Globals - constants | Inputs_Banks - 50+ fields per bank | Holdings - 13 asset classes + price-impact parameters | BDC - 34 BDC look-through | BDC_EAD - bank x BDC facility exposure | AI_Deals - 39 AI / GPU deals x bank holds | CreditEngine - Vasicek pool, migration, fund finance | Modules - standalone losses | Contagion - 8 rounds incl. panic intensity (column CD) | Network - interbank matrix | Results - final per bank + system | Standalone_Grid, Reverse_Stress, MC_Summary, MC_Distribution, Fat_Tails, PyCheck - Python outputs | Checks | Sources | Method.', ''),
 ('Most important caveats', 'H'),
 ('Bank-level private-credit, AI and BDC facility holdings are partly estimates (orange). Call-report business-credit-intermediary (BCI) loans are treated as back-leverage on junk pools: conservative for banks whose book is mostly IG fund lending (State Street in particular). BofA\'s $49.9bn written sub-IG TRS is treated as financing with an 80% advance (interpretation unresolved). Price-impact coefficients for illiquid credit, run-off rates and the Monte Carlo lever mappings are judgment, documented on Scenarios / Holdings / MC_Summary. No PPNR credit in named scenarios (instantaneous marks). Probabilities are model-conditional, not forecasts.', ''),
]
r = 1
for text, kind in README:
    c = ws_readme.cell(row=r, column=1, value=text)
    c.font = F_T if kind == 'T' else (Font(name=AR, size=11, bold=True, color='1F3864') if kind == 'H' else F_N)
    c.alignment = Alignment(wrap_text=True, vertical='top'); r += 1 if kind else 1
    if not kind: ws_readme.row_dimensions[r - 1].height = max(15, 15 * (len(text) // 150 + 1))
ws_readme.column_dimensions['A'].width = 160

METHOD = [
 ('Method and equations', 'T'),
 ('Credit pool (CreditEngine)', 'H'),
 ('Underlying loans: Fitch private-credit rating mix (B+ 7%, B 24%, B- 44%, CCC+ 9%, CCC 16%). 3-yr PD by rating from S&P 1981-2024 cumulative table, plus a hidden-default add-on (Lincoln bad-PIK 6.2%). Conditional PD = N[(N^-1(PD) - sqrt(rho) z)/sqrt(1-rho)], rho = 0.20; software sub-pool PD x m_sw. Incremental loss = PD(z) x LGD(scenario) - PD(0) x LGD(base) because carrying values already embed base expected loss. Pool value (hold) = 1 - incremental loss - valuation gap - weight x (1 - market-implied mark). Pool value (liquidated) = hold x (1 - fire-sale discount on private-credit loans) - spread MTM - liquidation cost.', ''),
 ('Bank loss on senior advance a (SPV back-leverage, TRS, ABF warehouse): LR = phi x max(0, a - V_liq)/a + (1 - phi) x max(0, a - V_hold)/a, phi = share enforced now. BDC fund-level revolvers: advance = secured debt / assets of that BDC, so they lose only if the whole portfolio falls below the secured debt.', ''),
 ('BDC layer (BDC): market-implied mark = 1 - (1 - P/NAV) x E/A (listed; non-traded use listed average). Loses IG if asset coverage < 1.75x or NAV falls > 20% (FSK, TCPC already HY) -> revolvers 100% drawn. Forced sales = assets x [theta x max(borrowing-base deficiency incl. migration haircut, 150% coverage deficiency) + honoured redemptions x E/A x 0.7] x private-credit universe multiple.', ''),
 ('AI / GPU (AI_Deals)', 'H'),
 ('PD from lessee rating (S&P 3-yr) conditioned on an AI factor (rho 0.30). GPU loans: collateral(t) = (1 - annual decline)^t, t = 2 yrs; balance(t) = LTV x (1 - share repaid); LGD = max(0, 1 - 0.8 x collateral/balance) x (1 - cash-collateralised share). Data centres: LGD 35-40% + syndication mark-down + quoted marks (Jupiter 89-91). Anthropic $60bn: senior Broadcom-backstopped LGD 10%, junior 70%, plus syndication mark-down on the whole hold. RCFs drawn in stress.', ''),
 ('Other modules', 'H'),
 ('M2 fund finance: sub lines LP default x 30% LGD; NAV loans (15% of book, LTV 20%) lose only when NAV falls below LTV, tail funds fall 2.5x average. M3 ABF / SE residual: senior warehouses, 80% advance on pools with scenario loss. M4: insurer facilities + FA-backed repo x PD x 40%. M6: holdings x net fraction x fundamental price decline (+ Japanese strategic equities). M7: CRE x loss rate. M8: AFS MTM for banks with AOCI in CET1 (net duration 2.5 US / 1.0 non-US) + (HTM losses + opt-out AFS losses) x share sold. M9: lost SRT relief x RWA. M10: BofA written sub-IG TRS at 80% advance on the generic pool. M11: prime/margin x client default x max(0, 2 x shock - 20% margin).', ''),
 ('Contagion loop (Contagion, 8 rounds)', 'H'),
 ('Start of round: CET1 and ratio from previous round. Notches = min(3, floor((ratio now - ratio start)/step)) + 1 if below MDA + 2 if below 4.5%. Outflows = contractual downgrade triggers (cumulative by notch) + uninsured deposits x run-off(notches, MDA, minimum) + ST wholesale x non-rollover + prime-MMF CP/CD x non-rollover + non-govt repo x (haircut add-on + inventory non-rollover) + committed lines drawn - flight-to-quality inflow at unaffected banks. Shortfall = outflows - 85% HQLA - backstop share x CB-eligible capacity. Sales = shortfall + capital-driven deleveraging (to MDA + 0.5%, max 25% of saleable assets), allocated pro rata across saleable classes. HTM losses crystallise on (1 - backstop) x outflow/HQLA x 50%.', ''),
 ('Prices: discount_k = min(cap_k, dealer multiplier x lambda_k x total sold_k / 10,000), total sold = banks + non-banks (BDCs, private-credit funds, insurers) + matched-book clients. Re-marks: holdings x net fraction x discount; private-credit pools and ABF pools re-marked at the new prices. Default = CET1 < 0, below 4.5% minimum, or illiquid without backstop; creditor loss = LGD_ib x 35% in-sample x 40% unsecured x network exposure.', ''),
 ('Panic / information contagion (Contagion, system cells CC:CD of each round)', 'H'),
 ('News_r = news0 + w_cov x BDC asset share below 150% coverage (previous round) + w_notch x G-SIB notches / (3 x # G-SIBs) + w_mda x share of G-SIBs below MDA + w_def x (any failure) + w_fs x private-credit discount (previous round) / 30%. Panic S_r = S0 + (1 - S0) x [logistic((News - theta)/tau) - logistic(-theta/tau)] / [1 - logistic(-theta/tau)], so S = S0 with no news and S -> 1 as news rises. Calibration: Laeven-Valencia 151 crises 1970-2017; Cookson et al. (SVB 2023: Twitter exposure -> 4.3pp larger losses); Azizpour-Giesecke-Schwenkler (contagion drives default clustering); Longin-Solnik (correlations rise in bear markets); LLI 76.23 on 23-Mar-2020.', ''),
 ('Levers: credit factor z - zc x S; spreads ds + ds_pan x S; private-credit marks weight w_mkt + (1 - w_mkt) x S; fund deleveraging theta + (1 - theta) x S; redemptions red_rate + red_pan x S with requests x (1 + req_pan x S); deposit run-off + u_pan_all x S everywhere and + u_pan_weak x S at the n_weak banks with least capital headroom; wholesale / CP / repo pulls + w_pan, cp_pan, pull_pan x S; repo haircuts + dh_pan x S; dealer capacity x (1 + dm_pan x S); insurer sales + ins_pan x S; flight-to-quality recycling x (1 - rec_pan x S). Price discount_k = min(cap_k, dealer multiplier x (1 + dm_pan S) x lambda_k x sold_k / 10,000 + pmax_k x S^gamma).', ''),
 ('Monte Carlo and reverse stress', 'H'),
 ('Factors z (credit), z_AI = 0.5 z + 0.87 e1, z_liq = 0.6 z + 0.8 e2, rates dy = 1% x e3; all levers mapped from factors (MC_Summary lists the mapping). Fat tails: all four factors share one chi-square mixing variable (multivariate Student-t, nu = 4, unit variance) so extremes arrive together; with probability 10% a crisis regime sets the AI and liquidity loadings to 0.95 and adds 0.20 to S0; mean of z shifted -0.3 to condition on today (private-credit marks already under pressure). Probabilities are for a ~3-year horizon; Fat_Tails converts to 1-year and 3-month assuming a constant hazard. Reverse stress moves z = z_AI = z_liq together with no earnings credit and reports the first G-SIB MDA breach, the systemic point and the first failure, with the generic pool value at each point.', ''),
 ('Calibration sources', 'H'),
 ('FFIEC Call Reports RC-C Memo 10 and RC-L (30-Jun-2026); Q2-26 10-Qs, Pillar 3 and results releases (capital, liquidity, downgrade triggers, off-balance-sheet notes); OFR Bank Systemic Risk Monitor and MMF Monitor; NY Fed tri-party repo statistics; Gorton-Metrick; CGFS 36; Duarte-Eisenbach; Cont-Schaanning; S&P and Moody\'s default and transition studies; BDC credit agreements (EX-10); NAIC; GPU price data and CoreWeave / Oracle / Anthropic filings and deal reports; Laeven-Valencia; Cookson et al. (SVB 2023).', ''),
 ('Known limitations', 'H'),
 ('Single 3-yr horizon, no dynamic balance-sheet management, no PPNR in named scenarios, no core-book (non-NDFI) credit losses except CRE, no derivative counterparty or CCP channel, non-bank sellers are exogenous within the contagion loop, interbank matrix is max-entropy (true bilateral exposures are not public), Japanese / European figures mix reporting dates (Dec-25 to Jul-26).', ''),
]
r = 1
for text, kind in METHOD:
    c = ws_me.cell(row=r, column=1, value=text)
    c.font = F_T if kind == 'T' else (Font(name=AR, size=11, bold=True, color='1F3864') if kind == 'H' else F_N)
    c.alignment = Alignment(wrap_text=True, vertical='top')
    if not kind: ws_me.row_dimensions[r].height = max(15, 15 * (len(text) // 150 + 1))
    r += 1
ws_me.column_dimensions['A'].width = 160
for ws in wb.worksheets:
    ws.sheet_view.showGridLines = False if ws.title in ('README', 'Method', 'Dashboard') else True
wb.active = wb.sheetnames.index('Dashboard')

wb.save(OUT)
print('saved', OUT, 'last block row', LAST)
