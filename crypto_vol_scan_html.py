import re, requests, math, statistics
from bs4 import BeautifulSoup

# 1) CoinGecko HTML to get Top coins list without API rate limit
cg_url = 'https://www.coingecko.com/en/coins'
html = requests.get(cg_url, headers={'user-agent':'openclaw-vol-scan/1.0'}, timeout=30).text
soup = BeautifulSoup(html, 'html.parser')

rows = []
# CoinGecko uses table rows with data-coin-id / data-coin-symbol in many versions
for tr in soup.select('table tbody tr'):
    sym = tr.get('data-coin-symbol') or tr.get('data-coin-symbols')
    coin_id = tr.get('data-coin-id')
    if not sym:
        # try to find symbol text (often in span.tw-hidden)
        sym_el = tr.select_one('td span.tw-hidden')
        sym = sym_el.get_text(strip=True) if sym_el else None
    if not sym:
        continue
    sym = sym.upper()
    # filter obvious stables & majors
    if sym in {'USDT','USDC','DAI','TUSD','FDUSD','BUSD','USDE','PYUSD','BTC','ETH'}:
        continue
    # name
    name_el = tr.select_one('a.tw-flex.tw-items-center.tw-text-gray-700')
    name = name_el.get_text(' ', strip=True) if name_el else sym

    # parse 1h/24h % if visible in HTML
    def parse_pct(td):
        if not td: return None
        txt = td.get_text(' ', strip=True)
        m = re.search(r'([-+]?\d+(?:\.\d+)?)\s*%', txt)
        return float(m.group(1)) if m else None

    tds = tr.find_all('td')
    # Heuristic column positions can change; search for % cells
    pcts = [parse_pct(td) for td in tds if '%' in td.get_text()]
    cg1h = pcts[0] if len(pcts)>0 else None
    cg24h = pcts[1] if len(pcts)>1 else None

    # market cap and volume may be present as numbers with $ and commas
    def parse_money(text):
        text=text.replace('\xa0',' ').strip()
        text=re.sub(r'[^0-9\.,]', '', text)
        if not text: return None
        # remove commas (assume US formatting)
        text=text.replace(',', '')
        try:
            return float(text)
        except:
            return None

    # try find Market Cap and Volume columns by looking for $ in cells
    monies=[td.get_text(' ',strip=True) for td in tds]
    money_vals=[parse_money(t) for t in monies]
    # pick last money as mcap usually, and a middle as volume
    mcap = next((v for v in reversed(money_vals) if v), None)
    vol = next((v for v in money_vals if v and mcap and v!=mcap), None)

    rows.append({'sym':sym,'name':name,'cg1h':cg1h,'cg24h':cg24h,'cg_vol':vol,'cg_mcap':mcap})
    if len(rows)>=120:
        break

# Keep top 100 alts
coins = rows[:100]

# 2) Binance 24hr tickers for volume/price moves
bn_url='https://api.binance.com/api/v3/ticker/24hr'
tickers=requests.get(bn_url, timeout=30).json()

bn_usdt={}
for t in tickers:
    s=t.get('symbol','')
    if not s.endswith('USDT'): continue
    base=s[:-4]
    if base.endswith(('UP','DOWN','BULL','BEAR')): continue
    qv=float(t.get('quoteVolume',0) or 0)
    if base not in bn_usdt or qv>float(bn_usdt[base].get('quoteVolume',0) or 0):
        bn_usdt[base]=t

merged=[]
for c in coins:
    bn=bn_usdt.get(c['sym'])
    if not bn: continue
    bn_ch24=float(bn.get('priceChangePercent') or 0)
    bn_qv=float(bn.get('quoteVolume') or 0)
    mcap=c.get('cg_mcap') or 0
    vol=c.get('cg_vol') or 0
    vol_mcap = (vol/mcap) if mcap else 0
    merged.append({**c,'bn24h':bn_ch24,'bn_qv':bn_qv,'vol_mcap':vol_mcap})

if not merged:
    print('NO_DATA')
    raise SystemExit(0)

# scoring
abs1=[abs(r['cg1h'] or 0) for r in merged]
abs24=[abs(r['cg24h'] or 0) for r in merged]
vm=[r['vol_mcap'] for r in merged]
qv=[math.log10(r['bn_qv']+1) for r in merged]

def z(x, arr):
    mu=statistics.mean(arr)
    sd=statistics.pstdev(arr) or 1
    return (x-mu)/sd

for r in merged:
    r['score_move']=max(z(abs(r['cg1h'] or 0),abs1), z(abs(r['cg24h'] or 0),abs24), z(abs(r['bn24h'] or 0), [abs(x) for x in [m['bn24h'] for m in merged]]))
    r['score_vol']=max(z(r['vol_mcap'],vm), z(math.log10(r['bn_qv']+1),qv))
    r['score']=r['score_move']*0.7 + r['score_vol']*0.5

cands=[r for r in merged if (r['cg1h'] is not None and abs(r['cg1h'])>=6) or abs(r['bn24h'])>=18 or r['score']>=2.0]

# Reversal risk
for r in merged:
    if r['cg1h'] is None or r['bn24h'] is None: continue
    if abs(r['cg1h'])>=4 and abs(r['bn24h'])>=12 and (r['cg1h']*r['bn24h']<0):
        r['flag_reversal']=True
        if r not in cands: cands.append(r)

cands=sorted(cands,key=lambda r:r['score'], reverse=True)[:10]

for r in cands:
    cg1h='n/a' if r['cg1h'] is None else f"{r['cg1h']:+.2f}%"
    cg24h='n/a' if r['cg24h'] is None else f"{r['cg24h']:+.2f}%"
    print(f"{r['sym']}: 1h(CG) {cg1h} | 24h(CG) {cg24h} | 24h(BN) {r['bn24h']:+.2f}% | BN qVol ${r['bn_qv']/1e6:.1f}M")
