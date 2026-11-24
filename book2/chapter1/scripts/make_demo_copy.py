"""從書中範例工作流程產生【錄影用】複本。

用法（在 chapter1 資料夾執行）：
  python scripts\\make_demo_copy.py workflows\\1.3-呷早頓早餐店POS點餐系統.json workflows\\1.3-呷早頓早餐店POS點餐系統_錄影用.json
  加上 --disable-external：停用「LINE 廚房通知」「寫入日結報表」，沒有憑證也能完整跑完
  （停用的節點會把輸入原樣往下傳）。

對原版只做以下調整：
  1. name 加上「【錄影用】」前綴
  2. 「營業時段判斷」rightValue 6／10 → 0／23，任何時間都會走主流程的 true 分支
  3. Webhook path／webhookId 改成 qiaozaodun-order-demo／qiaozaodun-pos-demo，避免與原版衝突
  4. （選用）停用 LINE 與 Google Sheets 節點
  5. 「訂單驗證與清洗」改讀 item.json.body ?? item.json：
     實際 HTTP 呼叫時，Webhook 節點把訂單放在 body 裡；編輯器的 pinned data 則是扁平格式
"""
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--disable-external", action="store_true", help="停用 LINE 廚房通知與寫入日結報表")
args = ap.parse_args()

src, dst = Path(args.src), Path(args.dst)
wf = json.loads(src.read_text(encoding="utf-8"))
nodes = {n["name"]: n for n in wf["nodes"]}

# 1. 名稱
wf["name"] = "【錄影用】呷早頓早餐店 POS 點餐系統"

# 2. 營業時段判斷：6 → 0、10 → 23
conds = nodes["營業時段判斷"]["parameters"]["conditions"]["conditions"]
by_id = {c["id"]: c for c in conds}
assert by_id["cond-gte-6"]["rightValue"] == 6
assert by_id["cond-lte-10"]["rightValue"] == 10
by_id["cond-gte-6"]["rightValue"] = 0
by_id["cond-lte-10"]["rightValue"] = 23

# 3. Webhook 路徑與 webhookId
wh = nodes["接收點餐訂單"]
assert wh["parameters"]["path"] == "qiaozaodun-order"
wh["parameters"]["path"] = "qiaozaodun-order-demo"
wh["webhookId"] = "qiaozaodun-pos-demo"

# 4.（選用）停用需要外部憑證的兩個節點
if args.disable_external:
    nodes["LINE 廚房通知"]["disabled"] = True
    nodes["寫入日結報表"]["disabled"] = True

# 5. 訂單驗證與清洗：實際 Webhook 呼叫時訂單在 body 裡
code = nodes["訂單驗證與清洗"]["parameters"]["jsCode"]
OLD = "const order = item.json;"
assert code.count(OLD) == 1
nodes["訂單驗證與清洗"]["parameters"]["jsCode"] = code.replace(
    OLD,
    "// 實際 HTTP 呼叫時訂單包在 body 裡；編輯器的 pinned data 則沒有這一層\n"
    "const order = item.json.body ?? item.json;")

dst.write_text(json.dumps(wf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("written", dst, "nodes:", len(wf["nodes"]))
