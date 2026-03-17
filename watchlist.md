---
name: watchlist
description: 使用者自訂的關注個股清單，市場報告生成時會優先抓取並分析這些標的
last_updated: 2026-03-17
---

# Watchlist — 自訂關注個股

> 本檔案由 market-analyst skill 管理。報告生成時會自動讀取此清單，為關注個股提供額外的盤勢預估與技術分析。

## 關注個股清單

<!-- 每個個股一行，請勿刪除表頭 -->

| Ticker | 名稱 | 板塊 | 優先級 | 關注原因 | 加入日期 |
|--------|------|------|--------|----------|----------|
<!-- 範例（取消註解即可使用）: -->
<!-- | TSMC | 台積電 ADR | Semiconductors | high | 核心持倉，AI 晶片供應鏈龍頭 | 2026-03-17 | -->
<!-- | AAPL | Apple | Technology | medium | 長期觀察，iPhone 換機週期 | 2026-03-17 | -->
<!-- | NVDA | NVIDIA | Semiconductors | high | GTC 大會後追蹤 AI 需求展望 | 2026-03-17 | -->

## 優先級說明

- **high**：每份報告必須包含該標的的獨立分析段落（盤勢預估、技術訊號、近期催化劑）
- **medium**：報告中提及相關板塊時一併分析，不需獨立段落
- **low**：僅在有重大新聞或異常波動時才納入報告

## 管理指令

使用以下自然語言即可管理此清單（透過 market-analyst skill）：

| 操作 | 範例指令 |
|------|----------|
| 新增個股 | `加入 TSMC 到關注清單` 或 `watchlist add NVDA` |
| 移除個股 | `從關注清單移除 AAPL` 或 `watchlist remove AAPL` |
| 查看清單 | `顯示我的關注清單` 或 `watchlist show` |
| 修改優先級 | `把 TSMC 的優先級改為 high` |
| 清空清單 | `清空關注清單` 或 `watchlist clear` |
| 新增備註 | `NVDA 備註：關注 GTC 後法說會指引` |
