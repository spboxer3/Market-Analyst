#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from yfinance_client import fetch_quotes

TZ = ZoneInfo("Asia/Taipei")


def fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def cls(value: float) -> str:
    if value > 0:
        return "ma-up"
    if value < 0:
        return "ma-down"
    return "ma-flat"


def arrow(value: float) -> str:
    if value > 0:
        return "▲"
    if value < 0:
        return "▼"
    return "→"


def zh_cn(text: str) -> str:
    pairs = [
        ("盤後報告", "盘后报告"),
        ("目標日期", "目标日期"),
        ("注意", "注意"),
        ("為", "为"),
        ("休市", "休市"),
        ("本報告", "本报告"),
        ("收盤", "收盘"),
        ("宏觀事件", "宏观事件"),
        ("基線", "基线"),
        ("科技與小型股較強", "科技与小盘股较强"),
        ("下一個交易日", "下一个交易日"),
        ("板塊", "板块"),
        ("最強", "最强"),
        ("個股追蹤", "个股追踪"),
        ("未直接納入", "未直接纳入"),
        ("結論", "结论"),
        ("盤前", "盘前"),
        ("盤中", "盘中"),
        ("風險", "风险"),
    ]
    for a, b in pairs:
        text = text.replace(a, b)
    return text


def build_report(target_date: str):
    quotes = fetch_quotes(
        [
            "^GSPC",
            "^DJI",
            "^IXIC",
            "^RUT",
            "^VIX",
            "CL=F",
            "DX-Y.NYB",
            "AAPL",
            "MSFT",
            "NVDA",
            "AMZN",
            "TSLA",
            "META",
            "GOOGL",
            "XLE",
            "XLK",
            "XLF",
            "XLV",
            "XLI",
            "XLY",
            "XLP",
            "XLU",
            "XLRE",
            "XLB",
            "XLC",
        ],
        period="5d",
        interval="1d",
    )
    rows = {item["symbol"]: item for item in quotes["data"]}

    def pct(symbol: str) -> float:
        return float(rows[symbol]["change_pct"])

    session_note = (
        "2026-04-03 為 Good Friday，美股休市；本報告以 2026-04-02 收盤與 2026-04-03 宏觀事件為基線。"
        if target_date == "2026-04-03"
        else f"{target_date} 的現貨收盤資料為本次盤後報告基線。"
    )

    sectors = [
        ("XLRE 房地產", pct("XLRE")),
        ("XLK 科技", pct("XLK")),
        ("XLP 必需消費", pct("XLP")),
        ("XLU 公用事業", pct("XLU")),
        ("XLE 能源", pct("XLE")),
        ("XLC 通訊", pct("XLC")),
        ("XLF 金融", pct("XLF")),
        ("XLB 原物料", pct("XLB")),
        ("XLI 工業", pct("XLI")),
        ("XLV 醫療", pct("XLV")),
        ("XLY 非必需消費", pct("XLY")),
    ]
    sectors.sort(key=lambda x: x[1], reverse=True)

    mega = [
        ("MSFT", pct("MSFT")),
        ("NVDA", pct("NVDA")),
        ("AAPL", pct("AAPL")),
        ("AMZN", pct("AMZN")),
        ("GOOGL", pct("GOOGL")),
        ("META", pct("META")),
        ("TSLA", pct("TSLA")),
    ]
    mega.sort(key=lambda x: x[1], reverse=True)

    report = {
        "schema_version": "1.0",
        "status": "ok",
        "drafted_at": datetime.now(TZ).isoformat(),
        "report_metadata": {
            "report_type": "post_market",
            "target_date": target_date,
            "market": "US",
            "market_color_convention": "us_stock",
            "session_note": session_note,
            "locale_priority": ["zh-TW", "zh-CN"],
        },
        "executive_insights": [
            {
                "title": "4 月 3 日美股休市，這份盤後解讀必須回看 4 月 2 日正式收盤。",
                "level": "critical",
                "signal": "neutral",
                "confidence": "high",
                "type": "fact",
                "evidence": [
                    "NYSE 2026 holiday calendar lists Friday, April 3, 2026 as Good Friday.",
                    "美股現貨休市，但 4 月 3 日非農與期貨走勢仍影響 4 月 6 日開盤預期。",
                ],
                "invalidation": "若使用者只想看假日當天新聞摘要而非盤後市場基線，才需要改寫報告框架。",
            },
            {
                "title": "4 月 2 日收盤結構偏向科技與小型股修復，Dow 相對偏弱。",
                "level": "high",
                "signal": "bullish",
                "confidence": "medium",
                "type": "fact",
                "evidence": [
                    f"Nasdaq {rows['^IXIC']['regular_market_price']} ({fmt_pct(pct('^IXIC'))})。",
                    f"Russell 2000 {rows['^RUT']['regular_market_price']} ({fmt_pct(pct('^RUT'))})。",
                    f"S&P 500 {rows['^GSPC']['regular_market_price']} ({fmt_pct(pct('^GSPC'))})，Dow {rows['^DJI']['regular_market_price']} ({fmt_pct(pct('^DJI'))})。",
                ],
                "invalidation": "若 4 月 6 日開盤 Russell 與 Nasdaq 同步失守相對強度，這個修復敘事就會失效。",
            },
            {
                "title": "強非農與高油價並存，下一個交易日更像利率與能源衝擊的再定價測試。",
                "level": "watch",
                "signal": "mixed",
                "confidence": "medium",
                "type": "mixed",
                "evidence": [
                    "BLS 公布 2026 年 3 月非農新增 178,000、失業率 4.3%。",
                    f"WTI {rows['CL=F']['regular_market_price']} ({fmt_pct(pct('CL=F'))})。",
                    f"DXY {rows['DX-Y.NYB']['regular_market_price']} ({fmt_pct(pct('DX-Y.NYB'))})。",
                ],
                "invalidation": "若油價快速回落且利率預期重新轉鴿，對成長股估值的壓力會顯著下降。",
            },
        ],
        "scenarios": [
            {
                "name": "base",
                "probability": 50,
                "trigger_conditions": [
                    "假日期間沒有新增地緣升級。",
                    "非農被市場解讀為成長韌性，而不是更鷹派的政策壓力。",
                ],
                "expected_market_behavior": "S&P 與 Nasdaq 延續震盪偏強，能源與消費可選分化。",
                "recommended_positioning": "維持中性偏多，優先保留科技龍頭與相對強勢 ETF。",
            },
            {
                "name": "bull",
                "probability": 25,
                "trigger_conditions": [
                    "油價與美元在 4 月 6 日開盤前降溫。",
                    "期貨跌幅收斂，科技與小型股領先轉強。",
                ],
                "expected_market_behavior": "Nasdaq 與 S&P 延續 4 月 2 日的修復行情。",
                "recommended_positioning": "順勢加碼強勢科技股，停損放在開盤區間低點下方。",
            },
            {
                "name": "bear",
                "probability": 25,
                "trigger_conditions": [
                    "油價續強、美元續升。",
                    "市場把強非農解讀成延後寬鬆的壓力。",
                ],
                "expected_market_behavior": "4 月 6 日出現風險偏好降溫，長久期成長股承壓。",
                "recommended_positioning": "提高現金比重，減碼弱勢高 beta 與可選消費。",
            },
        ],
        "execution_playbook": [
            {
                "window": "post_holiday_premarket",
                "action": "先用 4 月 2 日收盤結構當作基線，不要把 4 月 3 日休市新聞誤當成現貨確認。",
                "risk_control": "避免因假日新聞流而追單邊方向。",
            },
            {
                "window": "monday_open",
                "action": "觀察 Nasdaq 與 Russell 是否延續相對強勢，並留意 XLY 是否繼續弱於防禦板塊。",
                "risk_control": "若油價與美元同步上行，快速收縮總曝險。",
            },
            {
                "window": "first_90_minutes",
                "action": "只有在市場廣度跟上時才加碼，否則以觀察和低槓桿應對。",
                "risk_control": "以開盤區間低點或 ETF VWAP 失守作為失效點。",
            },
        ],
        "cross_market_transmission": {
            "fact": "4 月 3 日美股現貨休市，但非農、美元與油價的變化會直接傳導到 4 月 6 日的開盤定價。",
            "inference": "若強勞動市場搭配高油價延續，市場更可能先重定價利率與通膨風險，再決定是否延續科技股修復。",
        },
        "quick_stats": {
            "sp500": {"close": rows["^GSPC"]["regular_market_price"], "pct": pct("^GSPC")},
            "dow": {"close": rows["^DJI"]["regular_market_price"], "pct": pct("^DJI")},
            "nasdaq": {"close": rows["^IXIC"]["regular_market_price"], "pct": pct("^IXIC")},
            "russell2000": {"close": rows["^RUT"]["regular_market_price"], "pct": pct("^RUT")},
            "vix": {"close": rows["^VIX"]["regular_market_price"], "pct": pct("^VIX")},
            "wti": {"close": rows["CL=F"]["regular_market_price"], "pct": pct("CL=F")},
            "dxy": {"close": rows["DX-Y.NYB"]["regular_market_price"], "pct": pct("DX-Y.NYB")},
        },
        "sector_table": [{"sector": name, "pct": value} for name, value in sectors],
        "leaders_laggards": [{"ticker": ticker, "pct": value} for ticker, value in mega],
        "source_links": [
            {"title": "NYSE 2026 Holiday Calendar", "url": "https://www.nyse.com/markets/hours-calendars?os=svergi"},
            {"title": "BLS Employment Situation - 2026 M03 Results", "url": "https://www.bls.gov/news.release/archives/empsit_04032026.htm"},
            {"title": "AP: Wall Street closed for Good Friday, but US futures inch lower following strong March jobs report", "url": "https://apnews.com/article/cbf38b67032e2fae95073f4fbcc0ca24"},
            {"title": "AP: Stocks recover from early losses and close with a weekly gain. US oil tops $110 a barrel", "url": "https://apnews.com/article/6fc90a2e50b1252cde130fc3e0ce0da3"},
            {"title": "AP: How major US stock indexes fared Thursday 4/2/2026", "url": "https://apnews.com/article/a61cf10b1c2630e3f41aa9592356c472"},
        ],
    }
    return report


def render_html(report: dict) -> str:
    qs = report["quick_stats"]
    sectors = report["sector_table"]
    mega = report["leaders_laggards"]
    insights = report["executive_insights"]
    sector_rows = "".join(
        f"<tr><td>{row['sector']}</td><td class='ma-num {cls(row['pct'])}'>{arrow(row['pct'])} {fmt_pct(row['pct'])}</td></tr>"
        for row in sectors
    )
    mega_rows = "".join(
        f"<tr><td>{row['ticker']}</td><td class='ma-num {cls(row['pct'])}'>{arrow(row['pct'])} {fmt_pct(row['pct'])}</td></tr>"
        for row in mega
    )
    source_rows = "".join(
        f"<li><a href='{row['url']}' target='_blank' rel='noreferrer'>{row['title']}</a></li>"
        for row in report["source_links"]
    )
    insight_cards = "".join(
        f"<div class='ma-card ma-c4'><div class='ma-chip {'ma-critical' if i['level']=='critical' else ('ma-key' if i['level']=='high' else 'ma-watch')}'>{i['level'].title()}</div><h3>{i['title']}</h3><div class='ma-small'>signal={i['signal']} | confidence={i['confidence']} | type={i['type']}</div><p class='ma-small'><b>Evidence:</b> {' '.join(i['evidence'])}</p><p class='ma-small'><b>Invalidation:</b> {i['invalidation']}</p></div>"
        for i in insights
    )
    return f"""<!doctype html>
<html lang='zh-Hant'>
<head>
<meta charset='utf-8'/>
<meta name='viewport' content='width=device-width,initial-scale=1'/>
<title>美股盤後報告 {report['report_metadata']['target_date']}</title>
<style>:root{{--bg-page:#f3f6fb;--bg-card:#fff;--bg-muted:#eef2f8;--text-primary:#0f172a;--text-secondary:#1e293b;--text-muted:#64748b;--border-subtle:#dbe3ef;--border-strong:#93a4bc;--state-critical:#b42318;--state-key:#1d4ed8;--state-watch:#b45309;--state-context:#475467;--stock-up:#16A34A;--stock-down:#DC2626;--stock-flat:#6B7280;--shadow-card:0 10px 24px rgba(15,23,42,.08)}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(180deg,#eef4ff 0%,#f8fafc 60%,#eef2f8 100%);color:var(--text-primary);font-family:'Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif}}.ma-wrap{{max-width:1240px;margin:0 auto;padding:20px}}.ma-grid{{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px}}.ma-card{{background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:16px;padding:16px;box-shadow:var(--shadow-card)}}.ma-c12{{grid-column:span 12}}.ma-c8,.ma-c6,.ma-c4{{grid-column:span 12}}@media(min-width:980px){{.ma-c8{{grid-column:span 8}}.ma-c6{{grid-column:span 6}}.ma-c4{{grid-column:span 4}}}}.ma-chip{{display:inline-flex;align-items:center;gap:6px;width:fit-content;max-width:100%;padding:4px 9px;border-radius:999px;font-size:12px;font-weight:700;white-space:nowrap}}.ma-critical{{background:#fee4e2;color:var(--state-critical)}}.ma-key{{background:#dbeafe;color:var(--state-key)}}.ma-watch{{background:#ffedd5;color:var(--state-watch)}}.ma-context{{background:#e8edf4;color:var(--state-context)}}.ma-up{{color:var(--stock-up)}}.ma-down{{color:var(--stock-down)}}.ma-flat{{color:var(--stock-flat)}}.ma-num{{font-variant-numeric:tabular-nums}}.ma-kpi{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.ma-kpi>div{{background:var(--bg-muted);padding:10px;border-radius:12px}}@media(min-width:980px){{.ma-kpi{{grid-template-columns:repeat(4,minmax(0,1fr))}}}}.ma-table{{width:100%;border-collapse:collapse;font-size:14px}}.ma-table th,.ma-table td{{padding:8px;border-bottom:1px solid #e6ecf4;text-align:left;vertical-align:top}}.ma-small{{font-size:12px;color:var(--text-muted)}}</style>
</head>
<body><div class='ma-wrap'><section class='ma-card ma-c12'><h1 style='margin:0 0 8px'>美股盤後報告</h1><div class='ma-small'>目標日期：{report['report_metadata']['target_date']} | 注意：{report['report_metadata']['session_note']}</div></section><div class='ma-grid' style='margin-top:12px'><section class='ma-card ma-c8'><h2 style='margin:0 0 8px'>Top 3 Takeaways</h2><p><span class='ma-chip ma-critical'>Critical</span> 2026-04-03 是 Good Friday，美股休市，所以這份盤後報告屬於休市特別版。</p><p><span class='ma-chip ma-key'>Key</span> 4 月 2 日收盤顯示科技與小型股較強，Nasdaq {qs['nasdaq']['close']} ({fmt_pct(qs['nasdaq']['pct'])})、Russell 2000 {qs['russell2000']['close']} ({fmt_pct(qs['russell2000']['pct'])})。</p><p><span class='ma-chip ma-watch'>Watch</span> 強非農搭配高油價，意味 4 月 6 日開盤更像利率與能源風險的再定價測試。</p></section><section class='ma-card ma-c4'><h2 style='margin:0 0 8px'>Quick Stats</h2><div class='ma-kpi'><div><div class='ma-small'>S&P 500</div><div class='ma-num {cls(qs['sp500']['pct'])}'>{arrow(qs['sp500']['pct'])} {qs['sp500']['close']} ({fmt_pct(qs['sp500']['pct'])})</div></div><div><div class='ma-small'>Nasdaq</div><div class='ma-num {cls(qs['nasdaq']['pct'])}'>{arrow(qs['nasdaq']['pct'])} {qs['nasdaq']['close']} ({fmt_pct(qs['nasdaq']['pct'])})</div></div><div><div class='ma-small'>VIX</div><div class='ma-num {cls(-qs['vix']['pct'])}'>{arrow(qs['vix']['pct'])} {qs['vix']['close']} ({fmt_pct(qs['vix']['pct'])})</div></div><div><div class='ma-small'>WTI</div><div class='ma-num {cls(qs['wti']['pct'])}'>{arrow(qs['wti']['pct'])} {qs['wti']['close']} ({fmt_pct(qs['wti']['pct'])})</div></div></div></section><section class='ma-card ma-c12'><h2 style='margin:0 0 8px'>Executive Insights</h2></section>{insight_cards}<section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>Sector Heatmap</h2><table class='ma-table'><thead><tr><th>Sector</th><th>Daily Change</th></tr></thead><tbody>{sector_rows}</tbody></table></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>Mega-cap Movers</h2><table class='ma-table'><thead><tr><th>Ticker</th><th>Daily Change</th></tr></thead><tbody>{mega_rows}</tbody></table></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>Scenario Analysis</h2><table class='ma-table'><thead><tr><th>Scenario</th><th>Probability</th><th>Trigger</th><th>Action</th></tr></thead><tbody><tr><td>Base</td><td class='ma-num'>50%</td><td>假日期間未出現新一輪風險升級</td><td>中性偏多，保留科技與品質股</td></tr><tr><td>Bull</td><td class='ma-num'>25%</td><td>油價與美元回落</td><td>順勢加碼強勢科技</td></tr><tr><td>Bear</td><td class='ma-num'>25%</td><td>油價續強且市場重新定價利率</td><td>提高現金，減碼弱勢高 beta</td></tr></tbody></table></section><section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>Execution Playbook</h2><ul><li>先用 4 月 2 日收盤結構作為基線，不要把 4 月 3 日新聞流誤當現貨確認。</li><li>觀察 4 月 6 日開盤時 Nasdaq 和 Russell 是否延續相對強勢。</li><li>若油價與美元同步續強，優先降低高估值與高 beta 曝險。</li></ul></section><section class='ma-card ma-c8'><h2 style='margin:0 0 8px'>Cross-market Transmission</h2><p><span class='ma-chip ma-context'>Fact</span> 4 月 3 日美股休市，但非農、美元與油價變化會直接傳導到 4 月 6 日開盤。</p><p><span class='ma-chip ma-watch'>Inference</span> 若強勞動市場與高油價延續，市場會先重定價利率與通膨風險，再決定是否延續科技修復行情。</p></section><section class='ma-card ma-c4'><h2 style='margin:0 0 8px'>Watchlist 個股追蹤</h2><div class='ma-small'>目前高優先級 watchlist 為台股 2344，未直接納入本次美股盤後個股段落。</div></section><section class='ma-card ma-c12'><h3 style='margin:0 0 8px'>Sources</h3><ul>{source_rows}</ul></section></div></div></body></html>"""


def main():
    target_date = "2026-04-03"
    run_id = "post_market_us_20260405_1856"
    base = Path(__file__).resolve().parent.parent
    run = base / "runs" / run_id
    for folder in ["fetched", "processed", "charts", "output"]:
        (run / folder).mkdir(parents=True, exist_ok=True)

    report = build_report(target_date)
    report["report_id"] = run_id
    html = render_html(report)
    html_cn = zh_cn(html).replace("lang='zh-Hant'", "lang='zh-Hans'")

    tw_json = run / "output" / f"report_post_market_{target_date}_zh-TW.json"
    cn_json = run / "output" / f"report_post_market_{target_date}_zh-CN.json"
    tw_html = run / "output" / f"report_post_market_{target_date}_zh-TW.html"
    cn_html = run / "output" / f"report_post_market_{target_date}_zh-CN.html"
    draft_path = run / "processed" / "report_draft.json"
    manifest_path = run / "output_manifest.json"

    draft_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tw_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report_cn = json.loads(json.dumps(report, ensure_ascii=False))
    report_cn["report_metadata"]["locale"] = "zh-CN"
    cn_json.write_text(json.dumps(report_cn, ensure_ascii=False, indent=2), encoding="utf-8")
    tw_html.write_text(html, encoding="utf-8")
    cn_html.write_text(html_cn, encoding="utf-8")

    manifest = {
        "schema_version": "1.0",
        "report_id": run_id,
        "generated_at": report["drafted_at"],
        "status": "ok",
        "style_contract": {
            "market_color_convention": "us_stock",
            "stock_up_color": "#16A34A",
            "stock_down_color": "#DC2626",
            "stock_flat_color": "#6B7280",
            "uses_sign_and_icon_with_color": True,
            "interpretation_on_hover_enabled": False,
        },
        "outputs": [
            {"locale": "zh-TW", "priority": "primary", "file_path": str(tw_html).replace("\\", "/"), "file_format": "html", "status": "ok"},
            {"locale": "zh-CN", "priority": "secondary", "file_path": str(cn_html).replace("\\", "/"), "file_format": "html", "status": "ok"},
            {"locale": "zh-TW", "priority": "primary", "file_path": str(tw_json).replace("\\", "/"), "file_format": "json", "status": "ok"},
            {"locale": "zh-CN", "priority": "secondary", "file_path": str(cn_json).replace("\\", "/"), "file_format": "json", "status": "ok"},
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_id)


if __name__ == "__main__":
    main()
