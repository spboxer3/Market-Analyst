#!/usr/bin/env python3
import json,re
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

TZ=ZoneInfo('Asia/Taipei')
UA={'User-Agent':'market-analyst/1.0'}


def now_iso(): return datetime.now(TZ).isoformat()

def wjson(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')

def read_watchlist(p):
    if not p.exists(): return []
    out=[]
    for ln in p.read_text(encoding='utf-8').splitlines():
        if not ln.strip().startswith('|') or 'Ticker' in ln or '---' in ln: continue
        a=[x.strip() for x in ln.strip().strip('|').split('|')]
        if len(a)>=6 and a[0] and not a[0].startswith('<!--'):
            out.append({'ticker':a[0],'name':a[1],'sector':a[2],'priority':a[3].lower(),'notes':a[4],'added_date':a[5]})
    return out

def to_yh(s):
    s=s.strip().upper()
    if s.endswith('.TW') or s.endswith('.TWO'): return s
    return f'{s}.TW' if re.fullmatch(r'\d{4}',s) else None

def fnum(x,default=0.0):
    try: return float(str(x).replace(',','').replace('%','').strip())
    except: return default

def fetch_twse(base):
    err=None; links=[]
    for i in range(8):
        d=(base-timedelta(days=i)).strftime('%Y%m%d')
        u1=f'https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d}'
        u2=f'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={d}&type=ALLBUT0999&response=json'
        u3=f'https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate={d}&type=day&response=json'
        links=[u1,u2,u3]
        try:
            mi=requests.get(u1,timeout=20,headers=UA).json()
            idx=requests.get(u2,timeout=20,headers=UA).json()
            bfi=requests.get(u3,timeout=20,headers=UA).json()
            if mi.get('stat')!='OK' or idx.get('stat')!='OK' or bfi.get('stat')!='OK': continue
            rows=mi.get('data') or []
            if not rows: continue
            last=rows[-1]
            idxrows={r[0]:r for r in (idx.get('tables',[{}])[0].get('data') or [])}
            tx=idxrows.get('發行量加權股價指數')
            if not tx: continue
            up=down=0
            for r in (idx.get('tables',[{}, {}, {}, {}, {}, {}, {}, {}])[7].get('data') or []):
                k=str(r[0]);v=int(str(r[1]).split('(')[0].replace(',',''))
                if k.startswith('漲'): up=v
                if k.startswith('跌'): down=v
            turn=''
            for r in (idx.get('tables',[{}, {}, {}, {}, {}, {}, {}])[6].get('data') or []):
                if str(r[0]).startswith('3.成交金額'): turn=str(r[1]).replace(',','')
            fnet=inet=None
            for r in (bfi.get('data') or []):
                t=str(r[0]).strip()
                if t=='外資及陸資(不含外資自營商)': fnet=str(r[3]).replace(',','')
                if t=='合計': inet=str(r[3]).replace(',','')
            return ({'status':'ok','trade_date':d,'taiex_close':str(tx[1]).replace(',',''),'taiex_change_pct':str(tx[4]).replace('%',''),'breadth_up':up,'breadth_down':down,'turnover_hundred_mn_twd':turn,'intraday_last_time':last[0],'intraday_cum_trades':str(last[5]).replace(',',''),'intraday_cum_shares':str(last[6]).replace(',',''),'intraday_cum_amount_hundred_mn_twd':str(last[7]).replace(',',''),'foreign_net_hundred_mn_twd':fnet,'total_inst_net_hundred_mn_twd':inet},links)
        except Exception as e:
            err=str(e)
    return ({'status':'error','error_message':err or 'twse unavailable'},links)

def fetch_yh(symbols):
    data=[]
    for s in symbols:
        try:
            u=f'https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval=5m&range=5d&includePrePost=false&events=div%2Csplit'
            j=requests.get(u,timeout=20,headers=UA).json();r=((j.get('chart') or {}).get('result') or [None])[0]
            if not r: continue
            m=r.get('meta') or {}
            q=((r.get('indicators') or {}).get('quote') or [{}])[0]
            pts=[(t,c) for t,c in zip(r.get('timestamp') or [],q.get('close') or []) if c is not None]
            if not pts: continue
            t,px=pts[-1];pc=m.get('previousClose');chg=None if pc in (None,0) else float(px)-float(pc);pct=None if pc in (None,0) else chg/float(pc)*100
            data.append({'symbol':s,'name':m.get('shortName') or s,'regular_market_price':f'{float(px):.2f}','change_pct':f'{pct:+.2f}' if pct is not None else None,'volume':str(m.get('regularMarketVolume')) if m.get('regularMarketVolume') else None,'timestamp':datetime.fromtimestamp(t,tz=TZ).isoformat()})
        except: pass
    return {'status':'ok' if data else 'error','error_message':None if data else 'No quotes','data':data}

def fetch_poly():
    try:
        a=requests.get('https://gamma-api.polymarket.com/markets?closed=false&limit=1000',timeout=30,headers=UA).json();o=[]
        for m in a:
            q=(m.get('question') or '').strip().lower();p=m.get('lastTradePrice')
            if p is None: continue
            if 'taiwan' in q or 'fed' in q or 'oil' in q:
                o.append({'question':m.get('question'),'probability_pct':round(float(p)*100,2),'end_date':m.get('endDate'),'url':f"https://polymarket.com/event/{m.get('slug')}" if m.get('slug') else None})
        return {'status':'ok','data':o[:6]}
    except Exception as e:
        return {'status':'error','error_message':str(e),'data':[]}

def fetch_reddit():
    try:
        subs=['stocks','investing','wallstreetbets'];kw=['taiwan','tsmc','semiconductor','ai','chip'];posts=[]
        for s in subs:
            j=requests.get(f'https://www.reddit.com/r/{s}/hot.json?limit=40',timeout=20,headers=UA).json()
            for p in ((j.get('data') or {}).get('children') or []):
                d=p.get('data') or {};t=(d.get('title') or '').strip().lower();hit=[k for k in kw if k in t]
                posts.append({'subreddit':s,'title':d.get('title') or '','score':d.get('score',0),'matched_keywords':hit,'url':'https://reddit.com'+(d.get('permalink') or '')})
        hits=[x for x in posts if x['matched_keywords']]
        return {'status':'ok','summary':{'sample_size':len(posts),'hit_count':len(hits),'hit_ratio_pct':round((len(hits)/len(posts)*100),2) if posts else 0.0},'top_hits':sorted(hits,key=lambda x:x['score'],reverse=True)[:8]}
    except Exception as e:
        return {'status':'error','error_message':str(e),'summary':None,'top_hits':[]}

def fetch_news():
    try:
        x=requests.get('https://tw.stock.yahoo.com/rss',timeout=20,headers=UA).text
        items=[]
        for blk in re.findall(r'<item>(.*?)</item>',x,re.S)[:12]:
            t=re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>',blk,re.S)
            l=re.search(r'<link>(.*?)</link>',blk,re.S)
            p=re.search(r'<pubDate>(.*?)</pubDate>',blk,re.S)
            title=((t.group(1) or t.group(2)) if t else '').strip()
            if title and l: items.append({'title':title,'link':l.group(1).strip(),'published':p.group(1).strip() if p else None})
        return {'status':'ok','headlines':items[:8]}
    except Exception as e:
        return {'status':'error','error_message':str(e),'headlines':[]}

def cls(p):
    x=fnum(p,0)
    return 'ma-up' if x>0 else ('ma-down' if x<0 else 'ma-flat')

def arr(p):
    x=fnum(p,0)
    return '▲' if x>0 else ('▼' if x<0 else '→')

def to_cn(s):
    for a,b in [('盤中','盘中'),('風險','风险'),('情境','情景'),('機率','概率'),('關注','关注'),('個股','个股'),('漲','涨'),('買超','买超'),('賣超','卖超'),('來源','来源')]: s=s.replace(a,b)
    return s


def main():
    now=datetime.now(TZ);date=now.strftime('%Y-%m-%d');run_id=f"intraday_tw_{now.strftime('%Y%m%d_%H%M')}"
    base=Path(__file__).resolve().parent.parent;run=base/'runs'/run_id
    for d in ['fetched','processed','charts','output']:(run/d).mkdir(parents=True,exist_ok=True)
    wl=read_watchlist(base/'watchlist.md');high=[w for w in wl if w.get('priority')=='high']
    syms=['2330.TW','2317.TW','2454.TW','2308.TW','2881.TW','2891.TW']
    for w in high:
        t=to_yh(w.get('ticker',''))
        if t and t not in syms: syms.append(t)
    fetched_at=now_iso();twse,twse_links=fetch_twse(now);yh=fetch_yh(['^TWII']+syms);poly=fetch_poly();rd=fetch_reddit();news=fetch_news()
    bls='https://www.bls.gov/schedule/2026/';bea='https://www.bea.gov/index.php/news/blog/2026-01-15/economic-release-schedule-updates-gdp-personal-income-and-outlays'
    fetched={
      '03a_financial_datasets.json':{'schema_version':'1.0','source':'financial_datasets','status':'error','fetched_at':fetched_at,'error_message':'Connector not available in this runtime','data':None},
      '03b_yfinance.json':{'schema_version':'1.0','source':'yfinance','status':yh['status'],'fetched_at':fetched_at,'error_message':yh.get('error_message'),'data':yh.get('data')},
      '03c_alpha_vantage.json':{'schema_version':'1.0','source':'alpha_vantage','status':'error','fetched_at':fetched_at,'error_message':'API key unavailable','data':None},
      '03d_polymarket.json':{'schema_version':'1.0','source':'polymarket','status':poly['status'],'fetched_at':fetched_at,'error_message':poly.get('error_message'),'data':poly.get('data',[])},
      '03e_reddit.json':{'schema_version':'1.0','source':'reddit','status':rd['status'],'fetched_at':fetched_at,'error_message':rd.get('error_message'),'data':{'summary':rd.get('summary'),'top_hits':rd.get('top_hits')}},
      '03f_web_search.json':{'schema_version':'1.0','source':'web_search','status':news['status'],'fetched_at':fetched_at,'error_message':news.get('error_message'),'data':{'headlines':news.get('headlines',[]),'macro_calendar':[{'event':'美國非農就業 (March 2026)','time_taipei':'2026-04-03T20:30:00+08:00','source':bls},{'event':'美國個人收入/支出 (February 2026)','time_taipei':'2026-04-09T20:30:00+08:00','source':bea},{'event':'美國 CPI (March 2026)','time_taipei':'2026-04-10T20:30:00+08:00','source':bls}], 'source_links':twse_links+[bls,bea,'https://tw.stock.yahoo.com/rss']}}
    }
    for fn,obj in fetched.items():wjson(run/'fetched'/fn,obj)

    qrows=[q for q in (yh.get('data') or []) if q.get('symbol')!='^TWII']
    strong=max(qrows,key=lambda r:fnum(r.get('change_pct'))) if qrows else None
    weak=min(qrows,key=lambda r:fnum(r.get('change_pct'))) if qrows else None
    twii=next((q for q in (yh.get('data') or []) if q.get('symbol')=='^TWII'),None)
    px=twii.get('regular_market_price') if twii else None; pct=twii.get('change_pct') if twii else None
    br=None
    if twse.get('status')=='ok' and (twse.get('breadth_up') or 0)>0: br=round(twse['breadth_down']/twse['breadth_up'],2)
    risk='若美債殖利率急升且外資賣超擴大，台股盤中反彈延續性會下降。'
    conf='medium'

    integrated={'schema_version':'1.0','status':'partial','generated_at':fetched_at,'report_id':run_id,'report_type':'intraday','market_color_convention':'tw_stock','watchlist_high_priority':high,'data':{'twse_intraday':twse,'quotes':yh.get('data'),'polymarket':poly.get('data',[]),'reddit':{'summary':rd.get('summary'),'top_hits':rd.get('top_hits',[])},'headlines':news.get('headlines',[])}}
    indicators={'schema_version':'1.0','status':'partial','generated_at':fetched_at,'report_id':run_id,'indicators':{'taiex_last':px,'taiex_change_pct':pct,'breadth_ratio_down_to_up':br,'strongest_symbol':strong.get('symbol') if strong else None,'strongest_change_pct':strong.get('change_pct') if strong else None,'weakest_symbol':weak.get('symbol') if weak else None,'weakest_change_pct':weak.get('change_pct') if weak else None,'risk_to_next_session':risk,'confidence':conf}}
    charts={'schema_version':'1.0','status':'ok','generated_at':fetched_at,'report_id':run_id,'charts':[{'id':'tw_quotes_table','type':'table','source':'03b_yfinance.json'},{'id':'scenario_probs','type':'bar','source':'processed.report_draft.scenarios'}]}
    draft={'schema_version':'1.0','status':'partial','report_id':run_id,'drafted_at':fetched_at,'report_metadata':{'report_type':'intraday','target_date':date,'market':'TW','market_color_convention':'tw_stock','locale_priority':['zh-TW','zh-CN']},'insight_scorecard':[{'title':'指數與成交統計顯示短線偏震盪。','signal':'mixed','confidence':conf,'type':'mixed','evidence':[f'TAIEX {px}，日變動 {pct}%',f'跌/漲比 {br}' if br is not None else '跌/漲比暫缺'],'invalidation':'若台指快速突破前高且量能放大，震盪假設失效。'},{'title':'權值股分化，選股優先。','signal':'mixed','confidence':'medium','type':'fact','evidence':[f"最強 {strong['symbol']} {strong['change_pct']}%" if strong else '最強標的資料不足',f"最弱 {weak['symbol']} {weak['change_pct']}%" if weak else '最弱標的資料不足'],'invalidation':'若權值股午盤同步轉正，分化敘事失效。'},{'title':'隔夜宏觀事件仍是最大外生變數。','signal':'bearish','confidence':'medium','type':'inference','evidence':['2026-04-03 非農、2026-04-09 個人收入/支出、2026-04-10 CPI 皆在台灣夜盤時段公布。'],'invalidation':'若數據低波動且利率反應溫和，風險溢酬下降。'}],'scenarios':[{'name':'base','probability':55,'trigger_conditions':['量價平衡、權值分化'],'expected_market_behavior':'區間震盪','recommended_positioning':'區間交易，控倉'},{'name':'bull','probability':25,'trigger_conditions':['電子權值同步轉強且成交量放大'],'expected_market_behavior':'收斂後向上突破','recommended_positioning':'順勢加碼強勢股'},{'name':'bear','probability':20,'trigger_conditions':['外資賣壓擴大且金融/電子同步轉弱'],'expected_market_behavior':'尾盤走低','recommended_positioning':'降槓桿，提高現金比重'}],'execution_playbook':[{'window':'open','action':'避免第一根追價，等確認量價。','risk_control':'單筆風險 <= 資金 0.5%'},{'window':'mid_session','action':'量縮盤整採回撤買/反彈賣。','risk_control':'跌破區間下緣減碼'},{'window':'close','action':'重大數據前降低淨曝險。','risk_control':'必要時避險'}],'cross_market_transmission':{'facts':['BLS 行事曆：2026-04-03（ET）就業報告，台北時間 20:30。','BEA 排程：2026-04-09（ET）個人收入/支出，台北時間 20:30。'],'inference':'若美國通膨/就業高於預期，利率預期上修可能壓抑台股估值。'}}
    for fn,obj in [('integrated_data.json',integrated),('indicators.json',indicators),('charts_manifest.json',charts),('report_draft.json',draft)]:wjson(run/'processed'/fn,obj)
    wjson(run/'trigger_request.json',{'schema_version':'1.0','report_id':run_id,'report_type':'intraday','input_mode':'contextual','requested_at':fetched_at,'target_date':date,'locale_priority':['zh-TW','zh-CN'],'user_instructions':'今日台股盤中報告','focus_tickers':syms,'focus_sectors':['Semiconductors','Financials','AI Supply Chain'],'custom_parameters':None})
    wjson(run/'portfolio_gate.json',{'schema_version':'1.0','report_id':run_id,'mode':'without_portfolio','checked_at':fetched_at,'portfolio':None})
    wjson(run/'report_structure.json',{'schema_version':'1.0','report_id':run_id,'report_type':'intraday','portfolio_mode':'without_portfolio','resolved_at':fetched_at})

    headline=''.join([f"<li><a href='{h['link']}' target='_blank' rel='noreferrer'>{h['title']}</a></li>" for h in news.get('headlines',[])[:5]]) or '<li>今日暫無可用新聞。</li>'
    high_txt='、'.join([w['ticker'] for w in high]) if high else '無 high 優先級個股'
    qr=''.join([f"<tr><td>{q['symbol']}</td><td>{q['name']}</td><td class='ma-num'>{q['regular_market_price']}</td><td class='ma-num {cls(q.get('change_pct'))}'>{arr(q.get('change_pct'))} {q.get('change_pct','0')}%</td><td class='ma-num'>{q.get('volume') or '-'}</td></tr>" for q in qrows]) or '<tr><td colspan="5">暫無個股報價資料</td></tr>'
    pr=''.join([f"<tr><td>{p['question']}</td><td class='ma-num'>{p['probability_pct']:.2f}%</td><td>{(p.get('end_date') or '')[:10]}</td></tr>" for p in poly.get('data',[])[:4]]) or '<tr><td colspan="3">無可用資料</td></tr>'

    html=f"""<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width,initial-scale=1'/><title>台股盤中報告 {date}</title><style>:root{{--bg-page:#f3f6fb;--bg-card:#fff;--bg-muted:#eef2f8;--text-primary:#0f172a;--text-secondary:#1e293b;--text-muted:#64748b;--border-subtle:#dbe3ef;--border-strong:#93a4bc;--state-critical:#b42318;--state-key:#1d4ed8;--state-watch:#b45309;--state-context:#475467;--stock-up:#D62828;--stock-down:#1F9D55;--stock-flat:#6B7280;--focus-ring:#2563eb;--shadow-card:0 10px 24px rgba(15,23,42,.08)}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg-page);color:var(--text-primary);font-family:'Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif}}.ma-wrap{{max-width:1200px;margin:0 auto;padding:18px}}.ma-grid{{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px}}.ma-card{{background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:14px;padding:14px;box-shadow:var(--shadow-card)}}.ma-c12{{grid-column:span 12}}.ma-c8{{grid-column:span 12}}.ma-c6{{grid-column:span 12}}.ma-c4{{grid-column:span 12}}@media(min-width:980px){{.ma-c8{{grid-column:span 8}}.ma-c6{{grid-column:span 6}}.ma-c4{{grid-column:span 4}}}}.ma-kpi{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}@media(min-width:980px){{.ma-kpi{{grid-template-columns:repeat(4,minmax(0,1fr))}}}}.ma-num{{font-variant-numeric:tabular-nums}}.ma-up{{color:var(--stock-up)}}.ma-down{{color:var(--stock-down)}}.ma-flat{{color:var(--stock-flat)}}.ma-chip{{display:inline-flex;align-items:center;gap:6px;width:fit-content;max-width:100%;padding:4px 9px;border-radius:999px;font-size:12px;font-weight:700;white-space:nowrap}}.ma-critical{{background:#fee4e2;color:var(--state-critical)}}.ma-key{{background:#dbeafe;color:var(--state-key)}}.ma-watch{{background:#ffedd5;color:var(--state-watch)}}.ma-context{{background:#e8edf4;color:var(--state-context)}}.ma-table{{width:100%;border-collapse:collapse;font-size:14px}}.ma-table th,.ma-table td{{padding:8px;border-bottom:1px solid #e6ecf4;text-align:left;vertical-align:top}}.ma-tip{{position:relative;border-bottom:1px dotted var(--border-strong);cursor:help;outline:none}}.ma-tip:hover::after,.ma-tip:focus::after{{content:attr(data-tip);position:absolute;left:0;top:calc(100% + 6px);z-index:20;min-width:260px;max-width:440px;white-space:pre-line;padding:10px;border-radius:10px;background:#0f172a;color:#f8fafc;font-size:12px;box-shadow:0 10px 20px rgba(0,0,0,.24)}}.ma-small{{font-size:12px;color:var(--text-muted)}}#ma-mobile-sheet{{position:fixed;left:0;right:0;bottom:-100%;background:#0f172a;color:#fff;padding:14px;border-radius:14px 14px 0 0;transition:bottom .2s ease;z-index:50;white-space:pre-line}}#ma-mobile-sheet.show{{bottom:0}}</style></head><body><div class='ma-wrap'><section class='ma-card ma-c12'><h1 style='margin:0 0 8px'>台股盤中報告</h1><div class='ma-small'>生成時間：{fetched_at} | 日期：{date} | 市場色彩慣例：<span class='ma-up'>漲(紅)</span> / <span class='ma-down'>跌(綠)</span> / <span class='ma-flat'>平(灰)</span></div></section><div class='ma-grid' style='margin-top:12px'><section class='ma-card ma-c8'><h2 style='margin:0 0 8px'>Top 3 Takeaways</h2><p><span class='ma-chip ma-critical'>Critical</span> <span tabindex='0' class='ma-tip' data-tip='what_it_is: 台股加權指數即時狀態\nwhy_it_matters: 決定大盤風險偏好方向\nhow_to_read: 指數與量能同向放大較可信\nconfidence: {conf}\ntype: fact\nrisk_note: 收盤前結構可能反轉'>TAIEX {px or '-'}（{pct or '-'}%）</span></p><p><span class='ma-chip ma-key'>Key</span> <span tabindex='0' class='ma-tip' data-tip='what_it_is: 漲跌家數結構\nwhy_it_matters: 檢查是否為權值股單點撐盤\nhow_to_read: 跌/漲比越高代表市場廣度偏弱\nconfidence: {conf}\ntype: fact\nrisk_note: 午盤可能修正結構'>{('跌/漲比 '+str(br)) if br is not None else '跌/漲比暫缺'}</span></p><p><span class='ma-chip ma-watch'>Watch</span> <span tabindex='0' class='ma-tip' data-tip='what_it_is: 隔夜宏觀風險傳導\nwhy_it_matters: 夜盤數據可能改變隔日開盤缺口\nhow_to_read: 就業/通膨高於預期偏壓估值\nconfidence: medium\ntype: inference\nrisk_note: 若數據波動小則影響降溫'>最大風險：{risk}</span></p></section><section class='ma-card ma-c4'><h2 style='margin:0 0 8px'>Quick Stats</h2><div class='ma-kpi'><div><div class='ma-small'>TAIEX</div><div class='ma-num {cls(pct)}'>{arr(pct)} {px or '-'} ({pct or '-'}%)</div></div><div><div class='ma-small'>成交筆數(累計)</div><div class='ma-num'>{twse.get('intraday_cum_trades','-')}</div></div><div><div class='ma-small'>最強標的</div><div class='ma-num ma-up'>{(strong['symbol']+' '+strong['change_pct']+'%') if strong else '-'}</div></div><div><div class='ma-small'>最弱標的</div><div class='ma-num ma-down'>{(weak['symbol']+' '+weak['change_pct']+'%') if weak else '-'}</div></div></div></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>技術與盤面訊號</h2><ul><li>Fact: 指數變動 {pct or '-'}%，成交量累計 {twse.get('intraday_cum_shares','-')} 股。</li><li>Fact: 外資（百萬元）{twse.get('foreign_net_hundred_mn_twd','-')}；三大法人合計（百萬元）{twse.get('total_inst_net_hundred_mn_twd','-')}。</li><li>Inference: 若權值股分化延續，盤中策略宜偏區間與分批。</li></ul></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>Watchlist 個股追蹤</h2><div class='ma-small'>High 優先級：{high_txt}</div></section><section class='ma-card ma-c12'><h2 style='margin:0 0 8px'>個股熱度表（盤中）</h2><table class='ma-table'><thead><tr><th>代號</th><th>名稱</th><th>最新價</th><th>漲跌幅</th><th>成交量</th></tr></thead><tbody>{qr}</tbody></table></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>情境分析</h2><table class='ma-table'><thead><tr><th>情境</th><th>機率</th><th>觸發條件</th><th>操作建議</th></tr></thead><tbody><tr><td>Base</td><td class='ma-num'>55%</td><td>量價平衡、權值分化</td><td>區間交易，控倉</td></tr><tr><td>Bull</td><td class='ma-num'>25%</td><td>電子權值同步轉強</td><td>順勢加碼強勢股</td></tr><tr><td>Bear</td><td class='ma-num'>20%</td><td>外資賣壓擴大</td><td>降槓桿、提高現金比重</td></tr></tbody></table></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>Polymarket</h2><table class='ma-table'><thead><tr><th>事件</th><th>機率</th><th>到期</th></tr></thead><tbody>{pr}</tbody></table></section><section class='ma-card ma-c8'><h2 style='margin:0 0 8px'>Breaking News（Web）</h2><ul>{headline}</ul></section><section class='ma-card ma-c4'><h2 style='margin:0 0 8px'>Tomorrow Preview</h2><ul><li>2026-04-03 20:30（台北）美國非農就業</li><li>2026-04-09 20:30（台北）美國個人收入/支出</li><li>2026-04-10 20:30（台北）美國 CPI</li></ul></section><section class='ma-card ma-c12'><h3 style='margin:0 0 8px'>Sources</h3><div class='ma-small'>TWSE MI_5MINS / MI_INDEX / BFI82U, Yahoo Finance Chart API, Yahoo TW RSS, Reddit JSON, Polymarket API, BLS Release Calendar, BEA Release Schedule Update</div></section></div></div><div id='ma-mobile-sheet'></div><script>const s=document.getElementById('ma-mobile-sheet');document.querySelectorAll('.ma-tip').forEach(e=>e.addEventListener('click',()=>{{s.textContent=e.getAttribute('data-tip');s.classList.add('show');}}));s.addEventListener('click',()=>s.classList.remove('show'));</script></body></html>"""
    html_cn=to_cn(html).replace("lang='zh-Hant'","lang='zh-Hans'")
    tw_html=run/'output'/f'report_intraday_{date}_zh-TW.html'; cn_html=run/'output'/f'report_intraday_{date}_zh-CN.html'; tw_json=run/'output'/f'report_intraday_{date}_zh-TW.json'; cn_json=run/'output'/f'report_intraday_{date}_zh-CN.json'
    tw_html.write_text(html,encoding='utf-8'); cn_html.write_text(html_cn,encoding='utf-8'); wjson(tw_json,draft); d2=json.loads(json.dumps(draft)); d2['report_metadata']['locale']='zh-CN'; wjson(cn_json,d2)
    wjson(run/'output_manifest.json',{'schema_version':'1.0','report_id':run_id,'generated_at':fetched_at,'status':'ok','style_contract':{'market_color_convention':'tw_stock','stock_up_color':'#D62828','stock_down_color':'#1F9D55','stock_flat_color':'#6B7280','uses_sign_and_icon_with_color':True,'interpretation_on_hover_enabled':True},'outputs':[{'locale':'zh-TW','priority':'primary','file_path':str(tw_html).replace('\\','/'),'file_format':'html','status':'ok'},{'locale':'zh-CN','priority':'secondary','file_path':str(cn_html).replace('\\','/'),'file_format':'html','status':'ok'},{'locale':'zh-TW','priority':'primary','file_path':str(tw_json).replace('\\','/'),'file_format':'json','status':'ok'},{'locale':'zh-CN','priority':'secondary','file_path':str(cn_json).replace('\\','/'),'file_format':'json','status':'ok'}]})
    print(run_id)

if __name__=='__main__': main()
