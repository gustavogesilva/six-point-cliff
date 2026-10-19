"""post/post.md -> post/post.html with the images embedded (handy for pasting into Substack).

Usage (from the repo root):  python post/build.py
"""
import re, base64, html
from pathlib import Path
HERE = Path(__file__).resolve().parent
s = open(HERE / 'post.md').read()
CAP = {'fig1_loop.png': 'How a re-rating turns into a run', 'fig2_cliff.png': 'G-SIBs below their capital buffer as private-credit marks fall, with and without panic',
       'tab1_scenarios.png': 'Same shock, with and without panic', 'fig3_ladder.png': 'Probability of a G-SIB below the 4.5% minimum, built up step by step',
       'fig4_banks.png': 'Probability of falling below the 4.5% minimum, by bank', 'tab2_triggers.png': 'What would move the odds',
       'fig5_market.png': 'Fall from the 3-month high, 19 October 2026'}
def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    return re.sub(r'\*([^*]+)\*', r'<em>\1</em>', t)
out, lst = [], False
for line in s.split('\n'):
    if line.startswith('- '):
        if not lst: out.append('<ul>'); lst = True
        out.append(f'<li>{inline(line[2:])}</li>'); continue
    if lst: out.append('</ul>'); lst = False
    if not line.strip(): continue
    if line.startswith('# '): out.append(f'<h1>{inline(line[2:])}</h1>')
    elif line.startswith('## '): out.append(f'<h2>{inline(line[3:])}</h2>')
    elif line.strip() == '---': out.append('<hr>')
    elif line.startswith('!['):
        f = re.search(r'\(fig/([^)]+)\)', line).group(1)
        b64 = base64.b64encode(open(HERE / 'fig' / f, 'rb').read()).decode()
        out.append(f'<figure><img src="data:image/png;base64,{b64}" alt="{html.escape(CAP[f])}" width="728"><figcaption>{html.escape(CAP[f])}</figcaption></figure>')
    elif line.startswith('*') and line.endswith('*') and not line.startswith('**'): out.append(f'<p class="sub">{inline(line[1:-1])}</p>')
    else: out.append(f'<p>{inline(line)}</p>')
if lst: out.append('</ul>')
css = ('body{max-width:728px;margin:40px auto;padding:0 16px;font-family:Georgia,serif;font-size:19px;line-height:1.6;color:#1B2433}'
       'h1{font-family:Inter,Helvetica,sans-serif;font-size:36px;line-height:1.15;color:#0F2747;margin-bottom:8px}'
       'h2{font-family:Inter,Helvetica,sans-serif;font-size:24px;color:#0F2747;margin-top:40px}'
       'p.sub{font-size:20px;color:#5B6577;margin-top:0}figure{margin:28px 0}img{width:100%;height:auto}'
       'figcaption{font-size:14px;color:#5B6577;text-align:center;margin-top:6px}a{color:#2F6FED}hr{border:0;border-top:1px solid #D9DFE8;margin:32px 0}')
open(HERE / 'post.html', 'w').write('<!doctype html><html><head><meta charset="utf-8"><title>The Six-Point Cliff</title><style>' + css + '</style></head><body>' + '\n'.join(out) + '</body></html>')
