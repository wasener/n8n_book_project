# 第二冊 第一章｜1.3 應用案例：「呷早頓」早餐店 POS 點餐系統

《n8n 自動化工作流程：進階篇》第一章 1.3 節的範例檔案，已在 **n8n 3.0.0**（Docker 自架）實際匯入、執行與驗證。

## 資料夾結構

```text
chapter1/
├── workflows/
│   ├── 1.3-呷早頓早餐店POS點餐系統.json          書中範例（原版）
│   └── 1.3-呷早頓早餐店POS點餐系統_錄影用.json   錄影／示範用複本（見下方說明）
├── test-data/
│   ├── test_order.json                          測試訂單（與 pinned data 相同）
│   └── test_order_badphone.json                 負面測試：phone 為 "0912"
└── scripts/
    ├── make_demo_copy.py                        由原版產生錄影用複本
    ├── record_demo.py                           Selenium＋ffmpeg 自動操作並錄製示範影片
    └── selenium_tools/                          檢查畫面、盤點 data-test-id 用的輔助程式
```

## 工作流程內容

一個工作流程裡有兩條互相獨立的流程：

| 流程 | 觸發 | 節點 |
|---|---|---|
| 點餐主流程 | Webhook `POST /qiaozaodun-order` | 接收點餐訂單 → 訂單驗證與清洗 → 營業時段判斷（IF）→ 品項金額計算 → LINE 廚房通知 → 回傳訂單確認；IF 的 false 分支 → 非營業時間回應（HTTP 422） |
| 日結流程 | Schedule Trigger 每日 11:30 | 日結排程 11:30 → 取得當日訂單（模擬 6 筆）→ 日結統計計算 → 寫入日結報表（Google Sheets） |

工作流程時區設為 `Asia/Taipei`，營業時間為每日 06:00～10:59。

## 匯入

**CLI**（已實測）：要先在瀏覽器建立 owner 帳號。

```powershell
docker cp "workflows\1.3-呷早頓早餐店POS點餐系統.json" <容器名稱>:/tmp/wf.json
docker exec <容器名稱> n8n import:workflow --input=/tmp/wf.json
docker exec -u root <容器名稱> rm -f /tmp/wf.json   # docker cp 進去的檔案屬於 root，要用 -u root 才刪得掉
```

**介面：** 用編輯器選單的 Import from File 匯入。n8n 3.0 已經拿掉 Import from URL。

## 設定憑證

匯入後有兩個節點需要換成你自己的憑證與 ID：

| 節點 | 憑證類型 | 要換掉的預留值 |
|---|---|---|
| LINE 廚房通知 | Header Auth：Name `Authorization`，Value `Bearer <Channel access token>` | JSON 中的 `YOUR_LINE_GROUP_ID_HERE`。user ID（U 開頭）或群組 ID（C 開頭）都可以 |
| 寫入日結報表 | Google Sheets OAuth2 API | Document 的 `YOUR_GOOGLE_SHEETS_ID_HERE`。試算表需有名為「日結報表」的工作表，第 1 列依序為：日期、總訂單數、完成訂單、取消訂單、完成率(%)、總營收(NT$)、平均客單價(NT$)、最高單筆(NT$)、最低單筆(NT$)、前5大品項、產生時間 |

> **注意：** 範例 JSON 裡引用的憑證只是示範名稱。換成自己的憑證之前，n8n 3.0 會把執行資料遮蔽起來（Output data redacted），打開節點也看不到輸出。
>
> 沒有憑證也想把流程跑完，可以用 `make_demo_copy.py --disable-external` 產生停用這兩個節點的複本。

## 測試

### 編輯器內執行

在「接收點餐訂單」上按 **Execute workflow**（已內建 pinned data），主要輸出如下：

| 節點 | 欄位 | 預期值 |
|---|---|---|
| 訂單驗證與清洗 | customerName／phone | `王小明`（前後空白已去除）／`0912345678` |
| 品項金額計算 | validItems 筆數 | 2（qty=0 的奶油吐司被濾除） |
| | subtotal／totalWithTax／formattedTotal | `140`／`147`／`NT$147` |
| | pickupCode／orderTimeFormatted | `03150042`／`07:23` |

在「日結排程 11:30」上按 **Execute workflow** 執行日結流程：

| 欄位 | 預期值 |
|---|---|
| totalCount／completedCount／cancelledCount | `6`／`5`／`1` |
| completionRate | `83` |
| totalRevenue／avgOrderValue | `630`／`126` |
| maxAmount／minAmount | `210`／`63` |
| topItems 前兩名 | 總匯蛋餅 4 份 NT$220、培根起司堡 2 份 NT$130 |

### 實際 HTTP 呼叫

右上角按 **Publish** 發布後，送出測試訂單：

```powershell
curl.exe -s -w "`nHTTP %{http_code}`n" -H "Content-Type: application/json; charset=utf-8" --data-binary "@test-data\test_order.json" http://localhost:5678/webhook/qiaozaodun-order
```

在 Windows PowerShell 5.1 請用 `curl.exe --data-binary` 送出，避免中文變成亂碼。

## 已知問題（n8n 3.0.0 實測）

1. **原版用實際 HTTP 呼叫會回 HTTP 500。**
   - Webhook 節點實際接收請求時，訂單放在 `$json.body` 裡；pinned data 卻是扁平格式，所以只有在編輯器內執行時正常。
   - 錄影用複本已修正：「訂單驗證與清洗」改成 `const order = item.json.body ?? item.json;`。修正後，正常訂單回 HTTP 200，電話格式錯誤的訂單回 HTTP 500，錯誤訊息為「電話格式不正確」。
2. **n8n 3.0 沒有 Active 開關，改為 Publish／Unpublish。**
   - 修改會自動存成草稿，發布後再修改要重新 Publish，正式網址與排程才會套用新版本。
   - 取消發布：Publish 按鈕旁的選單 → Unpublish。
3. **原版的營業時段判斷是 06:00～10:59。** 其他時間執行，會走 false 分支回應「非營業時間」。錄影用複本把條件改成 0～23，任何時間都會走主流程。

## 錄影用複本與錄影腳本

### 錄影用複本

由原版用 `make_demo_copy.py` 產生，只做以下調整：

1. 名稱加上「【錄影用】」。
2. 營業時段改成 0～23。
3. Webhook 路徑改成 `qiaozaodun-order-demo`，避免與原版衝突。
4. （選用）停用 LINE 與 Google Sheets 節點。
5. 加入上面「已知問題 1」的修正。

```powershell
python scripts\make_demo_copy.py "workflows\1.3-呷早頓早餐店POS點餐系統.json" "workflows\1.3-呷早頓早餐店POS點餐系統_錄影用.json"
```

### 錄影腳本 `record_demo.py`

**需求**

- 僅限 Windows：使用 ffmpeg 的 gdigrab 錄整個主螢幕。
- Google Chrome。
- Python 套件：`selenium`（4.6 以上，由 Selenium Manager 自動下載對應版本的 ChromeDriver）、`imageio`、`imageio-ffmpeg`、`pillow`。

**步驟**

1. 第一次使用：執行 `python scripts\selenium_tools\sel_launch.py`，在開啟的 Chrome（設定檔放在 `chrome-profile\`）登入 n8n 後關閉。
2. 先只做準備確認畫面：`python scripts\record_demo.py --workflow-id <ID> --setup-only check.png`
3. 正式錄影：`python scripts\record_demo.py --workflow-id <ID> --exec-id <production execution ID>`
   - 錄影約 2 分鐘，期間不要操作滑鼠鍵盤。
   - 產出的影片在 `output\qiaozaodun_n8n3_demo.mp4`，逐步截圖在 `output\screenshots\`。
   - 會實際推播 1 則 LINE，並在試算表新增 1 列。

`output\` 和 `chrome-profile\` 已列在 `.gitignore`。`chrome-profile\` 內含 n8n 的登入狀態，請不要上傳。

## 驗證環境

n8n 3.0.0（`n8nio/n8n:3.0.0`）、Google Chrome 158、Python 3.15、Windows 11，驗證於 2026 年 11 月。
