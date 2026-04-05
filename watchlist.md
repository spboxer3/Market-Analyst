---
name: watchlist
description: 市场观察名单，供 market-analyst skill 在生成报告时读取。
last_updated: 2026-04-05
---

# Watchlist 观察名单

> 这个文件由 `market-analyst` skill 读取，用于生成报告时加入重点追踪标的。

## 观察名单表格

| Ticker | Name | Market | Priority | Notes | Added Date |
|--------|------|--------|----------|-------|------------|
| 2344 | 2344 | Taiwan Equity | high |  | 2026-04-05 |

## 优先级说明

- `high`: 报告中重点追踪，纳入个股追踪卡片与相关数据抓取。
- `medium`: 正常追踪，视上下文决定展示方式。
- `low`: 仅在出现异常波动、放量或催化事件时展示。

## 常用操作

| 操作 | 示例 |
|------|------|
| 加入观察名单 | `加入 TSMC 到观察名单` / `watchlist add NVDA` |
| 移除观察名单 | `从观察名单移除 AAPL` / `watchlist remove AAPL` |
| 显示观察名单 | `显示我的观察名单` / `watchlist show` |
| 更新优先级 | `把 TSMC 优先级改为 high` |
| 清空观察名单 | `watchlist clear` |
| 更新备注 | `NVDA 备注：追踪 GTC 后续催化` |
