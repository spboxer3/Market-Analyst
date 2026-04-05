#!/usr/bin/env python3
import json, re
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from yfinance_client import fetch_quotes

TZ = ZoneInfo("Asia/Taipei")
UA = {"User-Agent": "market-analyst/1.0"}

def now_iso(): return datetime.now(TZ).isoformat()
def fnum(v, d=0.0):
    try: return float(str(v).replace(",", "").replace("%", "").strip())
    except: return d
def fmt_pct(v): return "-" if v in (None, "") else f"{fnum(v):+.2f}%"
def cls(v): return "ma-up" if fnum(v) > 0 else ("ma-down" if fnum(v) < 0 else "ma-flat")
def arr(v): return "▲" if fnum(v) > 0 else ("▼" if fnum(v) < 0 else "→")
def wjson(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
def rjson(p):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except:
        try: return json.loads(p.read_text(encoding="utf-8-sig"))
        except: return None

def read_watchlist(p):
    out = []
    if not p.exists(): return out
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip().startswith("|") or "Ticker" in ln or "---" in ln: continue
        a = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(a) >= 6 and a[0] and not a[0].startswith("<!--"):
            out.append({"ticker": a[0], "name": a[1], "market": a[2], "priority": a[3].lower(), "notes": a[4], "added_date": a[5]})
    return out

def to_yh(s):
    s = s.strip().upper()
    if s.endswith(".TW") or s.endswith(".TWO"): return s
    return f"{s}.TW" if re.fullmatch(r"\d{4}", s) else None

def fetch_twse(base):
    err = None; links = []
    for i in range(8):
        d = (base - timedelta(days=i)).strftime("%Y%m%d")
        u1 = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d}"
        u2 = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={d}&type=ALLBUT0999&response=json"
        u3 = f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate={d}&type=day&response=json"
        links = [u1, u2, u3]
        try:
            mi = requests.get(u1, timeout=20, headers=UA).json()
            idx = requests.get(u2, timeout=20, headers=UA).json()
            bfi = requests.get(u3, timeout=20, headers=UA).json()
            if mi.get("stat") != "OK" or idx.get("stat") != "OK" or bfi.get("stat") != "OK": continue
            rows = mi.get("data") or []
            if not rows: continue
            last = rows[-1]
            tx = {r[0]: r for r in (idx.get("tables", [{}])[0].get("data") or [])}.get("發行量加權股價指數")
            if not tx: continue
            up = down = 0
            for r in (idx.get("tables", [{}, {}, {}, {}, {}, {}, {}, {}])[7].get("data") or []):
                k, v = str(r[0]), int(str(r[1]).split("(")[0].replace(",", ""))
                if k.startswith("漲"): up = v
                if k.startswith("跌"): down = v
            fnet = inet = None
            for r in (bfi.get("data") or []):
                t = str(r[0]).strip()
                if t == "外資及陸資(不含外資自營商)": fnet = str(r[3]).replace(",", "")
                if t == "合計": inet = str(r[3]).replace(",", "")
            return ({
                "status": "ok", "trade_date": d, "taiex_close": str(tx[1]).replace(",", ""), "taiex_change_pct": str(tx[4]).replace("%", ""),
                "breadth_up": up, "breadth_down": down, "intraday_last_time": last[0], "intraday_cum_trades": str(last[5]).replace(",", ""),
                "intraday_cum_shares": str(last[6]).replace(",", ""), "foreign_net_hundred_mn_twd": fnet, "total_inst_net_hundred_mn_twd": inet
            }, links)
        except Exception as e:
            err = str(e)
    return ({"status": "error", "error_message": err or "twse unavailable"}, links)

def fetch_yh(symbols):
    return fetch_quotes(symbols, period="5d", interval="5m")

def fetch_news():
    try:
        x = requests.get("https://tw.stock.yahoo.com/rss", timeout=20, headers=UA).text
        items = []
        for blk in re.findall(r"<item>(.*?)</item>", x, re.S)[:8]:
            t = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", blk, re.S)
            l = re.search(r"<link>(.*?)</link>", blk, re.S)
            title = ((t.group(1) or t.group(2)) if t else "").strip()
            if title and l: items.append({"title": title, "link": l.group(1).strip()})
        return {"status": "ok", "headlines": items}
    except Exception as e:
        return {"status": "error", "error_message": str(e), "headlines": []}

def latest_premarket(base, date):
    cand = sorted((base / "runs").glob("pre_market_tw_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for run in cand:
        p = run / "output" / f"report_pre_market_{date}_zh-TW.json"
        if p.exists():
            d = rjson(p)
            if d: return {"run_id": run.name, "path": str(p).replace("\\", "/"), "data": d}
    return None

def market_bias(pct, br, foreign):
    bear = (pct is not None and pct <= -1) + (br is not None and br >= 1.5) + (foreign is not None and foreign < 0)
    bull = (pct is not None and pct >= 1) + (br is not None and br <= 0.75) + (foreign is not None and foreign > 0)
    return "bearish" if bear >= 2 else ("bullish" if bull >= 2 else "mixed")

def validate(pre, pct, br, foreign):
    live = market_bias(pct, br, foreign)
    if not pre:
        return {"status": "missing", "score": None, "verdict": "no_baseline", "summary": "找不到盤前報告基線，盤中改以即時盤面為主。", "matched_points": [], "missed_points": [], "live_view": live, "premarket_report_id": None, "premarket_path": None}
    insights = pre["data"].get("executive_insights") or []
    bias = "bearish" if any(i.get("signal") == "bearish" for i in insights) else ("bullish" if any(i.get("signal") == "bullish" for i in insights) else "mixed")
    score, matched, missed = 45, [], []
    if bias == live: score += 25; matched.append(f"盤前主基調 {bias} 與盤中結果一致。")
    elif bias == "mixed": score += 10; matched.append("盤前保留震盪假設，避免了單邊誤判。")
    else: missed.append(f"盤前主基調 {bias}，但盤中更接近 {live}。")
    if br is not None and ((br >= 1.5 and bias != "bullish") or (br <= 0.75 and bias == "bullish")): score += 15; matched.append(f"跌/漲比 {br} 支持盤前風險判斷。")
    elif br is not None: missed.append("市場廣度沒有完全支持盤前方向。")
    if foreign is not None and ((foreign < 0 and bias != "bullish") or (foreign > 0 and bias == "bullish")): score += 10; matched.append("資金流向與盤前風控方向一致。")
    elif foreign is not None: missed.append("資金流向對盤前方向驗證不足。")
    score = max(0, min(score, 100))
    verdict = "accurate" if score >= 75 else ("partially_accurate" if score >= 55 else "inaccurate")
    summary = {"accurate": "盤前策略目前大致準確，可沿用原先風控框架。", "partially_accurate": "盤前策略部分準確，方向可參考，但需調整節奏與倉位。", "inaccurate": "盤前策略與盤中盤面偏差擴大，應改以即時訊號為主。"}[verdict]
    return {"status": "ok", "score": score, "verdict": verdict, "summary": summary, "matched_points": matched, "missed_points": missed, "live_view": live, "premarket_report_id": pre["run_id"], "premarket_path": pre["path"]}

def advice(state, qrows):
    if state == "bearish":
        acts, risk = ["避免追價，反彈未帶量前不提高曝險。", "弱勢股優先減碼，高 beta 部位先收斂。", "只允許小部位試單相對強勢股。"], "high"
    elif state == "bullish":
        acts, risk = ["分批跟進強勢股，不在急拉時一次性追進。", "確認權值與中小型股同步轉強再擴大部位。", "回檔守住均價可保留趨勢單。"], "medium"
    else:
        acts, risk = ["以區間應對，不重押單邊方向。", "量縮時做回撤承接、反彈調節。", "停損放在區間下緣，避免震盪放大風險。"], "medium"
    watch = []
    for q in qrows:
        if q["symbol"] == "2344.TW":
            watch.append({"ticker": "2344", "last_price": q["regular_market_price"], "change_pct": q["change_pct"], "commentary": "若強於大盤且量能放大，可列為盤中優先驗證標的。"})
    return {"stance": state, "risk_level": risk, "focus": acts[0], "actions": acts, "watchlist_actions": watch}

def main():
    now = datetime.now(TZ); date = now.strftime("%Y-%m-%d"); run_id = f"intraday_tw_{now.strftime('%Y%m%d_%H%M')}"
    base = Path(__file__).resolve().parent.parent; run = base / "runs" / run_id
    for d in ["fetched", "processed", "charts", "output"]: (run / d).mkdir(parents=True, exist_ok=True)
    wl = read_watchlist(base / "watchlist.md"); high = [w for w in wl if w.get("priority") == "high"]
    syms = ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2881.TW", "2891.TW"]
    for w in high:
        t = to_yh(w["ticker"])
        if t and t not in syms: syms.append(t)
    fetched_at = now_iso(); twse, twse_links = fetch_twse(now); yh = fetch_yh(["^TWII"] + syms); news = fetch_news()
    qrows = [q for q in (yh.get("data") or []) if q.get("symbol") != "^TWII"]; twii = next((q for q in (yh.get("data") or []) if q.get("symbol") == "^TWII"), None)
    strong = max(qrows, key=lambda r: fnum(r.get("change_pct"))) if qrows else None; weak = min(qrows, key=lambda r: fnum(r.get("change_pct"))) if qrows else None
    px = twii.get("regular_market_price") if twii else None; pct = twii.get("change_pct") if twii else None; pct_num = fnum(pct, None) if pct is not None else None
    br = round(twse["breadth_down"] / twse["breadth_up"], 2) if twse.get("status") == "ok" and (twse.get("breadth_up") or 0) > 0 else None
    foreign = fnum(twse.get("foreign_net_hundred_mn_twd"), None) if twse.get("foreign_net_hundred_mn_twd") else None
    pre = latest_premarket(base, date); validation = validate(pre, pct_num, br, foreign); live = advice(validation["live_view"], qrows); conf = "medium" if validation["verdict"] != "inaccurate" else "low"
    fetched = {
        "03b_yfinance.json": {"schema_version": "1.0", "source": "yfinance", "status": yh["status"], "fetched_at": fetched_at, "error_message": yh.get("error_message"), "data": yh.get("data")},
        "03f_web_search.json": {"schema_version": "1.0", "source": "web_search", "status": news["status"], "fetched_at": fetched_at, "error_message": news.get("error_message"), "data": {"headlines": news.get("headlines", []), "source_links": twse_links + ["https://tw.stock.yahoo.com/rss"]}},
    }
    for fn, obj in fetched.items(): wjson(run / "fetched" / fn, obj)
    draft = {
        "schema_version": "1.0", "status": "partial", "report_id": run_id, "drafted_at": fetched_at,
        "report_metadata": {"report_type": "intraday", "target_date": date, "market": "TW", "market_color_convention": "tw_stock", "locale_priority": ["zh-TW", "zh-CN"]},
        "premarket_validation": validation, "realtime_advice": live,
        "insight_scorecard": [
            {"title": "盤前策略驗證已納入盤中判斷。", "signal": validation["live_view"], "confidence": conf, "type": "mixed", "evidence": [validation["summary"], f"驗證分數 {validation['score']}/100" if validation["score"] is not None else "無可用驗證分數"], "invalidation": "若午後量價結構翻轉，需重新評估。"},
            {"title": "市場廣度與資金面決定盤中節奏。", "signal": validation["live_view"], "confidence": conf, "type": "fact", "evidence": [f"TAIEX {px}，日變動 {fmt_pct(pct)}", f"跌/漲比 {br}" if br is not None else "跌/漲比暫缺", f"外資淨流向 {foreign:+.0f} 百萬元" if foreign is not None else "外資流向暫缺"], "invalidation": "若權值股與中小型股同步轉強，盤勢可轉攻。"},
            {"title": "即時建議以風險控制先行。", "signal": live["stance"], "confidence": conf, "type": "inference", "evidence": live["actions"], "invalidation": "若盤中出現新主線且量能擴大，建議需更新。"}
        ],
        "scenarios": [{"name": "base", "probability": 50, "trigger_conditions": ["盤前僅部分準確", "量價未失衡"], "expected_market_behavior": "區間震盪", "recommended_positioning": "控倉交易"}, {"name": "bull", "probability": 25, "trigger_conditions": ["電子權值同步轉強", "跌/漲比修復"], "expected_market_behavior": "向上突破", "recommended_positioning": "順勢加碼強勢股"}, {"name": "bear", "probability": 25, "trigger_conditions": ["外資賣壓擴大", "弱勢擴散"], "expected_market_behavior": "尾盤走低", "recommended_positioning": "提高現金比重"}],
        "execution_playbook": [{"window": "open", "action": "先看盤前策略是否被第一波量價確認。", "risk_control": "未被驗證前，不提高總曝險。"}, {"window": "mid_session", "action": "依驗證結果切換成區間交易或趨勢追蹤。", "risk_control": "驗證分數低於 55 時，減少主觀方向部位。"}, {"window": "close", "action": "若盤前觀點失準，尾盤前重建隔日假設。", "risk_control": "重大數據前降低淨曝險。"}]
    }
    for fn, obj in [("integrated_data.json", {"schema_version": "1.0", "status": "partial", "report_id": run_id, "generated_at": fetched_at, "premarket_validation": validation, "watchlist_high_priority": high, "data": {"twse_intraday": twse, "quotes": yh.get("data"), "headlines": news.get("headlines", [])}}), ("indicators.json", {"schema_version": "1.0", "status": "partial", "report_id": run_id, "generated_at": fetched_at, "indicators": {"taiex_last": px, "taiex_change_pct": pct, "breadth_ratio_down_to_up": br, "strategy_validation_score": validation["score"], "realtime_stance": live["stance"], "risk_level": live["risk_level"]}}), ("report_draft.json", draft)]: wjson(run / "processed" / fn, obj)
    matched = "".join([f"<li>{escape(x)}</li>" for x in validation["matched_points"]]) or "<li>尚無明確命中點。</li>"
    missed = "".join([f"<li>{escape(x)}</li>" for x in validation["missed_points"]]) or "<li>目前未發現重大偏差。</li>"
    headlines = "".join([f"<li><a href='{escape(h['link'])}' target='_blank' rel='noreferrer'>{escape(h['title'])}</a></li>" for h in news.get("headlines", [])[:5]]) or "<li>今日暫無可用新聞。</li>"
    qr = "".join([f"<tr><td>{escape(q['symbol'])}</td><td>{escape(q['name'])}</td><td class='ma-num'>{escape(q['regular_market_price'])}</td><td class='ma-num {cls(q.get('change_pct'))}'>{arr(q.get('change_pct'))} {escape(fmt_pct(q.get('change_pct')))}</td><td class='ma-num'>{escape(str(q.get('volume') or '-'))}</td></tr>" for q in qrows]) or "<tr><td colspan='5'>暫無個股報價資料</td></tr>"
    wh = "".join([f"<tr><td>{escape(w['ticker'])}</td><td class='ma-num'>{escape(str(w['last_price']))}</td><td class='ma-num {cls(w.get('change_pct'))}'>{arr(w.get('change_pct'))} {escape(fmt_pct(w.get('change_pct')))}</td><td>{escape(w['commentary'])}</td></tr>" for w in live["watchlist_actions"]]) or "<tr><td colspan='4'>目前沒有可用的 high watchlist 即時建議。</td></tr>"
    badge = {"accurate": "ma-key", "partially_accurate": "ma-watch", "inaccurate": "ma-critical", "no_baseline": "ma-context"}.get(validation["verdict"], "ma-context")
    label = {"accurate": "Accurate", "partially_accurate": "Partially Accurate", "inaccurate": "Needs Reset", "no_baseline": "No Baseline"}.get(validation["verdict"], "Unknown")
    html = f"""<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width,initial-scale=1'/><title>台股盤中驗證報告 {date}</title><style>:root{{--bg-page:#f3f6fb;--bg-card:#fff;--bg-muted:#eef2f8;--text-primary:#0f172a;--text-secondary:#1e293b;--text-muted:#64748b;--border-subtle:#dbe3ef;--state-critical:#b42318;--state-key:#1d4ed8;--state-watch:#b45309;--state-context:#475467;--stock-up:#D62828;--stock-down:#1F9D55;--stock-flat:#6B7280;--shadow-card:0 10px 24px rgba(15,23,42,.08)}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(180deg,#eef4ff 0%,#f8fafc 55%,#eef2f8 100%);color:var(--text-primary);font-family:'Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif}}.ma-wrap{{max-width:1240px;margin:0 auto;padding:20px}}.ma-grid{{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px}}.ma-card{{background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:16px;padding:16px;box-shadow:var(--shadow-card)}}.ma-c12{{grid-column:span 12}}.ma-c8,.ma-c6,.ma-c4{{grid-column:span 12}}@media(min-width:980px){{.ma-c8{{grid-column:span 8}}.ma-c6{{grid-column:span 6}}.ma-c4{{grid-column:span 4}}}}.ma-kpi{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.ma-kpi>div{{background:var(--bg-muted);padding:10px;border-radius:12px}}@media(min-width:980px){{.ma-kpi{{grid-template-columns:repeat(4,minmax(0,1fr))}}}}.ma-num{{font-variant-numeric:tabular-nums}}.ma-up{{color:var(--stock-up)}}.ma-down{{color:var(--stock-down)}}.ma-flat{{color:var(--stock-flat)}}.ma-chip{{display:inline-flex;align-items:center;gap:6px;width:fit-content;max-width:100%;padding:4px 9px;border-radius:999px;font-size:12px;font-weight:700;white-space:nowrap}}.ma-critical{{background:#fee4e2;color:var(--state-critical)}}.ma-key{{background:#dbeafe;color:var(--state-key)}}.ma-watch{{background:#ffedd5;color:var(--state-watch)}}.ma-context{{background:#e8edf4;color:var(--state-context)}}.ma-table{{width:100%;border-collapse:collapse;font-size:14px}}.ma-table th,.ma-table td{{padding:8px;border-bottom:1px solid #e6ecf4;text-align:left;vertical-align:top}}.ma-small{{font-size:12px;color:var(--text-muted)}}</style></head><body><div class='ma-wrap'><section class='ma-card ma-c12'><h1 style='margin:0 0 8px'>台股盤中驗證報告</h1><div class='ma-small'>生成時間：{escape(fetched_at)} | 日期：{escape(date)} | 市場色彩慣例：<span class='ma-up'>漲(紅)</span> / <span class='ma-down'>跌(綠)</span> / <span class='ma-flat'>平(灰)</span></div></section><div class='ma-grid' style='margin-top:12px'><section class='ma-card ma-c8'><h2 style='margin:0 0 8px'>Top 3 Takeaways</h2><p><span class='ma-chip {badge}'>{label}</span> 盤前驗證 {validation['score'] if validation['score'] is not None else '-'} / 100</p><p><span class='ma-chip ma-key'>Key</span> TAIEX {escape(str(px or '-'))}（{escape(fmt_pct(pct))}）</p><p><span class='ma-chip ma-watch'>Watch</span> {escape(live['focus'])}</p></section><section class='ma-card ma-c4'><h2 style='margin:0 0 8px'>Quick Stats</h2><div class='ma-kpi'><div><div class='ma-small'>TAIEX</div><div class='ma-num {cls(pct)}'>{arr(pct)} {escape(str(px or '-'))} ({escape(fmt_pct(pct))})</div></div><div><div class='ma-small'>跌/漲比</div><div class='ma-num'>{escape(str(br if br is not None else '-'))}</div></div><div><div class='ma-small'>最強標的</div><div class='ma-num ma-up'>{escape((strong['symbol'] + ' ' + fmt_pct(strong['change_pct'])) if strong else '-')}</div></div><div><div class='ma-small'>最弱標的</div><div class='ma-num ma-down'>{escape((weak['symbol'] + ' ' + fmt_pct(weak['change_pct'])) if weak else '-')}</div></div></div></section><section class='ma-card ma-c4'><h2 style='margin:0 0 8px'>盤前策略驗證</h2><p>{escape(validation['summary'])}</p><div class='ma-small'>盤前來源：{escape(validation.get('premarket_report_id') or '無')}</div></section><section class='ma-card ma-c8'><h2 style='margin:0 0 8px'>即時投資建議</h2><div class='ma-chip {badge}'>{escape(live['stance'])}</div><ul>{"".join([f"<li>{escape(x)}</li>" for x in live['actions']])}</ul></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>驗證命中點</h2><ul>{matched}</ul></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>策略偏差與修正</h2><ul>{missed}</ul></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>Watchlist 個股追蹤</h2><div class='ma-small'>High 優先級：{escape("、".join([w['ticker'] for w in high]) if high else "無")}</div><table class='ma-table' style='margin-top:8px'><thead><tr><th>代號</th><th>最新價</th><th>漲跌幅</th><th>盤中建議</th></tr></thead><tbody>{wh}</tbody></table></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>個股熱度表（盤中）</h2><table class='ma-table'><thead><tr><th>代號</th><th>名稱</th><th>最新價</th><th>漲跌幅</th><th>成交量</th></tr></thead><tbody>{qr}</tbody></table></section><section class='ma-card ma-c12'><h2 style='margin:0 0 8px'>Breaking News（Web）</h2><ul>{headlines}</ul></section></div></div></body></html>"""
    html_cn = html.replace("盤中驗證報告", "盘中验证报告").replace("盤前策略驗證", "盘前策略验证").replace("即時投資建議", "实时投资建议").replace("驗證命中點", "验证命中点").replace("策略偏差與修正", "策略偏差与修正").replace("個股熱度表（盤中）", "个股热度表（盘中）").replace("Watchlist 個股追蹤", "Watchlist 个股追踪").replace("日期", "日期")
    tw_html = run / "output" / f"report_intraday_{date}_zh-TW.html"; cn_html = run / "output" / f"report_intraday_{date}_zh-CN.html"
    tw_json = run / "output" / f"report_intraday_{date}_zh-TW.json"; cn_json = run / "output" / f"report_intraday_{date}_zh-CN.json"
    tw_html.write_text(html, encoding="utf-8"); cn_html.write_text(html_cn, encoding="utf-8"); wjson(tw_json, draft); d2 = json.loads(json.dumps(draft)); d2["report_metadata"]["locale"] = "zh-CN"; wjson(cn_json, d2)
    wjson(run / "output_manifest.json", {"schema_version": "1.0", "report_id": run_id, "generated_at": fetched_at, "status": "ok", "style_contract": {"market_color_convention": "tw_stock", "stock_up_color": "#D62828", "stock_down_color": "#1F9D55", "stock_flat_color": "#6B7280", "uses_sign_and_icon_with_color": True, "interpretation_on_hover_enabled": False}, "outputs": [{"locale": "zh-TW", "priority": "primary", "file_path": str(tw_html).replace("\\", "/"), "file_format": "html", "status": "ok"}, {"locale": "zh-CN", "priority": "secondary", "file_path": str(cn_html).replace("\\", "/"), "file_format": "html", "status": "ok"}, {"locale": "zh-TW", "priority": "primary", "file_path": str(tw_json).replace("\\", "/"), "file_format": "json", "status": "ok"}, {"locale": "zh-CN", "priority": "secondary", "file_path": str(cn_json).replace("\\", "/"), "file_format": "json", "status": "ok"}]})
    print(run_id)

if __name__ == "__main__": main()
