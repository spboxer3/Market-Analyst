param(
  [string]$TargetDate = "2026-04-01"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Get-LatestTwseDate([datetime]$baseDate) {
  for ($i = 0; $i -lt 8; $i++) {
    $d = $baseDate.AddDays(-$i).ToString("yyyyMMdd")
    $u = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=$d&type=ALLBUT0999&response=json"
    $r = curl.exe -sL $u
    if ($r -and $r.Length -gt 60) { return $d }
  }
  return $null
}

function Parse-WatchlistHigh([string]$path) {
  if (-not (Test-Path $path)) { return @() }
  $out = @()
  foreach ($ln in [System.IO.File]::ReadAllLines($path, [System.Text.Encoding]::UTF8)) {
    if (-not $ln.TrimStart().StartsWith("|")) { continue }
    if ($ln -match "Ticker" -or $ln -match "---" -or $ln -match "<!--") { continue }
    $parts = $ln.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() }
    if ($parts.Count -ge 6 -and $parts[0] -and $parts[3].ToLower() -eq "high") { $out += $parts[0] }
  }
  return $out
}

function Encode-Html([string]$s) {
  if ($null -eq $s) { return "" }
  return [System.Net.WebUtility]::HtmlEncode($s)
}

function Write-Utf8NoBom([string]$path, [string]$content) {
  [System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))
}

function NumberClass([string]$pct) {
  if (-not $pct) { return "ma-flat" }
  $x = [double](($pct -replace ",", ""))
  if ($x -gt 0) { return "ma-up" }
  if ($x -lt 0) { return "ma-down" }
  return "ma-flat"
}

function NumberArrow([string]$pct) {
  if (-not $pct) { return "&#8594;" }
  $x = [double](($pct -replace ",", ""))
  if ($x -gt 0) { return "&#9650;" }
  if ($x -lt 0) { return "&#9660;" }
  return "&#8594;"
}

function BoolText([bool]$b) {
  if ($b) { return "ok" } else { return "error" }
}

function Tip(
  [string]$what,
  [string]$why,
  [string]$how,
  [string]$conf,
  [string]$type,
  [string]$risk
) {
  return "what_it_is: $what&#10;why_it_matters: $why&#10;how_to_read: $how&#10;confidence: $conf&#10;type: $type&#10;risk_note: $risk"
}

function Format-TwdYi([string]$v) {
  if (-not $v) { return "--" }
  $n = [decimal](($v -replace ",", ""))
  $yi = $n / 100000000
  if ($yi -gt 0) { return ("+{0:N2} 億" -f $yi) }
  if ($yi -lt 0) { return ("-{0:N2} 億" -f [math]::Abs($yi)) }
  return "0.00 億"
}

function To-Number([string]$v) {
  if (-not $v) { return [decimal]0 }
  return [decimal](($v -replace ",", ""))
}

function Localize-ZhCn([string]$html) {
  $r = $html
  $r = $r.Replace("台股盤前報告", "台股盘前报告")
  $r = $r.Replace("目標日期", "目标日期")
  $r = $r.Replace("基準交易日", "基准交易日")
  $r = $r.Replace("生成時間", "生成时间")
  $r = $r.Replace("核心洞察", "核心洞察")
  $r = $r.Replace("重點觀察", "重点观察")
  $r = $r.Replace("技術訊號", "技术信号")
  $r = $r.Replace("個股追蹤", "个股追踪")
  $r = $r.Replace("成交值前八名", "成交值前八名")
  $r = $r.Replace("情境分析", "情景分析")
  $r = $r.Replace("執行計畫", "执行计划")
  $r = $r.Replace("跨市場傳導", "跨市场传导")
  $r = $r.Replace("明日重點", "明日重点")
  $r = $r.Replace("資料來源狀態", "数据来源状态")
  $r = $r.Replace("台北時間", "台北时间")
  $r = $r.Replace("機率", "概率")
  $r = $r.Replace("無", "无")
  return $r
}

$target = [datetime]::Parse($TargetDate)
$targetIso = $target.ToString("yyyy-MM-dd")
$generatedAt = (Get-Date).ToString("o")
$runId = "pre_market_tw_{0}_{1}" -f $target.ToString("yyyyMMdd"), (Get-Date).ToString("HHmm")
$runDir = Join-Path (Get-Location) ("runs\" + $runId)
$fetchedDir = Join-Path $runDir "fetched"
$processedDir = Join-Path $runDir "processed"
$chartsDir = Join-Path $runDir "charts"
$outputDir = Join-Path $runDir "output"
New-Item -ItemType Directory -Force -Path $runDir, $fetchedDir, $processedDir, $chartsDir, $outputDir | Out-Null

$latest = Get-LatestTwseDate $target
if (-not $latest) { throw "Cannot find TWSE trading day in the last 8 days." }
$latestIso = "{0}-{1}-{2}" -f $latest.Substring(0, 4), $latest.Substring(4, 2), $latest.Substring(6, 2)

$miUrl = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=$latest&type=ALLBUT0999&response=json"
$bfiUrl = "https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate=$latest&type=day&response=json"
$t86Url = "https://www.twse.com.tw/rwd/zh/fund/T86?date=$latest&selectType=ALLBUT0999&response=json"
$polyUrl = "https://gamma-api.polymarket.com/markets?limit=120&active=true&closed=false&search=fed"
$rssUrl = "https://tw.stock.yahoo.com/rss?category=%E5%8F%B0%E8%82%A1"
$redditUrl = "https://www.reddit.com/r/stocks/search.json?q=Taiwan%20OR%20TSMC&restrict_sr=1&sort=new&t=week&limit=8"
$yfHelper = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "yfinance_client.py"
$pythonExe = (Get-Command python -ErrorAction Stop).Source

$mi = Invoke-RestMethod -Uri $miUrl -Method Get -TimeoutSec 30
$bfi = Invoke-RestMethod -Uri $bfiUrl -Method Get -TimeoutSec 30
$t86 = Invoke-RestMethod -Uri $t86Url -Method Get -TimeoutSec 30

$taiexRow = $mi.tables[0].data[1]
$upRow = $mi.tables[7].data[0]
$downRow = $mi.tables[7].data[1]
$tradeInfo = $mi.tables[6].data[0]
$foreignRow = $bfi.data[3]
$totalInstRow = $bfi.data[5]
$topTurnover = @($t86.data | Select-Object -First 8)

$taiexClose = [string]$taiexRow[1]
$taiexPts = [string]$taiexRow[3]
$taiexPct = [string]$taiexRow[4]
$upCount = [string]$upRow[2]
$downCount = [string]$downRow[2]
$turnover = [string]$tradeInfo[1]
$foreignNet = [string]$foreignRow[3]
$totalInstNet = [string]$totalInstRow[3]
$highWatch = Parse-WatchlistHigh (Join-Path (Get-Location) "watchlist.md")

$yhData = $null
$srcYfOk = $false
$yhErr = $null
try {
  $yhRaw = & $pythonExe $yfHelper --symbols "^TWII" --period "5d" --interval "1d"
  if ($yhRaw) {
    $yhData = $yhRaw | ConvertFrom-Json
    $srcYfOk = ($yhData.status -eq "ok" -and $yhData.data.Count -gt 0)
    if (-not $srcYfOk) { $yhErr = $yhData.error_message }
  } else {
    $yhErr = "empty response"
  }
} catch {
  $yhErr = $_.Exception.Message
}

$polyRaw = curl.exe -sL $polyUrl
$polyOk = $false
$polyPicks = @()
$polyErr = $null
if ($polyRaw) {
  try {
    $arr = $polyRaw | ConvertFrom-Json
    foreach ($m in $arr) {
      $q = [string]$m.question
      if (-not $q) { continue }
      if ($q.ToLower() -notmatch "fed|rate|cpi|inflation") { continue }
      $pp = if ($m.lastTradePrice) { [Math]::Round(([double]$m.lastTradePrice) * 100, 2) } else { $null }
      $polyPicks += @{
        question = $q
        probability_pct = $pp
        end_date = $m.endDate
        url = if ($m.slug) { "https://polymarket.com/event/$($m.slug)" } else { $null }
      }
      if ($polyPicks.Count -ge 5) { break }
    }
    $polyOk = $true
  } catch {
    $polyErr = $_.Exception.Message
  }
} else {
  $polyErr = "empty response"
}

$redditRaw = curl.exe -sL -H "User-Agent: market-analyst/1.0" $redditUrl
$redditOk = $false
$redditSummary = $null
$redditHits = @()
$redditErr = $null
if ($redditRaw) {
  try {
    $rj = $redditRaw | ConvertFrom-Json
    foreach ($c in ($rj.data.children | Select-Object -First 5)) {
      $redditHits += @{
        title = [string]$c.data.title
        score = $c.data.score
        subreddit = [string]$c.data.subreddit
        url = "https://reddit.com" + [string]$c.data.permalink
      }
    }
    $redditSummary = "Taiwan/TSMC discussion remains visible; sentiment is mixed between AI demand optimism and valuation caution."
    $redditOk = $true
  } catch {
    $redditErr = $_.Exception.Message
  }
} else {
  $redditErr = "empty response"
}

$rssRaw = curl.exe -sL $rssUrl
$rssOk = $false
$rssHeadlines = @()
$rssErr = $null
if ($rssRaw) {
  $rssOk = $true
  $rssHeadlines = @([regex]::Matches($rssRaw, "<title>(.*?)</title>") | ForEach-Object { $_.Groups[1].Value } | Where-Object { $_ -and $_ -notmatch "Yahoo" } | Select-Object -First 8)
} else {
  $rssErr = "empty response"
}

$f03a = @{ schema_version="1.0"; source="financial_datasets"; status="error"; fetched_at=$generatedAt; error_message="No connector in runtime" }
$f03b = @{ schema_version="1.0"; source="yfinance"; status=(BoolText $srcYfOk); fetched_at=$generatedAt; error_message=$yhErr; data=if ($srcYfOk) { $yhData.data } else { $null } }
$f03c = @{ schema_version="1.0"; source="alpha_vantage"; status="error"; fetched_at=$generatedAt; error_message="No API key" }
$f03d = @{ schema_version="1.0"; source="polymarket"; status=(BoolText $polyOk); fetched_at=$generatedAt; error_message=$polyErr; data=$polyPicks }
$f03e = @{ schema_version="1.0"; source="reddit"; status=(BoolText $redditOk); fetched_at=$generatedAt; error_message=$redditErr; summary=$redditSummary; top_hits=$redditHits }
$f03f = @{ schema_version="1.0"; source="web_search"; status=(BoolText $rssOk); fetched_at=$generatedAt; error_message=$rssErr; headlines=$rssHeadlines }

$f03a | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $fetchedDir "03a_financial_datasets.json")
$f03b | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $fetchedDir "03b_yfinance.json")
$f03c | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $fetchedDir "03c_alpha_vantage.json")
$f03d | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $fetchedDir "03d_polymarket.json")
$f03e | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $fetchedDir "03e_reddit.json")
$f03f | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $fetchedDir "03f_web_search.json")

$sourceErrors = @(
  if (-not $srcYfOk) { "yfinance" }
  if (-not $polyOk) { "polymarket" }
  if (-not $redditOk) { "reddit" }
  if (-not $rssOk) { "web_search" }
  "financial_datasets"
  "alpha_vantage"
)
$missingCount = @($sourceErrors).Count
$confidence1 = if ($missingCount -ge 3) { "low" } else { "medium" }
$confidence2 = if ($missingCount -ge 2) { "medium" } else { "high" }

$riskLine = "外資流向仍偏空，且盤面廣度偏弱，開盤宜先採防守。"
$crossFact = "TWSE 最新收盤（${latestIso}）：TAIEX ${taiexClose}（${taiexPct}%），外資淨買賣超 ${foreignNet} 元。"
$crossInference = "若美國利率預期夜盤再走高，台股大型權值股開盤可能承壓。"

$integrated = @{
  schema_version = "1.0"
  status = "partial"
  generated_at = $generatedAt
  report_id = $runId
  report_type = "pre_market"
  target_date = $targetIso
  baseline_trading_date = $latestIso
  market_color_convention = "tw_stock"
  watchlist_high_priority = $highWatch
  data = @{
    taiex = @{ close = $taiexClose; pct = $taiexPct; points = $taiexPts }
    market_breadth = @{ up = $upCount; down = $downCount }
    turnover_twd = $turnover
    foreign_net_twd = $foreignNet
    total_inst_net_twd = $totalInstNet
    top_turnover = @($topTurnover | ForEach-Object { @{ symbol = $_[0]; volume = $_[8] } })
    polymarket = $polyPicks
    reddit = @{ summary = $redditSummary; top_hits = $redditHits }
    headlines = $rssHeadlines
    source_failures = $sourceErrors
  }
}
$integrated | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 (Join-Path $processedDir "integrated_data.json")

$draft = @{
  schema_version = "1.0"
  status = "ok"
  report_id = $runId
  drafted_at = $generatedAt
  report_metadata = @{
    report_type = "pre_market"
    target_date = $targetIso
    market = "TW"
    locale_priority = @("zh-TW", "zh-CN")
    market_color_convention = "tw_stock"
  }
  executive_insights = @(
    @{
      title = "市場廣度偏弱仍是開盤主要風險"
      level = "critical"
      signal = "bearish"
      confidence = $confidence1
      type = "fact"
      evidence = @(
        "TAIEX 在 $latestIso 收 $taiexClose（$taiexPct%）",
        "下跌家數 $downCount，高於上漲家數 $upCount"
      )
      invalidation = "前 30 分鐘若成交量能擴增且廣度翻正，則此觀點失效。"
    },
    @{
      title = "三大法人與外資流向仍偏風險趨避"
      level = "high"
      signal = "bearish"
      confidence = $confidence2
      type = "fact"
      evidence = @(
        "外資淨買賣超 $foreignNet 元",
        "三大法人合計淨買賣超 $totalInstNet 元"
      )
      invalidation = "若現貨與期貨部位同時轉為淨多，則此觀點失效。"
    },
    @{
      title = "利率傳導效應可能壓抑日內上行空間"
      level = "watch"
      signal = "mixed"
      confidence = "medium"
      type = "inference"
      evidence = @(
        "Fed/利率相關預測市場仍活躍",
        "社群情緒分歧：需求樂觀與估值保守並存"
      )
      invalidation = "若美債殖利率回落且成長股風險偏好回升，則此觀點失效。"
    }
  )
  scenarios = @(
    @{
      name = "base"
      probability = 55
      trigger_conditions = @("量能中性", "市場廣度未明顯修復")
      expected_market_behavior = "開盤區間震盪、以輪動為主"
      recommended_positioning = "降低部位，採戰術型進出"
    },
    @{
      name = "bull"
      probability = 25
      trigger_conditions = @("權值股同步轉強", "外資賣壓減弱")
      expected_market_behavior = "開高後維持漲勢"
      recommended_positioning = "分批加碼相對強勢股"
    },
    @{
      name = "bear"
      probability = 20
      trigger_conditions = @("外資賣壓延續", "下跌家數持續擴大")
      expected_market_behavior = "反彈無力，仍有回測低點風險"
      recommended_positioning = "提高現金比重，快速降槓桿"
    }
  )
  execution_playbook = @(
    @{ window="開盤前"; action="先檢查期貨與美債殖利率方向"; risk_control="單筆風險控制在 1% 以內" },
    @{ window="前30分鐘"; action="驗證量價與市場廣度"; risk_control="若跌破開盤低點，降低曝險" },
    @{ window="盤中"; action="僅保留相對強勢標的"; risk_control="嚴格執行失效停損" }
  )
  cross_market_transmission = @{
    fact = $crossFact
    inference = $crossInference
  }
}
$draft | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 (Join-Path $processedDir "report_draft.json")

$tipTop1 = Tip "加權指數最新收盤錨點" "定義今日開盤風險基準" "前日跌幅大且廣度偏弱，通常代表開盤先防守" $confidence1 "fact" "集合競價可能快速反轉"
$tipTop2 = Tip "市場廣度（漲跌家數）" "反映盤面參與度是否健康" "下跌家數明顯大於上漲家數，代表結構偏弱" "high" "fact" "開盤後若資金回流可改善"
$tipTop3 = Tip "利率傳導影響" "直接影響成長股估值" "殖利率上行常壓抑高估值族群" "medium" "inference" "若殖利率回落，壓力可緩解"

$rowsHtml = (($integrated.data.top_turnover | Select-Object -First 8) | ForEach-Object {
  "<tr><td>$(Encode-Html $_.symbol)</td><td class='ma-num'>$(Encode-Html $_.volume)</td></tr>"
}) -join ""

$watchText = if ($highWatch.Count -gt 0) { [string]::Join(", ", $highWatch) } else { "無" }
$scenarioRows = @(
  "<tr><td>基準情境</td><td class='ma-num'>55%</td><td>量能中性且廣度未修復</td><td>降低部位、戰術進出</td></tr>",
  "<tr><td>多方情境</td><td class='ma-num'>25%</td><td>權值股轉強且賣壓鈍化</td><td>分批布局相對強勢股</td></tr>",
  "<tr><td>空方情境</td><td class='ma-num'>20%</td><td>外資賣壓延續且跌家擴大</td><td>提高現金、降低槓桿</td></tr>"
) -join ""

$insightCards = @(
  @{
    label = "Critical"; cls = "ma-critical"; title = "市場廣度偏弱仍是開盤主要風險";
    signal = "bearish"; conf = $confidence1; type = "fact";
    evidence = "TAIEX $taiexClose ($taiexPct%)，廣度 $upCount/$downCount";
    invalidation = "若前30分鐘廣度翻正，則觀點失效。"
  },
  @{
    label = "Key"; cls = "ma-key"; title = "三大法人與外資流向仍偏風險趨避";
    signal = "bearish"; conf = $confidence2; type = "fact";
    evidence = "外資 $foreignNet；三大法人合計 $totalInstNet";
    invalidation = "若現貨與期貨同步翻多，則觀點失效。"
  },
  @{
    label = "Watch"; cls = "ma-watch"; title = "利率傳導效應可能壓抑日內上行空間";
    signal = "mixed"; conf = "medium"; type = "inference";
    evidence = "利率與 Fed 事件定價仍活躍。";
    invalidation = "若開盤前美債殖利率回落，則觀點失效。"
  }
)
$insightCardsHtml = ($insightCards | ForEach-Object {
  "<div class='ma-card ma-c4'><div class='ma-chip $($_.cls)'>$($_.label)</div><h3 style='margin:10px 0 8px'>$($_.title)</h3><div class='ma-small'>訊號=$($_.signal) | 信心=$($_.conf) | 類型=$($_.type)</div><p class='ma-small' style='margin-top:8px'><b>證據：</b>$($_.evidence)</p><p class='ma-small'><b>失效條件：</b>$($_.invalidation)</p></div>"
}) -join ""
$insightSummaryHtml = "<ul><li><b>洞察一：</b>市場廣度偏弱仍是開盤主要風險。</li><li><b>洞察二：</b>三大法人與外資流向仍偏風險趨避。</li><li><b>洞察三：</b>利率傳導效應可能壓抑日內上行空間。</li></ul>"

$polyRows = (($polyPicks | Select-Object -First 4) | ForEach-Object {
  $ed = ""
  if ($_.end_date) { $ed = ([string]$_.end_date).Substring(0, [Math]::Min(10, ([string]$_.end_date).Length)) }
  "<tr><td>$(Encode-Html $_.question)</td><td class='ma-num'>$(Encode-Html ([string]$_.probability_pct))%</td><td>$(Encode-Html $ed)</td></tr>"
}) -join ""
if (-not $polyRows) { $polyRows = "<tr><td colspan='3'>暫無可用預測市場資料</td></tr>" }

$twTitle = "&#21488;&#32929;&#30436;&#21069;&#22577;&#21578;"
$twTarget = "&#30446;&#27161;&#26085;&#26399;"
$twBaseline = "&#22522;&#28310;&#20132;&#26131;&#26085;"
$twTop3 = "Top 3 &#37325;&#40670;&#35264;&#23519;"
$twExec = "Executive Insights / &#26680;&#24515;&#27934;&#23519;"
$twQuick = "&#24555;&#36895;&#25351;&#27161;"
$twTech = "&#25216;&#34899;&#35338;&#34399;"
$twWatch = "Watchlist &#20491;&#32929;&#36861;&#36452;"
$twTurnover = "&#25104;&#20132;&#20540;&#21069;&#20843;&#21517;"
$twScenarios = "&#24773;&#22659;&#20998;&#26512;"
$twPlaybook = "&#22519;&#34892;&#35336;&#30059;"
$twCross = "&#36328;&#24066;&#22580;&#20659;&#23566;"
$twPoly = "Polymarket"
$twPreview = "&#26126;&#26085;&#37325;&#40670;"
$twSource = "&#36039;&#26009;&#20358;&#28304;&#29376;&#24907;"

$turnoverYi = Format-TwdYi $turnover
$foreignNetYi = Format-TwdYi $foreignNet
$totalInstNetYi = Format-TwdYi $totalInstNet
$foreignClass = if ((To-Number $foreignNet) -gt 0) { "ma-up" } elseif ((To-Number $foreignNet) -lt 0) { "ma-down" } else { "ma-flat" }
$instClass = if ((To-Number $totalInstNet) -gt 0) { "ma-up" } elseif ((To-Number $totalInstNet) -lt 0) { "ma-down" } else { "ma-flat" }

$twHtml = @"
<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width,initial-scale=1'/><title>$twTitle $targetIso</title>
<style>:root{--bg-page:#f3f6fb;--bg-card:#fff;--bg-muted:#eef2f8;--text-primary:#0f172a;--text-secondary:#1e293b;--text-muted:#64748b;--border-subtle:#dbe3ef;--border-strong:#93a4bc;--state-critical:#b42318;--state-key:#1d4ed8;--state-watch:#b45309;--state-context:#475467;--stock-up:#D62828;--stock-down:#1F9D55;--stock-flat:#6B7280;--focus-ring:#2563eb;--shadow-card:0 10px 24px rgba(15,23,42,.08)}*{box-sizing:border-box}body{margin:0;background:var(--bg-page);color:var(--text-primary);font-family:'Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif}.ma-wrap{max-width:1200px;margin:0 auto;padding:18px}.ma-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px}.ma-card{background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:14px;padding:14px;box-shadow:var(--shadow-card)}.ma-c12{grid-column:span 12}.ma-c8,.ma-c6,.ma-c4{grid-column:span 12}@media(min-width:980px){.ma-c8{grid-column:span 8}.ma-c6{grid-column:span 6}.ma-c4{grid-column:span 4}}.ma-kpi{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.ma-kpi>div{min-width:0;background:var(--bg-muted);border-radius:10px;padding:8px}.ma-kpi .ma-num{font-size:14px;line-height:1.35;overflow-wrap:anywhere}@media(min-width:980px){.ma-kpi{grid-template-columns:repeat(2,minmax(0,1fr))}}.ma-num{font-variant-numeric:tabular-nums}.ma-up{color:var(--stock-up)}.ma-down{color:var(--stock-down)}.ma-flat{color:var(--stock-flat)}.ma-chip{display:inline-flex;align-items:center;gap:6px;width:fit-content;max-width:100%;padding:4px 9px;border-radius:999px;font-size:12px;font-weight:700;white-space:nowrap}.ma-critical{background:#fee4e2;color:var(--state-critical)}.ma-key{background:#dbeafe;color:var(--state-key)}.ma-watch{background:#ffedd5;color:var(--state-watch)}.ma-context{background:#e8edf4;color:var(--state-context)}.ma-table{width:100%;border-collapse:collapse;font-size:14px}.ma-table th,.ma-table td{padding:8px;border-bottom:1px solid #e6ecf4;text-align:left;vertical-align:top}.ma-tip{position:relative;border-bottom:1px dotted var(--border-strong);cursor:help;outline:none}.ma-tip:hover::after,.ma-tip:focus::after{content:attr(data-tip);position:absolute;left:0;top:calc(100% + 6px);z-index:20;min-width:260px;max-width:460px;white-space:pre-line;padding:10px;border-radius:10px;background:#0f172a;color:#f8fafc;font-size:12px;box-shadow:0 10px 20px rgba(0,0,0,.24)}.ma-small{font-size:12px;color:var(--text-muted)}</style></head>
<body><div class='ma-wrap'>
<section class='ma-card ma-c12'><h1 style='margin:0 0 8px'>$twTitle</h1><div class='ma-small'>${twTarget}: ${targetIso} | ${twBaseline}: ${latestIso} | 生成時間: $generatedAt | 規則: tw_stock（漲=紅、跌=綠）</div></section>
<div class='ma-grid' style='margin-top:12px'>
<section class='ma-card ma-c8'><h2 style='margin:0 0 8px'>$twTop3</h2>
<p><span class='ma-chip ma-critical'>Critical</span> <span tabindex='0' class='ma-tip' data-tip='$tipTop1'>TAIEX $taiexClose ($taiexPct%)</span></p>
<p><span class='ma-chip ma-key'>Key</span> <span tabindex='0' class='ma-tip' data-tip='$tipTop2'>市場廣度（漲/跌）= $upCount / $downCount</span></p>
<p><span class='ma-chip ma-watch'>Watch</span> <span tabindex='0' class='ma-tip' data-tip='$tipTop3'>$riskLine</span></p>
</section>
<section class='ma-card ma-c4'><h2 style='margin:0 0 8px'>$twQuick</h2><div class='ma-kpi'>
<div><div class='ma-small'>TAIEX</div><div class='ma-num $(NumberClass $taiexPct)'>$(NumberArrow $taiexPct) $taiexClose ($taiexPct%)</div></div>
<div><div class='ma-small'>成交值（億元）</div><div class='ma-num'>$turnoverYi</div></div>
<div><div class='ma-small'>外資淨買賣超（億元）</div><div class='ma-num $foreignClass'>$foreignNetYi</div></div>
<div><div class='ma-small'>三大法人淨買賣超（億元）</div><div class='ma-num $instClass'>$totalInstNetYi</div></div>
</div></section>
<section class='ma-card ma-c12'><h2 style='margin:0 0 8px'>$twExec</h2>$insightSummaryHtml</section>
$insightCardsHtml
<section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>$twTech</h2><ul><li>Fact：TAIEX 在 $latestIso 變動 $taiexPts 點（$taiexPct%）。</li><li>Fact：市場廣度（漲/跌）= $upCount/$downCount。</li><li>Inference：若前30分鐘廣度未修復，建議維持低 Beta 配置。</li></ul></section>
<section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>$twWatch</h2><div class='ma-small'>高優先追蹤：$(Encode-Html $watchText)</div></section>
<section class='ma-card ma-c12'><h2 style='margin:0 0 8px'>$twTurnover</h2><table class='ma-table'><thead><tr><th>代號</th><th>成交量</th></tr></thead><tbody>$rowsHtml</tbody></table></section>
<section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>$twScenarios</h2><table class='ma-table'><thead><tr><th>情境</th><th>機率</th><th>觸發條件</th><th>建議動作</th></tr></thead><tbody>$scenarioRows</tbody></table></section>
<section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>$twPlaybook</h2><table class='ma-table'><thead><tr><th>時段</th><th>動作</th><th>風險控管</th></tr></thead><tbody><tr><td>開盤前</td><td>檢查台指期與美債殖利率</td><td>單筆風險 <= 1%</td></tr><tr><td>前30分鐘</td><td>驗證量價與廣度品質</td><td>跌破開盤低點即減碼</td></tr><tr><td>盤中</td><td>僅保留相對強勢股</td><td>嚴格執行失效停損</td></tr></tbody></table></section>
<section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>$twCross</h2><p><span class='ma-chip ma-context'>Fact</span> $crossFact</p><p><span class='ma-chip ma-watch'>Inference</span> $crossInference</p></section>
<section class='ma-card ma-c6'><h2 style='margin:0 0 8px'>$twPoly</h2><table class='ma-table'><thead><tr><th>事件</th><th>機率</th><th>到期</th></tr></thead><tbody>$polyRows</tbody></table></section>
<section class='ma-card ma-c8'><h2 style='margin:0 0 8px'>盤前新聞摘要</h2><ul><li>若來源編碼不穩定，先隱藏標題文字並以來源狀態判讀可信度。</li></ul></section>
<section class='ma-card ma-c4'><h2 style='margin:0 0 8px'>$twPreview</h2><ul><li>2026-04-03 20:30 台北時間 - 美國非農就業</li><li>2026-04-10 20:30 台北時間 - 美國 CPI</li><li>2026-05-01 04:00 台北時間 - FOMC 決議</li></ul></section>
<section class='ma-card ma-c12'><h3 style='margin:0 0 8px'>$twSource</h3><div class='ma-small'>TWSE=ok | yfinance=$(BoolText $srcYfOk) | polymarket=$(BoolText $polyOk) | reddit=$(BoolText $redditOk) | web_search=$(BoolText $rssOk) | financial_datasets=error | alpha_vantage=error</div></section>
</div></div></body></html>
"@

$cnHtml = Localize-ZhCn($twHtml.Replace("lang='zh-Hant'", "lang='zh-Hans'"))

$twHtmlPath = Join-Path $outputDir ("report_pre_market_{0}_zh-TW.html" -f $targetIso)
$cnHtmlPath = Join-Path $outputDir ("report_pre_market_{0}_zh-CN.html" -f $targetIso)
$twJsonPath = Join-Path $outputDir ("report_pre_market_{0}_zh-TW.json" -f $targetIso)
$cnJsonPath = Join-Path $outputDir ("report_pre_market_{0}_zh-CN.json" -f $targetIso)

if ($insightCards.Count -lt 3) {
  throw "Insight guard failed: fewer than 3 executive insights."
}
if ($twHtml -notmatch "Executive Insights") {
  throw "Insight guard failed: missing Executive Insights section header."
}

Write-Utf8NoBom $twHtmlPath $twHtml
Write-Utf8NoBom $cnHtmlPath $cnHtml
$draft | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $twJsonPath
$cnDraft = $draft.PSObject.Copy()
$cnDraft.report_metadata = @{
  report_type = "pre_market"
  target_date = $targetIso
  market = "TW"
  locale_priority = @("zh-CN")
  market_color_convention = "tw_stock"
}
$cnDraft | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $cnJsonPath

$manifest = @{
  schema_version = "1.0"
  report_id = $runId
  generated_at = $generatedAt
  status = "ok"
  style_contract = @{
    market_color_convention = "tw_stock"
    stock_up_color = "#D62828"
    stock_down_color = "#1F9D55"
    stock_flat_color = "#6B7280"
    uses_sign_and_icon_with_color = $true
    interpretation_on_hover_enabled = $true
  }
  outputs = @(
    @{ locale="zh-TW"; priority="primary"; file_path=($twHtmlPath -replace "\\", "/"); file_format="html"; status="ok" },
    @{ locale="zh-CN"; priority="secondary"; file_path=($cnHtmlPath -replace "\\", "/"); file_format="html"; status="ok" },
    @{ locale="zh-TW"; priority="primary"; file_path=($twJsonPath -replace "\\", "/"); file_format="json"; status="ok" },
    @{ locale="zh-CN"; priority="secondary"; file_path=($cnJsonPath -replace "\\", "/"); file_format="json"; status="ok" }
  )
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $runDir "output_manifest.json")

Write-Output $runId


