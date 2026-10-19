"""Charts for the post. 1456 px wide PNGs (Substack shows them at 728 px).

Usage (from the repo root):  python post/charts.py loop cliff ladder banks market
Reads data/results/post_runs.json (src/post_runs.py) and, for the market chart, data/prices/ (post/fetch_prices.py).
Needs the Inter font; falls back to the matplotlib default if it is missing.
"""
import json, datetime, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager as fm

for f in fm.findSystemFonts():
    if 'inter' in Path(f).name.lower():
        fm.fontManager.addfont(f)
plt.rcParams.update({'font.family': 'Inter', 'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.edgecolor': '#D5DAE3', 'axes.linewidth': 0.6, 'xtick.color': '#5B6577', 'ytick.color': '#5B6577',
                     'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5, 'axes.labelcolor': '#5B6577', 'axes.labelsize': 8.5,
                     'figure.facecolor': 'white', 'axes.facecolor': 'white', 'savefig.facecolor': 'white'})
NAVY, BLUE, GREY, LGREY, INK, MUTED, GRID, RED = '#0F2747', '#2F6FED', '#A9B4C6', '#D9DFE8', '#1B2433', '#5B6577', '#E7EBF1', '#C2413A'
W, DPI = 7.28, 200          # 7.28 in x 200 dpi = 1456 px
ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / 'data' / 'prices'
AS_OF = datetime.date(2026, 10, 19)   # the post's price date (the published chart used 19 Oct intraday prices)
OUT = str(ROOT / 'post' / 'fig') + '/'


def frame(h, title, sub, source, top=0.80, bottom=0.12, left=0.06, right=0.97):
    fig = plt.figure(figsize=(W, h), dpi=DPI)
    fig.text(left, 1 - 0.30 / h, title, fontsize=13.5, fontweight='bold', color=NAVY, va='top')
    fig.text(left, 1 - 0.62 / h, sub, fontsize=9.5, color=MUTED, va='top')
    fig.text(left, 0.16 / h, source, fontsize=7.2, color=MUTED, va='bottom')
    fig.text(right, 1 - 0.36 / h, 'PROTEO MARKETS', fontsize=7.2, color=NAVY, fontweight='bold', va='top', ha='right')
    return fig


def save(fig, name):
    fig.savefig(OUT + name, dpi=DPI)
    plt.close(fig)


# ------------------------------------------------------------------ market check: % below 3-month high
def market():
    import matplotlib.transforms as mt
    def series(t):
        d = json.load(open(PRICES / f'{t}.json'))['chart']['result'][0]
        xs = [(datetime.datetime.fromtimestamp(a, datetime.timezone.utc).date(), b) for a, b in zip(d['timestamp'], d['indicators']['quote'][0]['close']) if b is not None]
        xs = [(a, b) for a, b in xs if a <= AS_OF]
        w = [b for a, b in xs if a >= AS_OF - datetime.timedelta(days=92)]
        return xs[-1][1] / max(w) - 1
    groups = [('Private-credit managers and BDCs', BLUE, [('Blue Owl', 'OWL'), ('Blackstone', 'BX'), ('KKR', 'KKR'), ('Ares', 'ARES'), ('Apollo', 'APO'),
                                                          ('FS KKR Capital (BDC)', 'FSK'), ('Blue Owl Capital Corp (BDC)', 'OBDC'), ('BDC index (BIZD)', 'BIZD')]),
              ('AI borrower', NAVY, [('CoreWeave', 'CRWV')]),
              ('Banks', GREY, [('State Street', 'STT'), ('Regional banks (KRE)', 'KRE'), ('JPMorgan', 'JPM')]),
              ('Credit and stocks', LGREY, [('Leveraged loans (BKLN)', 'BKLN'), ('High-yield bonds (HYG)', 'HYG'), ('S&P 500', '^GSPC')])]
    fig = frame(6.3, 'Shares down 13 to 42%, loans down 2%', 'Fall from the 3-month high, as of 19 October 2026',
                'Source: Yahoo Finance daily prices, 19 Jul to 19 Oct 2026 (19 Oct intraday).')
    ax = fig.add_axes([0.36, 0.10, 0.58, 0.76])
    tr = mt.blended_transform_factory(ax.transAxes, ax.transData)
    y = 0; ticks = []
    for gname, colr, items in groups:
        ax.text(-0.015, y, gname.upper(), transform=tr, ha='right', va='center', fontsize=7, color=MUTED, fontweight='bold')
        y -= 1
        for lab, t in items:
            v = series(t) * 100
            ax.barh(y, v, height=0.64, color=colr, zorder=3)
            ax.text(v - 0.8, y, f'{v:.0f}%', va='center', ha='right', fontsize=8.5, color=INK)
            ax.text(-0.015, y, lab, transform=tr, ha='right', va='center', fontsize=8.8, color=INK)
            y -= 1
        y -= 0.4
    ax.set_xlim(-50, 0.8); ax.set_ylim(y + 0.6, 0.6)
    ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.axvline(0, color=MUTED, lw=0.8, zorder=4)
    ax.set_xticks([-40, -30, -20, -10, 0]); ax.set_xticklabels(['-40%', '-30%', '-20%', '-10%', '0'])
    ax.grid(axis='x', color=GRID, lw=0.6, zorder=0)
    _v = json.load(open(PRICES / '^VIX.json'))['chart']['result'][0]
    vix = [b for a, b in zip(_v['timestamp'], _v['indicators']['quote'][0]['close']) if b is not None and datetime.datetime.fromtimestamp(a, datetime.timezone.utc).date() <= AS_OF][-1]
    ax.text(-49, y + 1.9, f'VIX {vix:.1f}\n3-month range 14 to 21', fontsize=8, color=INK, va='center', ha='left', linespacing=1.4,
            bbox=dict(boxstyle='round,pad=0.45', fc='white', ec=LGREY, lw=0.6))
    save(fig, 'fig5_market.png')


# ------------------------------------------------------------------ the loop
def loop():
    fig = frame(5.9, 'How a re-rating turns into a run',
                'Each turn of the loop is one round of news',
                'Source: Proteo Markets contagion model.')
    ax = fig.add_axes([0.02, 0.07, 0.96, 0.79]); ax.set_xlim(0, 10); ax.set_ylim(0, 6.3); ax.axis('off')
    bw, bh = 3.2, 1.0
    nodes = [(5.0, 5.65, 'Loans get re-rated', 'software and AI borrowers\nmarked down'),
             (8.2, 4.25, 'Funds hit their limits', 'borrowing bases shrink,\nredemptions pile up'),
             (8.2, 1.95, 'Forced selling', 'funds, insurers and\nrepo clients sell'),
             (5.0, 0.6, 'Everything falls together', 'loans, high yield, CLOs\nand stocks at once'),
             (1.8, 1.95, 'Bank capital falls', 'marks, downgrades,\nbuffers breached'),
             (1.8, 4.25, 'Funding pulls back', 'depositors, money funds\nand repo lenders')]
    for x, yv, t, b in nodes:
        ax.add_patch(FancyBboxPatch((x - bw / 2, yv - bh / 2), bw, bh, boxstyle='round,pad=0.02,rounding_size=0.12', fc='white', ec=NAVY, lw=1.0))
        ax.text(x, yv + 0.22, t, ha='center', va='center', fontsize=9.6, fontweight='bold', color=NAVY)
        ax.text(x, yv - 0.17, b, ha='center', va='center', fontsize=7.6, color=MUTED, linespacing=1.25)
    conns = [((6.62, 5.55), (7.6, 4.77)), ((8.2, 3.73), (8.2, 2.47)), ((7.6, 1.43), (6.62, 0.7)),
             ((3.38, 0.7), (2.4, 1.43)), ((1.8, 2.47), (1.8, 3.73)), ((2.4, 4.77), (3.38, 5.55))]
    for (a, b) in conns:
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=12, color=BLUE, lw=1.7, connectionstyle='arc3,rad=-0.2'))
    ax.add_patch(FancyBboxPatch((3.65, 2.3), 2.7, 1.7, boxstyle='round,pad=0.02,rounding_size=0.2', fc='#EEF3FD', ec=BLUE, lw=1.0))
    ax.text(5.0, 3.68, 'Headlines', ha='center', va='center', fontsize=10, fontweight='bold', color=BLUE)
    ax.text(5.0, 2.98, 'every breach, downgrade\nand gate raises the panic\nlevel, and the panic level\npushes every arrow harder', ha='center', va='center', fontsize=7.6, color=INK, linespacing=1.3)
    save(fig, 'fig1_loop.png')



RUN = ROOT / 'data' / 'results' / 'post_runs.json'
MARK_TODAY = 88.4      # asset-weighted market-implied mark from listed BDC P/NAV, 19 Oct 2026
NAMES = {'STT': 'State Street', 'PNC': 'PNC', 'DBK': 'Deutsche Bank', 'WFC': 'Wells Fargo', 'BARC': 'Barclays', 'TFC': 'Truist', 'MUFG': 'MUFG',
         'GS': 'Goldman Sachs', 'BK': 'BNY', 'MS': 'Morgan Stanley', 'BAC': 'Bank of America', 'C': 'Citigroup', 'JPM': 'JPMorgan'}


def cliff():
    r = json.load(open(RUN))['rev']
    fig = frame(5.0, 'The cliff', 'G-SIBs below their capital buffer as private-credit loan marks fall (central bank lending as normal)',
                'Source: Proteo Markets contagion model; 18 G-SIBs, capital at 30 September 2026.')
    ax = fig.add_axes([0.08, 0.18, 0.88, 0.63])
    for key, colr, lab, lw in [('0|1', GREY, 'Without panic', 1.8), ('1|1', BLUE, 'With panic', 2.2)]:
        m = np.array(r[key]['mark']) * 100; n = np.array(r[key]['mda'])
        k = m >= 55
        ax.plot(m[k], n[k], color=colr, lw=lw, drawstyle='steps-mid', solid_capstyle='round', zorder=3)
        ax.text(55.4, n[k][-1] + 0.35, lab, color=INK, fontsize=8.8, ha='right', va='bottom', fontweight='bold' if key == '1|1' else 'normal')
    ax.set_xlim(100, 55); ax.set_ylim(0, 18.5)
    ax.axvline(MARK_TODAY, color=NAVY, lw=1.0, zorder=2)
    ax.text(MARK_TODAY - 0.5, 17.6, f'Today: {MARK_TODAY:.0f}\n(implied by listed\nBDC prices)', fontsize=7.8, color=INK, va='top', ha='left', linespacing=1.3)
    ax.axvline(60.3, color=GREY, lw=0.9, zorder=2)
    ax.text(61.0, 1.0, '2008 low in\nloan prices: 60', fontsize=7.8, color=MUTED, va='bottom', ha='right', linespacing=1.3)
    m1 = np.array(r['1|1']['mark']) * 100; n1 = np.array(r['1|1']['mda']); L1 = np.array(r['1|1']['loss'])
    j = int(np.argmax(n1 >= 3))
    ax.annotate(f'Between marks of {m1[j - 1]:.0f} and {m1[j]:.0f}\nthe count jumps from {n1[j - 1]} to {n1[j]}\nand losses from \\${L1[j - 1]:.0f}bn to \\${L1[j]:.0f}bn',
                xy=(m1[j] - 0.3, n1[j] - 0.6), xytext=(78.6, 10.7), fontsize=7.8, color=INK, ha='left', va='center', linespacing=1.35,
                arrowprops=dict(arrowstyle='-', color=MUTED, lw=0.7, connectionstyle='arc3,rad=0.15'))
    ax.set_xlabel('Private-credit loan mark: value of a typical loan book, % of carrying value'); ax.set_yticks([0, 3, 6, 9, 12, 15, 18])
    ax.grid(axis='y', color=GRID, lw=0.6, zorder=0)
    save(fig, 'fig2_cliff.png')


def ladder():
    L = json.load(open(RUN))['ladder']
    steps = [('L0', 'Normal distribution, no panic'), ('L1', '+ fat tails'), ('L2', '+ correlations jump in a crisis'),
             ('L3', '+ panic (the headline loop)'), ('L4', "+ today's conditions")]
    on = [L[f'1|{k}']['gmin'] * 100 for k, _ in steps]; off = [L[f'0|{k}']['gmin'] * 100 for k, _ in steps]
    fig = frame(4.6, 'Panic does the damage, fat tails barely move it',
                'Probability that at least one G-SIB falls below the 4.5% CET1 minimum within ~3 years',
                'Source: Proteo Markets contagion model, 20,000 simulations per step. Ticks: same step with no central-bank lending.')
    ax = fig.add_axes([0.37, 0.12, 0.58, 0.68])
    n = len(steps) + 1; ys = np.arange(n)[::-1]
    prev = 0
    for i, ((k, lab), v, vo) in enumerate(zip(steps, on, off)):
        y = ys[i]; a, b = (0, v) if i == 0 else (prev, v)
        colr = BLUE if k == 'L3' else (NAVY if i == 0 else GREY)
        ax.barh(y, b - a, left=a, height=0.56, color=colr, zorder=3)
        ax.plot([vo, vo], [y - 0.34, y + 0.34], color=INK, lw=1.4, zorder=4)
        txt = f'{v:.1f}%' if i == 0 else f'+{v - prev:.1f} pts'
        ax.text(max(v, vo) + 0.25, y, txt, va='center', fontsize=8.8, color=INK, fontweight='bold' if k == 'L3' else 'normal')
        ax.text(-0.3, y, lab, va='center', ha='right', fontsize=8.8, color=INK)
        if i: ax.plot([prev, prev], [y + 0.28, y + 1 - 0.28], color=MUTED, lw=0.6)
        prev = v
    y = ys[-1]
    ax.barh(y, on[-1], height=0.56, color=NAVY, zorder=3); ax.plot([off[-1]] * 2, [y - 0.34, y + 0.34], color=INK, lw=1.4, zorder=4)
    ax.plot([on[-1]] * 2, [y + 0.28, y + 1 - 0.28], color=MUTED, lw=0.6)
    yr = (1 - (1 - on[-1] / 100) ** (1 / 3)) * 100; yro = (1 - (1 - off[-1] / 100) ** (1 / 3)) * 100
    ax.text(off[-1] + 0.25, y, f'{on[-1]:.1f}%, about {yr:.1f}% a year', va='center', fontsize=8.8, color=INK, fontweight='bold')
    ax.text(-0.3, y, 'Today, all together', va='center', ha='right', fontsize=8.8, color=INK, fontweight='bold')
    ax.set_xlim(0, 16); ax.set_ylim(-0.6, n - 0.4); ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_xticks([0, 5, 10, 15]); ax.set_xticklabels(['0%', '5%', '10%', '15%']); ax.grid(axis='x', color=GRID, lw=0.6, zorder=0)
    save(fig, 'fig3_ladder.png')


def banks():
    L = json.load(open(RUN))['ladder']; on = L['1|L4']['bank_min']; off = L['0|L4']['bank_min']
    top = sorted(on.items(), key=lambda t: -t[1])[:8]
    fig = frame(4.6, 'One name sits in every failing simulation',
                'Probability of falling below the 4.5% CET1 minimum within ~3 years, by bank, under today\'s conditions',
                'Source: Proteo Markets contagion model, 20,000 simulations; scenario odds, not forecasts. Ticks: no central-bank lending.\nState Street assumes its \\$22bn call-report line is junk-pool lending (0.3% if treated as fund lending). PNC and Truist are not G-SIBs.')
    ax = fig.add_axes([0.25, 0.19, 0.70, 0.61])
    ys = np.arange(len(top))[::-1]
    for y, (b, v) in zip(ys, top):
        ax.barh(y, v * 100, height=0.6, color=BLUE if b == 'STT' else GREY, zorder=3)
        ax.plot([off[b] * 100] * 2, [y - 0.36, y + 0.36], color=INK, lw=1.4, zorder=4)
        ax.text(max(v, off[b]) * 100 + 0.2, y, f'{v * 100:.1f}%', va='center', fontsize=8.8, color=INK, fontweight='bold' if b == 'STT' else 'normal')
        ax.text(-0.2, y, NAMES[b], va='center', ha='right', fontsize=8.8, color=INK)
    ax.set_xlim(0, 12); ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_xticks([0, 4, 8, 12]); ax.set_xticklabels(['0%', '4%', '8%', '12%']); ax.grid(axis='x', color=GRID, lw=0.6, zorder=0)
    save(fig, 'fig4_banks.png')


if __name__ == '__main__':
    for fn in sys.argv[1:]:
        globals()[fn]()
