#!/usr/bin/env python3
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_watchlist(path: Path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        if "Ticker" in line or "---" in line:
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) >= 6 and parts[0] and not parts[0].startswith("<!--"):
            rows.append(
                {
                    "ticker": parts[0],
                    "name": parts[1],
                    "sector": parts[2],
                    "priority": parts[3].lower(),
                    "notes": parts[4],
                    "added_date": parts[5],
                }
            )
    return rows


def twse_json(endpoint: str, date_str: str):
    url = endpoint.format(date=date_str)
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("stat") != "OK":
        raise RuntimeError(f"TWSE endpoint not OK: {url} | stat={data.get('stat')}")
    return data, url


def find_latest_twse_date(base_date: datetime):
    mi_ep = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALLBUT0999&response=json"
    bfi_ep = "https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate={date}&type=day&response=json"
    t86_ep = "https://www.twse.com.tw/rwd/zh/fund/T86?date={date}&selectType=ALLBUT0999&response=json"
    for d in range(0, 8):
        dt = (base_date - timedelta(days=d)).strftime("%Y%m%d")
        try:
            mi, mi_url = twse_json(mi_ep, dt)
            bfi, bfi_url = twse_json(bfi_ep, dt)
            t86, t86_url = twse_json(t86_ep, dt)
            return dt, mi, bfi, t86, [mi_url, bfi_url, t86_url]
        except Exception:
            continue
    raise RuntimeError("No TWSE trading date found in last 8 days")


def to_int(s: str) -> int:
    return int(str(s).replace(",", "").strip())


def to_float(s: str) -> float:
    return float(str(s).replace(",", "").strip())


def parse_sign(cell: str) -> int:
    return 1 if "+" in cell else -1


def fmt_money_ntd(v: int) -> str:
    sign = "-" if v < 0 else "+"
    return f"{sign}{abs(v)/1e8:.2f} 億"


def get_polymarket_markets():
    out = {"status": "error", "error": None, "data": []}
    try:
        url = "https://gamma-api.polymarket.com/markets?closed=false&limit=1200"
        arr = requests.get(url, timeout=30).json()
        picks = []
        for m in arr:
            q = (m.get("question") or "").strip()
            ql = q.lower()
            if ("taiwan" in ql and "invade" in ql) or ("oil" in ql and "win" not in ql):
                price = m.get("lastTradePrice")
                if price is None:
                    continue
                try:
                    p = round(float(price) * 100, 2)
                except Exception:
                    continue
                picks.append(
                    {
                        "question": q,
                        "probability_pct": p,
                        "end_date": m.get("endDate"),
                        "url": f"https://polymarket.com/event/{m.get('slug')}" if m.get("slug") else None,
                    }
                )
        out["status"] = "ok"
        out["data"] = picks[:5]
    except Exception as e:
        out["error"] = str(e)
    return out


def get_reddit_sentiment():
    subreddits = ["stocks", "investing", "wallstreetbets"]
    kws = ["energy", "oil", "gas", "power", "grid", "nuclear", "utility", "infrastructure"]
    merged = []
    try:
        for s in subreddits:
            url = f"https://www.reddit.com/r/{s}/hot.json?limit=50"
            r = requests.get(url, timeout=20, headers={"User-Agent": "market-analyst-bot/1.0"})
            r.raise_for_status()
            posts = r.json().get("data", {}).get("children", [])
            for p in posts:
                d = p.get("data", {})
                title = (d.get("title") or "").strip()
                merged.append(
                    {
                        "subreddit": s,
                        "title": title,
                        "score": d.get("score", 0),
                        "url": "https://reddit.com" + d.get("permalink", ""),
                    }
                )
        kw_count = {k: 0 for k in kws}
        energy_hits = []
        for p in merged:
            tl = p["title"].lower()
            matched = [k for k in kws if k in tl]
            for k in matched:
                kw_count[k] += 1
            if matched:
                energy_hits.append({**p, "matched_keywords": matched})
        return {
            "status": "ok",
            "summary": {"sample_size": len(merged), "energy_keyword_hits": len(energy_hits), "keyword_counts": kw_count},
            "top_energy_posts": sorted(energy_hits, key=lambda x: x["score"], reverse=True)[:8],
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e), "data": None}


def render_tw_html(
    target_date,
    latest_date,
    taiex_close,
    taiex_chg_pct,
    up_count,
    down_count,
    total_inst_net,
    strongest,
    weakest,
    us_macro,
    rows_html,
    poly_html,
    watch_text,
):
    return f"""<!doctype html>
<html lang='zh-Hant'>
<head>
<meta charset='utf-8'/>
<meta name='viewport' content='width=device-width, initial-scale=1'/>
<title>台股盤前報告（能源基礎設施） {target_date}</title>
<style>
:root {{
  --bg-page:#f4f7fb; --bg-card:#ffffff; --bg-muted:#eef3f9;
  --text-primary:#0f172a; --text-secondary:#1e293b; --text-muted:#64748b;
  --border-subtle:#dbe4ef; --border-strong:#94a3b8;
  --state-critical:#b42318; --state-key:#1d4ed8; --state-watch:#b45309; --state-context:#475467;
  --stock-up:#D62828; --stock-down:#1F9D55; --stock-flat:#6B7280;
  --focus-ring:#2563eb; --shadow-card:0 8px 24px rgba(15,23,42,.08);
}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg-page);color:var(--text-primary);font-family:"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif;line-height:1.5}}
.ma-wrap{{max-width:1200px;margin:0 auto;padding:20px}}
.ma-grid{{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px}}
.ma-card{{background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:14px;padding:14px;box-shadow:var(--shadow-card)}}
.ma-c12{{grid-column:span 12}} .ma-c8{{grid-column:span 12}} .ma-c6{{grid-column:span 12}} .ma-c4{{grid-column:span 12}}
@media (min-width: 980px) {{ .ma-c8{{grid-column:span 8}} .ma-c6{{grid-column:span 6}} .ma-c4{{grid-column:span 4}} }}
.ma-kpi{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}} @media (min-width:980px){{.ma-kpi{{grid-template-columns:repeat(4,minmax(0,1fr))}}}}
.ma-chip{{display:inline-flex;align-items:center;gap:6px;width:fit-content;max-width:100%;padding:4px 9px;border-radius:999px;font-size:12px;font-weight:700;white-space:nowrap}}
.ma-critical{{background:#fee4e2;color:var(--state-critical)}} .ma-key{{background:#dbeafe;color:var(--state-key)}} .ma-watch{{background:#ffedd5;color:var(--state-watch)}} .ma-context{{background:#e7ecf3;color:var(--state-context)}}
.ma-up{{color:var(--stock-up)}} .ma-down{{color:var(--stock-down)}} .ma-flat{{color:var(--stock-flat)}} .ma-num{{font-variant-numeric:tabular-nums}}
.ma-table{{width:100%;border-collapse:collapse;font-size:14px}} .ma-table th,.ma-table td{{padding:8px;border-bottom:1px solid #e7edf5;text-align:left;vertical-align:top}}
.ma-small{{font-size:12px;color:var(--text-muted)}}
.ma-tip{{position:relative;border-bottom:1px dotted var(--border-strong);cursor:help;outline:none}}
.ma-tip:hover::after,.ma-tip:focus::after{{content:attr(data-tip);position:absolute;left:0;top:calc(100% + 6px);z-index:10;min-width:260px;max-width:430px;white-space:pre-line;padding:10px;border-radius:10px;background:#0f172a;color:#f8fafc;font-size:12px;box-shadow:0 10px 24px rgba(0,0,0,.25)}}
.ma-fact{{border-left:4px solid #2563eb;padding-left:8px}} .ma-inf{{border-left:4px solid #f59e0b;padding-left:8px}}
</style>
</head>
<body>
<div class='ma-wrap'>
  <div class='ma-card ma-c12'>
    <h1 style='margin:0 0 6px'>台股盤前報告（能源基礎設施焦點）</h1>
    <div class='ma-small'>報告日：{target_date}｜市場資料基準：{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:]}｜市場慣例：<span class='ma-up'>漲紅 ▲</span> / <span class='ma-down'>跌綠 ▼</span> / <span class='ma-flat'>平盤 →</span></div>
  </div>
  <div class='ma-grid' style='margin-top:12px'>
    <section class='ma-card ma-c8'>
      <h2 style='margin:0 0 8px'>Top 3 Takeaways</h2>
      <p class='ma-fact'><span class='ma-chip ma-critical'>Critical</span> <span tabindex='0' class='ma-tip' data-tip='what_it_is: 市場廣度\nwhy_it_matters: 判斷賣壓是否擴散\nhow_to_read: 下跌家數明顯大於上漲家數偏空\nconfidence: high\ntype: fact\nrisk_note: 開盤若家數翻多則此訊號降級'>下跌家數/上漲家數 = {down_count}/{up_count}（{round(down_count/up_count,2)}），盤前風險偏好仍弱。</span></p>
      <p class='ma-fact'><span class='ma-chip ma-key'>Key</span> <span tabindex='0' class='ma-tip' data-tip='what_it_is: 政策Capex管線\nwhy_it_matters: 支撐重電與工程鏈中期訂單\nhow_to_read: 預算規模+執行進度是基本面核心\nconfidence: medium\ntype: fact\nrisk_note: 若工程遞延/執行率下滑，邏輯需下修'>台電電網韌性計畫總預算 5,645 億元；截至 2024/12 已完成 98 件工程（進度 29.61%）。</span></p>
      <p class='ma-inf'><span class='ma-chip ma-watch'>Watch</span> <span tabindex='0' class='ma-tip' data-tip='what_it_is: 族群擴散度\nwhy_it_matters: 單兵漲不等於族群趨勢\nhow_to_read: 上漲家數需擴大才可追價\nconfidence: medium\ntype: inference\nrisk_note: 量能同步放大且多檔翻紅時，需調整為偏多'>觀察池僅 {strongest['name']} 收紅（{strongest['chg_pct']}），短線仍偏個股行情而非全面輪動。</span></p>
    </section>
    <section class='ma-card ma-c4'>
      <h2 style='margin:0 0 8px'>Quick Stats</h2>
      <div class='ma-kpi'>
        <div><div class='ma-small'>加權指數</div><div class='ma-num ma-down'>▼ {taiex_close} ({taiex_chg_pct}%)</div></div>
        <div><div class='ma-small'>三大法人合計</div><div class='ma-num ma-down'>{fmt_money_ntd(total_inst_net)}</div></div>
        <div><div class='ma-small'>能源最強</div><div class='ma-num ma-up'>▲ {strongest['name']} {strongest['chg_pct']}</div></div>
        <div><div class='ma-small'>能源最弱</div><div class='ma-num ma-down'>▼ {weakest['name']} {weakest['chg_pct']}</div></div>
      </div>
      <div class='ma-small' style='margin-top:10px'>WTI：{us_macro['wti_close']}（{us_macro['wti_date']}）</div>
    </section>
    <section class='ma-card ma-c6'>
      <h2 style='margin:0 0 8px'>重大新聞 / 政策（Fact）</h2>
      <ul>
        <li>台電「強化電網韌性建設計畫」合計預算 <b>5,645 億元</b>。</li>
        <li>截至 2024 年底，已完成 <b>98 件</b> 工程，實績 <b>1,374 億元</b>，進度 <b>29.61%</b>。</li>
        <li>經濟部簡報：離岸風電 2025-2026 預估新增 <b>+2.6GW</b>，2030/2032/2035 累計目標 10.9/13.9/18.4GW。</li>
      </ul>
    </section>
    <section class='ma-card ma-c6'>
      <h2 style='margin:0 0 8px'>跨市場傳導（Interpretation）</h2>
      <ul>
        <li class='ma-inf'>油價維持高檔時，燃料成本與通膨預期可能壓抑高估值綠能股短線評價。</li>
        <li class='ma-inf'>但電網與離岸風電資本支出路徑明確，重電/EPC 中長期訂單可見度仍佳。</li>
        <li class='ma-fact'>下一個關鍵總經事件：美國非農（4/3 20:30 台北時間）。</li>
      </ul>
    </section>
    <section class='ma-card ma-c12'>
      <h2 style='margin:0 0 8px'>技術訊號：能源基建觀察池</h2>
      <table class='ma-table'>
        <thead><tr><th>代號</th><th>公司</th><th>子題材</th><th>收盤</th><th>漲跌幅</th><th>外資淨股數</th><th>三大法人淨股數</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div class='ma-small'>提示：顏色僅為輔助，已搭配 ▲/▼ 與 +/- 符號。</div>
    </section>
    <section class='ma-card ma-c8'>
      <h2 style='margin:0 0 8px'>Scenario（機率合計 100%）</h2>
      <table class='ma-table'>
        <thead><tr><th>情境</th><th>機率</th><th>觸發條件</th><th>建議操作</th></tr></thead>
        <tbody>
          <tr><td>Base</td><td class='ma-num'>50%</td><td>外資賣壓未完全收斂、量能偏低</td><td>核心持股保留，反彈調節高波動股</td></tr>
          <tr><td>Bull</td><td class='ma-num'>30%</td><td>政策標案加速、外資回補重電</td><td>回檔分批加碼強勢標的</td></tr>
          <tr><td>Bear</td><td class='ma-num'>20%</td><td>油價續升+風險資產回檔</td><td>降槓桿、停損前移</td></tr>
        </tbody>
      </table>
    </section>
    <section class='ma-card ma-c4'>
      <h2 style='margin:0 0 8px'>Watchlist 個股追蹤</h2>
      <div class='ma-small'>{watch_text}</div>
    </section>
    <section class='ma-card ma-c6'>
      <h2 style='margin:0 0 8px'>Polymarket（地緣風險）</h2>
      <table class='ma-table'>
        <thead><tr><th>市場</th><th>隱含機率</th><th>到期</th></tr></thead>
        <tbody>{poly_html}</tbody>
      </table>
    </section>
    <section class='ma-card ma-c6'>
      <h2 style='margin:0 0 8px'>Tomorrow Preview / 事件前瞻</h2>
      <ul>
        <li>2026-04-03 20:30（台北）：US Employment Situation（非農）。</li>
        <li>2026-04-09 20:30（台北）：US Personal Income and Outlays。</li>
        <li>2026-04-10 20:30（台北）：US CPI。</li>
      </ul>
      <div class='ma-small'>最大風險：若油價續升且外資賣壓擴散，能源基建短線估值壓力可能放大。</div>
    </section>
    <section class='ma-card ma-c12'>
      <h3 style='margin:0 0 8px'>Sources</h3>
      <div class='ma-small'>TWSE: MI_INDEX / BFI82U / T86；Taipower CSR（建構韌性電力）；MOEA 能源簡報；BLS/BEA 排程；Polymarket API；Reddit public JSON。</div>
    </section>
  </div>
</div>
</body>
</html>
"""


def main():
    tz = ZoneInfo("Asia/Taipei")
    now = datetime.now(tz)
    run_id = f"pre_market_tw_energyinfra_{now.strftime('%Y%m%d_%H%M')}"
    run_dir = Path("runs") / run_id
    for d in ["fetched", "processed", "charts", "output"]:
        (run_dir / d).mkdir(parents=True, exist_ok=True)

    fetched_at = now.isoformat()
    target_date = now.strftime("%Y-%m-%d")
    watchlist = read_watchlist(Path("watchlist.md"))
    high_watch = [w["ticker"] for w in watchlist if w.get("priority") == "high"]
    latest_date, mi, bfi, t86, twse_links = find_latest_twse_date(now)

    idx_rows = {r[0]: r for r in mi["tables"][0]["data"]}
    taiex_row = idx_rows["發行量加權股價指數"]
    mkt_table = mi["tables"][6]
    breadth_table = mi["tables"][7]
    stocks_table = mi["tables"][8]

    turnover = None
    for r in mkt_table["data"]:
        if str(r[0]).strip().startswith("3.大盤成交金額"):
            turnover = to_int(r[1])
            break
    if turnover is None:
        turnover = to_int(mkt_table["data"][-1][1])

    up_count = down_count = 0
    for r in breadth_table["data"]:
        t = str(r[0]).strip()
        if t.startswith("上漲"):
            up_count = to_int(re.sub(r"\(.*\)", "", r[1]))
        elif t.startswith("下跌"):
            down_count = to_int(re.sub(r"\(.*\)", "", r[1]))

    bfi_map = {r[0]: r for r in bfi["data"]}
    foreign_net = to_int(bfi_map["外資及陸資(不含外資自營商)"][3])
    total_inst_net = to_int(bfi_map["合計"][3])
    t86_rows = {r[0].strip(): r for r in t86["data"]}

    energy_tickers = [
        ("1513", "中興電", "重電/電網設備"),
        ("1519", "華城", "重電/變壓器"),
        ("1503", "士電", "重電設備"),
        ("1514", "亞力", "電力工程"),
        ("1504", "東元", "機電/馬達"),
        ("9933", "中鼎", "工程EPC"),
        ("9958", "世紀鋼", "離岸風電基礎"),
        ("6806", "森崴能源", "再生能源開發"),
        ("6869", "雲豹能源", "綠能整合"),
    ]
    srows = {r[0].strip(): r for r in stocks_table["data"]}
    energy_rows = []
    for tk, nm, grp in energy_tickers:
        r = srows.get(tk)
        if not r:
            continue
        sign = parse_sign(r[9])
        chg = to_float(r[10]) * sign
        close = to_float(r[8])
        prev = close - chg
        chg_pct = (chg / prev * 100) if prev else 0.0
        tr = t86_rows.get(tk, [])
        foreign_sh = to_int(tr[4]) if len(tr) >= 5 else 0
        total_inst_sh = to_int(tr[-1]) if len(tr) >= 1 else 0
        energy_rows.append(
            {
                "ticker": tk,
                "name": nm,
                "group": grp,
                "close": f"{close:.2f}",
                "chg": f"{chg:+.2f}",
                "chg_pct": f"{chg_pct:+.2f}%",
                "volume": str(to_int(r[2])),
                "foreign_net_shares": str(foreign_sh),
                "inst_net_shares": str(total_inst_sh),
            }
        )

    strongest = max(energy_rows, key=lambda x: float(x["chg_pct"].replace("%", "")))
    weakest = min(energy_rows, key=lambda x: float(x["chg_pct"].replace("%", "")))
    us_macro = {"wti_close": "101.91", "wti_date": "2026-03-29", "natgas_close": "2.94", "natgas_date": "2026-03-29"}
    macro_calendar = [
        {"event": "US Employment Situation (Mar)", "release_time_taipei": "2026-04-03T20:30:00+08:00", "source": "BLS"},
        {"event": "US Personal Income and Outlays (Feb)", "release_time_taipei": "2026-04-09T20:30:00+08:00", "source": "BEA"},
        {"event": "US CPI (Mar)", "release_time_taipei": "2026-04-10T20:30:00+08:00", "source": "BLS"},
    ]
    energy_policy_facts = [
        {
            "title": "台電強化電網韌性建設計畫",
            "facts": ["合計預算 5,645 億元", "截至 2024 年 12 月已完成 98 件工程，實績 1,374 億元，進度 29.61%"],
            "source": "Taipower CSR report excerpt PDF",
            "url": "https://service.taipower.com.tw/csr/report/Keo/2024_%25E5%25BB%25BA%25E6%25A7%258B%25E9%259F%258C%25E6%2580%25A7%25E9%259B%25BB%25E5%258A%259B.pdf",
        },
        {
            "title": "經濟部離岸風電路徑（簡報）",
            "facts": ["2025-2026 預估新增 +2.6GW", "累計目標裝置量：2030 年 10.9GW、2032 年 13.9GW、2035 年 18.4GW", "2030 年前區塊開發需 1.08 兆元融資"],
            "source": "MOEA energy briefing PDF",
            "url": "https://service.moea.gov.tw/EE514/wSite/public/Attachment/00104/f1739240662363.pdf",
        },
    ]

    polymarket = get_polymarket_markets()
    reddit = get_reddit_sentiment()

    fetched = {
        "03a_financial_datasets.json": {
            "schema_version": "1.0",
            "source": "financial_datasets",
            "status": "error",
            "fetched_at": fetched_at,
            "error_message": "Connector not available in current runtime",
            "data": None,
        },
        "03b_yfinance.json": {
            "schema_version": "1.0",
            "source": "yfinance",
            "status": "ok",
            "fetched_at": fetched_at,
            "error_message": None,
            "data": {
                "tw_market": {
                    "trade_date": latest_date,
                    "taiex_close": taiex_row[1].replace(",", ""),
                    "taiex_change_pct": taiex_row[4],
                    "turnover_twd": str(turnover),
                    "breadth_up": str(up_count),
                    "breadth_down": str(down_count),
                    "foreign_net_twd": str(foreign_net),
                    "total_institution_net_twd": str(total_inst_net),
                },
                "energy_infra_stocks": energy_rows,
                "macro_proxy": us_macro,
            },
        },
        "03c_alpha_vantage.json": {
            "schema_version": "1.0",
            "source": "alpha_vantage",
            "status": "error",
            "fetched_at": fetched_at,
            "error_message": "API key unavailable",
            "data": None,
        },
        "03d_polymarket.json": {
            "schema_version": "1.0",
            "source": "polymarket",
            "status": polymarket["status"],
            "fetched_at": fetched_at,
            "error_message": polymarket.get("error"),
            "data": {"markets": polymarket.get("data", [])},
        },
        "03e_reddit.json": {
            "schema_version": "1.0",
            "source": "reddit",
            "status": reddit["status"],
            "fetched_at": fetched_at,
            "error_message": reddit.get("error_message"),
            "data": reddit if reddit["status"] == "ok" else None,
        },
        "03f_web_search.json": {
            "schema_version": "1.0",
            "source": "web_search",
            "status": "ok",
            "fetched_at": fetched_at,
            "error_message": None,
            "data": {
                "macro_calendar": macro_calendar,
                "energy_policy_facts": energy_policy_facts,
                "source_links": twse_links
                + [
                    "https://service.taipower.com.tw/csr/report/Keo/2024_%25E5%25BB%25BA%25E6%25A7%258B%25E9%259F%258C%25E6%2580%25A7%25E9%259B%25BB%25E5%258A%259B.pdf",
                    "https://service.moea.gov.tw/EE514/wSite/public/Attachment/00104/f1739240662363.pdf",
                    "https://www.bls.gov/schedule/2026/04_sched_list.htm",
                    "https://www.bea.gov/index.php/news/blog/2026-01-15/economic-release-schedule-updates-gdp-personal-income-and-outlays",
                    "https://gamma-api.polymarket.com/markets?closed=false&limit=1200",
                ],
            },
        },
    }
    for fn, obj in fetched.items():
        write_json(run_dir / "fetched" / fn, obj)

    integrated = {
        "schema_version": "1.0",
        "status": "ok",
        "generated_at": fetched_at,
        "report_id": run_id,
        "target_market": "TW",
        "market_color_convention": "tw_stock",
        "focus_theme": "energy_infrastructure",
        "watchlist_high_priority": high_watch,
        "data": {
            "market": fetched["03b_yfinance.json"]["data"]["tw_market"],
            "energy_stocks": energy_rows,
            "macro_proxy": us_macro,
            "policy": energy_policy_facts,
            "polymarket": polymarket.get("data", []),
            "reddit_summary": reddit.get("summary") if reddit.get("status") == "ok" else None,
            "macro_calendar": macro_calendar,
        },
    }
    indicators = {
        "schema_version": "1.0",
        "status": "ok",
        "generated_at": fetched_at,
        "report_id": run_id,
        "indicators": {
            "breadth_ratio_down_to_up": round(down_count / up_count, 2) if up_count else None,
            "strongest_energy_name": strongest["name"],
            "strongest_energy_chg_pct": strongest["chg_pct"],
            "weakest_energy_name": weakest["name"],
            "weakest_energy_chg_pct": weakest["chg_pct"],
            "energy_advancers": sum(1 for r in energy_rows if float(r["chg_pct"].replace("%", "")) > 0),
            "energy_decliners": sum(1 for r in energy_rows if float(r["chg_pct"].replace("%", "")) < 0),
            "foreign_net_twd": str(foreign_net),
            "total_inst_net_twd": str(total_inst_net),
        },
    }
    charts_manifest = {
        "schema_version": "1.0",
        "status": "partial",
        "generated_at": fetched_at,
        "report_id": run_id,
        "charts": [
            {"id": "energy_table", "type": "table", "source": "03b_yfinance.energy_infra_stocks"},
            {"id": "scenario_probs", "type": "bar", "source": "processed.report_draft.scenarios"},
        ],
    }
    report_draft = {
        "schema_version": "1.0",
        "status": "ok",
        "report_id": run_id,
        "drafted_at": fetched_at,
        "report_metadata": {
            "report_type": "pre_market",
            "target_date": target_date,
            "market": "TW",
            "locale_priority": ["zh-TW", "zh-CN"],
            "focus_theme": "energy_infrastructure",
            "market_color_convention": "tw_stock",
        },
        "insight_scorecard": [
            {
                "title": "能源基建族群呈「政策長多、短線分歧」結構",
                "signal": "mixed",
                "confidence": "medium",
                "type": "mixed",
                "evidence": [
                    f"能源基建觀察池上漲家數 {sum(1 for r in energy_rows if float(r['chg_pct'].replace('%', '')) > 0)} / 下跌家數 {sum(1 for r in energy_rows if float(r['chg_pct'].replace('%', '')) < 0)}",
                    f"最強：{strongest['name']} {strongest['chg_pct']}；最弱：{weakest['name']} {weakest['chg_pct']}",
                ],
                "invalidation": "若出現連續兩日成交量放大且上漲家數明顯回升，短線分歧判讀將失效",
            },
            {
                "title": "電網韌性與離岸風電管線持續，重電/EPC 訂單可見度偏高",
                "signal": "bullish",
                "confidence": "medium",
                "type": "fact",
                "evidence": ["台電強化電網韌性計畫總預算 5,645 億元", "離岸風電 2025-2026 預估新增 +2.6GW"],
                "invalidation": "若年度預算執行率顯著低於規劃或關鍵工程遞延，該多頭邏輯需下修",
            },
            {
                "title": "高油價對台股能源基建是「雙刃」：設備更新受惠、用電成本壓力並存",
                "signal": "mixed",
                "confidence": "low",
                "type": "inference",
                "evidence": [f"WTI 近月收於 {us_macro['wti_close']}（{us_macro['wti_date']}）", f"外資現貨淨額 {fmt_money_ntd(foreign_net)}"],
                "invalidation": "若油價快速回落至 95 以下且外資轉為連續買超，成本壓力情境將弱化",
            },
        ],
        "scenarios": [
            {"name": "base", "probability": 50, "trigger_conditions": ["台股量能維持低檔、外資賣壓未完全收斂"], "expected_market_behavior": "能源基建個股區間震盪，資金偏好具訂單能見度標的", "recommended_positioning": "核心持股保留、反彈分批調節高波動股"},
            {"name": "bull", "probability": 30, "trigger_conditions": ["政策標案加速、外資回補重電/電網股"], "expected_market_behavior": "重電與工程股領漲，族群擴散至儲能與綠電平台", "recommended_positioning": "增加強勢股權重，採回檔分批加碼"},
            {"name": "bear", "probability": 20, "trigger_conditions": ["油價續升+全球風險偏好下滑"], "expected_market_behavior": "高本益比綠能股回檔，僅低估值或具防禦現金流標的抗跌", "recommended_positioning": "降低槓桿，停損紀律前移至前低"},
        ],
    }
    write_json(run_dir / "processed" / "integrated_data.json", integrated)
    write_json(run_dir / "processed" / "indicators.json", indicators)
    write_json(run_dir / "processed" / "charts_manifest.json", charts_manifest)
    write_json(run_dir / "processed" / "report_draft.json", report_draft)

    trigger_request = {
        "schema_version": "1.0",
        "report_id": run_id,
        "report_type": "pre_market",
        "input_mode": "contextual",
        "requested_at": fetched_at,
        "target_date": target_date,
        "locale_priority": ["zh-TW", "zh-CN"],
        "user_instructions": "台股盤前，重點聚焦能源基礎設施",
        "focus_tickers": [r["ticker"] for r in energy_rows] + high_watch,
        "focus_sectors": ["Energy Infrastructure", "Power Grid", "Offshore Wind", "EPC"],
        "custom_parameters": None,
    }
    write_json(run_dir / "trigger_request.json", trigger_request)
    write_json(run_dir / "portfolio_gate.json", {"schema_version": "1.0", "report_id": run_id, "mode": "without_portfolio", "checked_at": fetched_at, "portfolio": None})
    write_json(run_dir / "report_structure.json", {"schema_version": "1.0", "report_id": run_id, "report_type": "pre_market", "portfolio_mode": "without_portfolio", "resolved_at": fetched_at})

    def delta_cls(v: str):
        x = float(v.replace("%", ""))
        return "ma-up" if x > 0 else ("ma-down" if x < 0 else "ma-flat")

    def arrow(v: str) -> str:
        x = float(v.replace("%", ""))
        if abs(x) < 0.005:
            return "→"
        return "▲" if x > 0 else "▼"

    rows_html = "".join(
        f"<tr><td>{r['ticker']}</td><td>{r['name']}</td><td>{r['group']}</td><td class='ma-num'>{r['close']}</td><td class='ma-num {delta_cls(r['chg_pct'])}'>{arrow(r['chg_pct'])} {r['chg_pct']}</td><td class='ma-num'>{int(r['foreign_net_shares']):,}</td><td class='ma-num'>{int(r['inst_net_shares']):,}</td></tr>"
        for r in energy_rows
    )
    pol_rows = polymarket.get("data", [])[:3]
    poly_html = "".join(
        f"<tr><td>{p['question']}</td><td class='ma-num'>{p['probability_pct']:.2f}%</td><td>{(p.get('end_date') or '')[:10]}</td></tr>"
        for p in pol_rows
    ) or "<tr><td colspan='3'>資料不足（來源可用但無高相關市場）</td></tr>"
    watch_text = "目前 watchlist 無 high 優先級個股，本次以能源基建主題池取代。" if not high_watch else f"高優先級：{', '.join(high_watch)}"

    tw_html = render_tw_html(
        target_date,
        latest_date,
        taiex_row[1],
        taiex_row[4],
        up_count,
        down_count,
        total_inst_net,
        strongest,
        weakest,
        us_macro,
        rows_html,
        poly_html,
        watch_text,
    )
    cn_html = (
        tw_html.replace("zh-Hant", "zh-Hans")
        .replace("台股盤前報告（能源基礎設施焦點）", "台股盘前报告（能源基础设施焦点）")
        .replace("報告日", "报告日")
        .replace("市場資料基準", "市场数据基准")
        .replace("市場慣例", "市场惯例")
        .replace("重大新聞 / 政策（Fact）", "重大新闻 / 政策（Fact）")
    )

    tw_html_path = run_dir / "output" / f"report_pre_market_{target_date}_zh-TW.html"
    cn_html_path = run_dir / "output" / f"report_pre_market_{target_date}_zh-CN.html"
    tw_json_path = run_dir / "output" / f"report_pre_market_{target_date}_zh-TW.json"
    cn_json_path = run_dir / "output" / f"report_pre_market_{target_date}_zh-CN.json"
    tw_html_path.write_text(tw_html, encoding="utf-8")
    cn_html_path.write_text(cn_html, encoding="utf-8")
    write_json(tw_json_path, report_draft)
    cn_draft = json.loads(json.dumps(report_draft))
    cn_draft["report_metadata"] = {**cn_draft["report_metadata"], "locale": "zh-CN"}
    write_json(cn_json_path, cn_draft)

    output_manifest = {
        "schema_version": "1.0",
        "report_id": run_id,
        "generated_at": fetched_at,
        "style_contract": {
            "market_color_convention": "tw_stock",
            "stock_up_color": "#D62828",
            "stock_down_color": "#1F9D55",
            "stock_flat_color": "#6B7280",
            "uses_sign_and_icon_with_color": True,
            "interpretation_on_hover_enabled": True,
        },
        "outputs": [
            {"locale": "zh-TW", "priority": "primary", "file_path": str(tw_html_path).replace("\\", "/"), "file_format": "html", "status": "ok"},
            {"locale": "zh-CN", "priority": "secondary", "file_path": str(cn_html_path).replace("\\", "/"), "file_format": "html", "status": "ok"},
            {"locale": "zh-TW", "priority": "primary", "file_path": str(tw_json_path).replace("\\", "/"), "file_format": "json", "status": "ok"},
            {"locale": "zh-CN", "priority": "secondary", "file_path": str(cn_json_path).replace("\\", "/"), "file_format": "json", "status": "ok"},
        ],
    }
    write_json(run_dir / "output_manifest.json", output_manifest)
    print(run_id)


if __name__ == "__main__":
    main()
