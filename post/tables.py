"""Table images for the post: HTML rendered with Playwright at 728 CSS px x 2 = 1456 px.

Usage (from the repo root):  python post/tables.py      (needs: pip install playwright && playwright install chromium)
"""
import json, asyncio
from pathlib import Path
from playwright.async_api import async_playwright
ROOT = Path(__file__).resolve().parents[1]
R = json.load(open(ROOT / 'data' / 'results' / 'post_runs.json'))
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
body{margin:0;background:#fff;font-family:Inter,Helvetica,Arial,sans-serif;color:#1B2433;width:728px}
.wrap{padding:22px 22px 14px}
.top{display:flex;justify-content:space-between;align-items:baseline}
h1{font-size:19px;font-weight:700;color:#0F2747;margin:0}
.brand{font-size:10px;font-weight:700;color:#0F2747;letter-spacing:.02em}
.sub{font-size:13px;color:#5B6577;margin:6px 0 14px}
table{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}
th{font-size:11px;font-weight:600;color:#5B6577;text-align:right;padding:6px 8px;border-bottom:1.5px solid #0F2747;vertical-align:bottom;line-height:1.3}
th:first-child,td:first-child{text-align:left}
td{padding:8px 8px;border-bottom:1px solid #E7EBF1;text-align:right;vertical-align:top;line-height:1.35}
td small{display:block;color:#5B6577;font-size:11px;margin-top:2px}
tr.hi td{background:#EEF3FD}
td.b{font-weight:700;color:#0F2747}
.src{font-size:10px;color:#5B6577;margin-top:10px}
"""
def page(title, sub, head, rows, src):
    th = ''.join(f'<th>{h}</th>' for h in head)
    tr = ''.join(f'<tr class="{c}">' + ''.join(f'<td class="{k}">{v}</td>' for v, k in cells) + '</tr>' for c, cells in rows)
    return f'<html><head><style>{CSS}</style></head><body><div class="wrap"><div class="top"><h1>{title}</h1><span class="brand">PROTEO MARKETS</span></div><div class="sub">{sub}</div><table><tr>{th}</tr>{tr}</table><div class="src">{src}</div></div></body></html>'

def scen():
    S = R['scen']
    spec = [('Baseline', 'Calm baseline', "today's conditions", 'none'),
            ('Rerating cascade', 'Loan re-rating', 'downgrades 1.5x the 2009 pace, fast bank downgrades', 'none'),
            ('Credit 2009', '2009-style credit cycle', 'B- defaults 45% over 3 years, spreads +600bp', 'State Street below 4.5%; PNC also fails'),
            ('Repo run', 'Repo run, no central bank', 'haircuts +18 points, money funds pull 75%', 'State Street below 4.5%; Wells Fargo runs out of cash'),
            ('Rates shock', 'Rates shock', '+200bp, a quarter of held-to-maturity bonds sold', 'State Street below 4.5%'),
            ('2008-combined', '2008, all at once', 'all of the above together', '11 G-SIBs below 4.5%, 14 failures')]
    rows = []
    for k, name, what, fail in spec:
        a, b = S[f'{k}|0'], S[f'{k}|1']
        rows.append(('hi' if k == 'Rerating cascade' else '', [(f'{name}<small>{what}</small>', ''), (f"{a['fin']:,.0f}", ''), (f"{b['fin']:,.0f}", 'b'),
                                                           (f"{a['mda']} &rarr; {b['mda']}", ''), (fail, '')]))
    return page('Same shock, with and without panic', 'Losses across 24 banks after all contagion rounds, and G-SIBs pushed below their capital buffer',
                ['Scenario', 'Losses, no panic<br>($bn)', 'Losses, with panic<br>($bn)', 'G-SIBs below<br>buffer', 'Below the 4.5% minimum<br>or failed (with panic)'],
                rows, 'Source: Proteo Markets contagion model; model scenarios, not forecasts. Bank capital at 30 September 2026, market prices at 19 October 2026. State Street result assumes its $22bn call-report line is junk-pool lending.')

def trig():
    T = R['trig']; L = R['ladder']
    yr = lambda p: 1 - (1 - p) ** (1 / 3)
    spec = [(None, 'Nothing new (today)'), ('T1', 'The biggest semi-liquid funds break their gates'), ('T2', 'Private-credit marks cut by 10 points'),
            ('T3', 'Non-government repo seizes up'), ('T4', 'A PE-owned insurer fails'), ('T5', 'A G-SIB fails for a reason outside our model'),
            ('T6', 'Gates, marks and repo all at once')]
    rows = []
    for k, name in spec:
        on = L['1|L4'] if k is None else T[f'1|{k}']; off = L['0|L4'] if k is None else T[f'0|{k}']
        rows.append(('hi' if k in ('T2', 'T6') else '', [(name, ''), (f"{on['gmin'] * 100:.1f}%", 'b'), (f"{yr(on['gmin']) * 100:.1f}%", ''),
                                                       (f"{off['gmin'] * 100:.1f}%", ''), (f"{on['sys'] * 100:.0f}%", '')]))
    return page('What would move the odds', 'Probability that at least one G-SIB falls below the 4.5% CET1 minimum, given that you see the event',
                ['If you see this', 'Within ~3 years', 'Per year', 'Without central-<br>bank lending (~3 yrs)', 'Systemic event<br>(~3 yrs)'],
                rows, 'Source: Proteo Markets contagion model, 20,000 simulations per row. Systemic = three G-SIBs below their buffer or any G-SIB failing.')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 728, 'height': 400}, device_scale_factor=2)
        for name, html in [('tab1_scenarios.png', scen()), ('tab2_triggers.png', trig())]:
            await pg.set_content(html); await pg.wait_for_timeout(800)
            el = await pg.query_selector('.wrap'); await el.screenshot(path=str(ROOT / 'post' / 'fig' / name))
        await b.close()
asyncio.run(main())
