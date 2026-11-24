"""連到 sel_launch.py 開啟的 Chrome（remote debugging 9222），執行一段 Python 片段。

用法：python scripts\\selenium_tools\\sel_run.py <snippet.py> [args...]
片段內可直接使用：driver, By, inv(), shot(name), click(el), js(code, *args), sleep, OUT, json, time, argv
  inv()  列出畫面上可見元素的 data-test-id（寫選擇器前先盤點，不要憑記憶硬寫）
  shot() 截圖存到 chapter1\\output\\stage2\\<name>.png
"""
import json
import runpy
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parents[2]  # chapter1
OUT = ROOT / "output" / "stage2"
OUT.mkdir(parents=True, exist_ok=True)

opts = Options()
opts.debugger_address = "127.0.0.1:9222"
driver = webdriver.Chrome(options=opts)

INVENTORY_JS = """
const root = arguments[0] || document;
const m = {};
root.querySelectorAll('[data-test-id]').forEach(el => {
  if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') return;  // 只列可見的
  const k = el.getAttribute('data-test-id');
  if (!m[k]) m[k] = {count: 0, samples: []};
  m[k].count++;
  const t = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim().replace(/\\s+/g, ' ');
  if (m[k].samples.length < 2 && t) m[k].samples.push(t.slice(0, 70));
});
return m;
"""


def js(code, *args):
    return driver.execute_script(code, *args)


def inv(root=None, only=None):
    m = js(INVENTORY_JS, root)
    for k in sorted(m):
        if only and not any(o in k for o in only):
            continue
        print(f"  {k} x{m[k]['count']} {m[k]['samples']}")
    return m


def shot(name):
    p = OUT / f"{name}.png"
    driver.save_screenshot(str(p))
    print("screenshot:", p)


def click(el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    el.click()


def sleep(s):
    time.sleep(s)


g = dict(driver=driver, By=By, inv=inv, shot=shot, click=click, js=js, sleep=sleep,
         OUT=OUT, json=json, time=time, argv=sys.argv[2:])
runpy.run_path(sys.argv[1], init_globals=g)
