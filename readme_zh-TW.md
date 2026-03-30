# Market Analyst

一個 Claude Code 技能，用於生成結構化的美股市場分析報告。透過 7 階段管線從 6 個數據來源平行抓取資料，處理後輸出繁體中文 / 簡體中文的本地化報告。

## 這次修改的重點

- 預設先產生 HTML dashboard
- 自動標註重要資訊，不再所有資訊同權重
- 明確區分「直接來源事實」與「模型推論」
- 保留 JSON 中間產物供稽核
- PDF 只作為次要輸出或匯出格式

## 主要輸出契約

每次報告執行後，預設應產出：

- `output/report_<type>_<date>_<locale>.html`
- `processed/report_draft.json`
- 可選：`output/report_<type>_<date>_<locale>.md`
- 可選：`output/report_<type>_<date>_<locale>.pdf`

其中 `HTML dashboard` 是主要給人閱讀的成品。

## 重要資訊標註規則

報告內的重要點必須至少分成這幾級：

- `Critical`
- `Key`
- `Watch`
- `Context`

至少要標出：

- 前 3 大市場重點
- 下一個最重要的總經事件
- 下一交易日或下一週最大的風險
- 最強或最弱的主要指數 / 產業 / 關注股
- 所有屬於推論的句子

## UI 版面要求

HTML dashboard 應該預設包含：

1. 報告標題與市場日期
2. Top 3 takeaways 區塊
3. 主要指數 / 關鍵數據摘要列
4. 新聞、技術面、watchlist、產業、預測市場、社群情緒等卡片區塊
5. 未來事件與催化劑區
6. Sources / Methodology 區塊

不要再預設輸出成一整頁長文字。

## Watchlist 呈現規則

`watchlist.md` 仍然是 persistent watchlist。

優先級對應輸出方式：

- `high`：獨立分析卡片
- `medium`：摘要表格列
- `low`：只有異常波動、重大新聞或重要催化劑時才顯示

## 設計要求

介面必須：

- 支援桌機與手機閱讀
- 使用卡片、表格、標籤與 callout
- 不能只是把 markdown 原樣包成 HTML
- 要讓人一眼看出資訊層級

## 樣式與股票顏色規範

- 報告必須使用統一 design tokens（背景、文字、邊框、狀態標籤、漲跌色）。
- 漲跌顏色必須依市場慣例切換，不可全域固定：
- 台股（`tw_stock`）：漲=紅、跌=綠、平盤=灰
- 美股（`us_stock`）：漲=綠、跌=紅、平盤=灰
- 同一份報告若同時包含台股與美股（`mixed`），必須在各區塊顯示對應 legend。
- 不可只用顏色表達漲跌，需同時顯示 `+/-`、`▲/▼/→` 或文字方向標籤。
- 重要數值與訊號需支援 hover/tap 解讀（這是什麼、為何重要、如何解讀、信心度、風險提示）。

## 資料來源

- Financial Datasets
- yfinance
- Alpha Vantage
- Polymarket
- Reddit
- Web search
