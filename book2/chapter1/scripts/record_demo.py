"""呷早頓 POS × n8n 3.0 操作影片錄製腳本

做法
- Selenium 控制 Chrome（專用設定檔 chrome-profile，沿用使用者自己登入的狀態），視窗最大化
- imageio-ffmpeg 附帶的 ffmpeg 以 gdigrab 錄整個主螢幕（僅限 Windows）；結束時寫入 q 讓 MP4 正常收尾
- Selenium 的點擊不會移動系統游標 → 每次點擊前在目標外圍加 1 秒橘色外框；錄影時不畫游標
- 每個重要畫面停 2–3 秒，並用 driver.save_screenshot() 存到 output\\screenshots\\NN_說明.png

選擇器皆依 n8n 3.0.0 介面實際盤點的 data-test-id。

用法（在 chapter1 資料夾執行；workflow／execution ID 換成你自己 n8n 裡的值）：
  python scripts\\record_demo.py --workflow-id <錄影用工作流程 ID> --exec-id <要展示的 production execution ID>
  python scripts\\record_demo.py --workflow-id <ID> --setup-only check.png   # 只做準備、不錄影也不執行流程
注意：會實際執行主流程（推播 1 則 LINE）與日結流程（試算表新增 1 列）。
"""
import argparse
import ctypes
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

BASE = "http://localhost:5678"
ROOT = Path(__file__).resolve().parent.parent  # chapter1 資料夾；output\ 與 chrome-profile\ 都放這裡（已列入 .gitignore）
OUT = ROOT / "output"
SHOTS = OUT / "screenshots"
VIDEO = OUT / "qiaozaodun_n8n3_demo.mp4"
PROFILE = ROOT / "chrome-profile"
ORANGE = "#FF8C00"

T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:6.1f}s] {msg}", flush=True)


# ---------------------------------------------------------------- 錄影
def start_recording():
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "gdigrab", "-framerate", "20", "-draw_mouse", "0", "-i", "desktop",
           "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", str(VIDEO)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    time.sleep(1.5)  # 等 ffmpeg 開始擷取
    if proc.poll() is not None:
        raise RuntimeError("ffmpeg 啟動失敗")
    log("錄影開始")
    return proc


def stop_recording(proc):
    try:
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.stdin.close()
    except Exception:
        pass
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
    log(f"錄影結束（ffmpeg exit {proc.returncode}）")


# ---------------------------------------------------------------- 瀏覽器輔助
class Demo:
    def __init__(self, driver):
        self.d = driver
        self.n = 0

    def js(self, code, *args):
        return self.d.execute_script(code, *args)

    def pause(self, s):
        time.sleep(s)

    def shot(self, label):
        self.n += 1
        p = SHOTS / f"{self.n:02d}_{label}.png"
        self.d.save_screenshot(str(p))
        log(f"截圖 {p.name}")

    def visible(self, css, root=None):
        r = root or self.d
        return [e for e in r.find_elements(By.CSS_SELECTOR, css) if e.is_displayed()]

    def tid(self, test_id, root=None):
        els = self.visible(f'[data-test-id="{test_id}"]', root)
        if not els:
            raise RuntimeError(f"找不到 data-test-id={test_id}")
        return els[0]

    # 醒目外框：點擊前 1 秒
    def flash(self, el, secs=1.0):
        self.js("""const e = arguments[0];
                   e.dataset.demoOutline = e.style.outline || '';
                   e.dataset.demoOffset = e.style.outlineOffset || '';
                   e.style.outline = '4px solid %s'; e.style.outlineOffset = '2px';""" % ORANGE, el)
        time.sleep(secs)

    def unflash(self, el):
        try:
            self.js("""const e = arguments[0];
                       e.style.outline = e.dataset.demoOutline || ''; e.style.outlineOffset = e.dataset.demoOffset || '';""", el)
        except Exception:
            pass

    def click(self, el, secs=1.0):
        self.flash(el, secs)
        el.click()
        self.unflash(el)

    def dblclick(self, el, secs=1.0):
        self.flash(el, secs)
        ActionChains(self.d).double_click(el).perform()
        self.unflash(el)

    def dismiss_popups(self):
        for t in ("n8n-chat-hint-new_chat_sidebar-got-it", "banner-dynamic-banner-7-close"):
            for el in self.visible(f'[data-test-id="{t}"]'):
                try:
                    el.click(); time.sleep(0.4)
                except Exception:
                    pass
        # NPS 問卷或 Production Checklist 之類的浮窗：按 Esc
        if self.visible('[data-test-id="nps-survey-modal"]') or self.js(
                "return [...document.querySelectorAll('*')].some(e => e.offsetParent && "
                "(e.innerText||'').trim().startsWith('Production Checklist'))"):
            ActionChains(self.d).send_keys(Keys.ESCAPE).perform(); time.sleep(0.6)

    def close_checklist(self):
        """發布後開啟工作流程時會跳出 Production Checklist 浮窗；按它的關閉圖示（suggested-actions-close）。"""
        for x in self.visible('[data-test-id="suggested-actions-close"]'):
            x.click()
            return "closed"
        return None

    def wait_close_checklist(self, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            r = self.close_checklist()
            if r:
                time.sleep(0.4)
                return r
            time.sleep(0.15)
        return None

    def canvas_node(self, name):
        nodes = [n for n in self.d.find_elements(By.CSS_SELECTOR, '[data-test-id="canvas-node"]') if name in n.text]
        if len(nodes) != 1:
            raise RuntimeError(f"畫布節點 {name}：找到 {len(nodes)} 個")
        return nodes[0]

    def wait_node(self, name, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            n = self.canvas_node(name)
            for st in ("success", "error"):
                if n.find_elements(By.CSS_SELECTOR, f'[data-test-id="canvas-node-status-{st}"]'):
                    return st
            time.sleep(0.3)
        return "timeout"

    def execute_from(self, trigger):
        ActionChains(self.d).move_to_element(self.canvas_node(trigger)).perform()
        time.sleep(0.8)
        self.click(self.tid(f"execute-workflow-button-{trigger}"))

    def open_ndv(self, name):
        self.dblclick(self.canvas_node(name))
        time.sleep(2)

    def close_ndv(self):
        self.clear_boxes()
        self.click(self.tid("ndv-close-button"), 0.6)
        time.sleep(1)

    def output_mode(self, mode):
        out = self.tid("output-panel")
        self.click(self.tid(f"radio-button-{mode}", out), 0.8)
        time.sleep(1)
        return out

    def scroll_output(self, out, to="bottom", key=None):
        if key:
            self.js("""const leaf = [...arguments[0].querySelectorAll('*')].find(e => e.children.length === 0 &&
                         e.offsetParent && e.innerText.trim() === arguments[1]);
                       if (leaf) leaf.scrollIntoView({block: 'start', behavior: 'smooth'});""", out, key)
        else:
            self.js("""[...arguments[0].querySelectorAll('*')].filter(e => e.clientHeight > 0 &&
                         e.scrollHeight > e.clientHeight + 5 && ['auto','scroll'].includes(getComputedStyle(e).overflowY))
                       .forEach(s => s.scrollTo({top: s.scrollHeight, behavior: 'smooth'}));""", out)
        time.sleep(1.5)

    # 在 Schema 檢視中框出「欄位名稱 + 值」那一列
    def box_row(self, out, key, value):
        return self.js("""
            const [panel, key, val] = arguments;
            const leaf = [...panel.querySelectorAll('*')].find(e => e.children.length === 0 && e.offsetParent
                          && e.innerText.trim() === key);
            if (!leaf) return 'missing ' + key;
            let row = leaf;
            for (let i = 0; i < 6 && row.parentElement && !row.innerText.includes(val); i++) row = row.parentElement;
            const r = row.getBoundingClientRect();
            const b = document.createElement('div');
            b.className = 'demo-box';
            Object.assign(b.style, {position: 'fixed', left: (r.left - 4) + 'px', top: (r.top - 3) + 'px',
              width: (r.width + 8) + 'px', height: (r.height + 6) + 'px', border: '4px solid %s',
              borderRadius: '8px', pointerEvents: 'none', zIndex: 99999});
            document.body.appendChild(b);
            return 'ok';""" % ORANGE, out, key, value)

    # 框出從 start 文字到 end 文字之間的整段（虛擬清單沒有共同父節點，所以用座標畫框）
    def box_span(self, out, start, end):
        return self.js("""
            const [panel, start, end] = arguments;
            const leaves = [...panel.querySelectorAll('*')].filter(e => e.children.length === 0 && e.offsetParent);
            const a = leaves.find(e => e.innerText.trim() === start);
            if (!a) return 'missing ' + start;
            const ra = a.getBoundingClientRect();
            const b = leaves.filter(e => e.innerText.trim() === end && e.getBoundingClientRect().top >= ra.top)
                            .sort((x, y) => x.getBoundingClientRect().top - y.getBoundingClientRect().top)[0];
            if (!b) return 'missing ' + end;
            const rb = b.getBoundingClientRect(), rp = panel.getBoundingClientRect();
            const box = document.createElement('div');
            box.className = 'demo-box';
            Object.assign(box.style, {position: 'fixed', left: (ra.left - 10) + 'px', top: (ra.top - 6) + 'px',
              width: (rp.right - ra.left - 20) + 'px', height: (rb.bottom - ra.top + 12) + 'px',
              border: '4px solid %s', borderRadius: '10px', pointerEvents: 'none', zIndex: 99999});
            document.body.appendChild(box);
            return 'ok';""" % ORANGE, out, start, end)

    def clear_boxes(self):
        self.js("document.querySelectorAll('.demo-box').forEach(b => b.remove());")


def os_click_on(driver, el):
    """用真正的滑鼠點一下頁面元素，讓鍵盤焦點離開網址列（否則網址整段反白）。"""
    pos = driver.execute_script("""
        const r = arguments[0].getBoundingClientRect(), dpr = window.devicePixelRatio;
        const bx = (window.outerWidth - window.innerWidth) / 2;
        const by = window.outerHeight - window.innerHeight - bx;
        return [(window.screenX + bx + r.left + r.width / 2) * dpr, (window.screenY + by + r.top + r.height / 2) * dpr];""", el)
    u = ctypes.windll.user32
    u.SetCursorPos(int(pos[0]), int(pos[1])); time.sleep(0.2)
    u.mouse_event(0x0002, 0, 0, 0, 0); u.mouse_event(0x0004, 0, 0, 0, 0)  # 左鍵按下／放開
    time.sleep(0.4)
    u.SetCursorPos(1700, 15)  # 游標移到分頁列空白處，避免誤觸 hover
    return pos


def bring_to_front(driver):
    driver.minimize_window(); time.sleep(0.8)
    driver.maximize_window(); time.sleep(1.5)
    u = ctypes.windll.user32
    hwnd = u.FindWindowW(None, driver.title + " - Google Chrome")
    if hwnd and u.GetForegroundWindow() != hwnd:
        u.keybd_event(0x12, 0, 0, 0); u.keybd_event(0x12, 0, 2, 0)
        u.SetForegroundWindow(hwnd); time.sleep(1)
    return bool(hwnd) and u.GetForegroundWindow() == hwnd


# ---------------------------------------------------------------- 分鏡
def run(args):
    SHOTS.mkdir(parents=True, exist_ok=True)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    opts = Options()
    opts.add_argument(f"--user-data-dir={PROFILE}")
    opts.add_argument("--start-maximized")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])  # 去掉「受到自動測試軟體控制」
    opts.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=opts)  # 不指定路徑 → Selenium Manager（Chrome 158）
    demo = Demo(driver)
    rec = None
    try:
        driver.get(f"{BASE}/home/workflows")
        time.sleep(5)
        if "signin" in driver.current_url:
            raise RuntimeError("chrome-profile 尚未登入 n8n，請先在這個設定檔登入")
        demo.dismiss_popups()
        # 錄影前先開一次工作流程，把 Production Checklist 浮窗關掉
        driver.get(f"{BASE}/workflow/{args.workflow_id}")
        time.sleep(4)
        log(f"預先關閉 Production Checklist：{demo.wait_close_checklist(4)}")
        demo.dismiss_popups()
        driver.get(f"{BASE}/home/workflows")
        time.sleep(4)
        demo.dismiss_popups()
        log(f"Chrome 在最上層：{bring_to_front(driver)}")
        log(f"點頁面標題移開網址列焦點：{os_click_on(driver, demo.tid('project-name'))}")
        demo.dismiss_popups()
        time.sleep(1)

        if args.setup_only:  # 只準備、不錄影也不執行流程：抓一格畫面確認
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "gdigrab", "-framerate", "5", "-draw_mouse", "0", "-i", "desktop",
                            "-frames:v", "1", args.setup_only], check=True)
            log(f"準備完成，畫面存到 {args.setup_only}")
            return

        rec = start_recording()

        # 1. 工作流程列表
        log("分鏡 1：工作流程列表")
        demo.pause(4)
        demo.shot("工作流程列表")
        demo.pause(1)

        # 2. 打開【錄影用】，停在全畫布：兩條獨立流程與兩張便利貼
        log("分鏡 2：開啟【錄影用】工作流程")
        card = [c for c in demo.visible('[data-test-id="resources-list-item-workflow"]') if "【錄影用】" in c.text][0]
        demo.click(card, 1.2)
        log(f"  Production Checklist：{demo.wait_close_checklist(5)}")
        time.sleep(1.5)
        demo.dismiss_popups()
        demo.click(demo.tid("zoom-to-fit"), 0.8)
        demo.pause(3)
        for note in demo.visible('[data-test-id="sticky"]'):  # 依序點出兩張便利貼
            demo.flash(note, 1.8)
            demo.unflash(note)
        demo.pause(1.5)
        demo.shot("錄影用工作流程全畫布")
        demo.pause(1)

        # 3. 打開「訂單驗證與清洗」，展示程式碼 3 秒
        log("分鏡 3：訂單驗證與清洗程式碼")
        demo.open_ndv("訂單驗證與清洗")
        demo.pause(3.5)
        demo.shot("訂單驗證與清洗程式碼")
        demo.pause(0.5)
        demo.close_ndv()
        demo.pause(1)

        # 4. 執行主流程
        log("分鏡 4：執行主流程")
        demo.execute_from("接收點餐訂單")
        st = demo.wait_node("回傳訂單確認")
        log(f"  回傳訂單確認：{st}")
        demo.pause(4)
        demo.shot("主流程執行完成")
        demo.pause(1)

        # 5. 品項金額計算的輸出：totalWithTax、lineMessage 全文
        log("分鏡 5：品項金額計算輸出")
        demo.open_ndv("品項金額計算")
        out = demo.output_mode("schema")
        demo.pause(1.5)
        demo.scroll_output(out, "bottom")
        demo.pause(1)
        log("  " + demo.box_row(out, "totalWithTax", "147"))
        demo.pause(2)
        log("  " + demo.box_row(out, "lineMessage", "取餐碼"))
        demo.pause(5)
        demo.shot("品項金額計算輸出")
        demo.pause(1)
        demo.close_ndv()
        demo.pause(1)

        # 6. 從「日結排程 11:30」執行日結流程
        log("分鏡 6：執行日結流程")
        demo.execute_from("日結排程 11:30")
        st = demo.wait_node("寫入日結報表", timeout=90)
        log(f"  寫入日結報表：{st}")
        demo.pause(4)
        demo.shot("日結流程執行完成")
        demo.pause(1)

        # 7. 日結統計計算的輸出
        log("分鏡 7：日結統計計算輸出")
        demo.open_ndv("日結統計計算")
        out = demo.output_mode("schema")
        demo.pause(1.5)
        for k, v in (("completionRate", "83"), ("totalRevenue", "630"), ("avgOrderValue", "126")):
            log("  " + demo.box_row(out, k, v))
            demo.pause(1.2)
        demo.pause(3)
        demo.shot("日結統計計算輸出")
        demo.pause(0.5)
        demo.clear_boxes()
        demo.scroll_output(out, key="topItems")
        demo.pause(1)
        log("  " + demo.box_span(out, "topItems[0]", "NT$220"))
        demo.pause(1.5)
        log("  " + demo.box_span(out, "topItems[1]", "NT$130"))
        demo.pause(4)
        demo.shot("日結統計前兩名品項")
        demo.pause(0.5)
        demo.close_ndv()
        demo.pause(1)

        # 8. Executions 分頁，點開 2-2 的 production execution
        log("分鏡 8：Executions")
        demo.click(demo.tid("radio-button-executions"), 1.2)
        log(f"  Production Checklist：{demo.wait_close_checklist(3)}")
        demo.dismiss_popups()
        demo.pause(2)
        demo.click(demo.tid(f"execution-details-{args.exec_id}"), 1.2)
        log(f"  Production Checklist：{demo.wait_close_checklist(2)}")
        time.sleep(1)
        demo.dismiss_popups()
        demo.pause(1.5)
        demo.shot("Executions_production執行紀錄")
        info = demo.visible(f'[data-test-id="execution-preview-details-{args.exec_id}"]')
        if info:
            demo.flash(info[0], 2.5)
            demo.unflash(info[0])
        demo.pause(2)

        # 9. 結尾停 3 秒
        log("分鏡 9：結尾")
        demo.pause(3.5)
    finally:
        if rec:
            stop_recording(rec)
        driver.quit()
    log("完成")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow-id", required=True, help="【錄影用】工作流程的 ID（n8n list:workflow 可查）")
    ap.add_argument("--exec-id", help="分鏡 8 要點開的 production execution ID（實際 HTTP 呼叫成功的那一筆）")
    ap.add_argument("--setup-only", metavar="PNG", help="只做錄影前準備並抓一格畫面，不錄影、不執行流程")
    a = ap.parse_args()
    if not a.setup_only and not a.exec_id:
        ap.error("正式錄影需要 --exec-id")
    run(a)
