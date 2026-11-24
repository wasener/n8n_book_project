"""n8n 3.0 編輯器的共用操作（選擇器皆依 n8n 3.0.0 介面實際盤點的 data-test-id）。

在 sel_run.py 的片段中使用：
  import sys; sys.path.insert(0, r"<chapter1>\\scripts\\selenium_tools"); import n8n_ui as ui
"""
import json
import time

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

BASE = "http://localhost:5678"


def visible(driver, css):
    return [e for e in driver.find_elements(By.CSS_SELECTOR, css) if e.is_displayed()]


def dismiss_popups(driver):
    for tid in ("n8n-chat-hint-new_chat_sidebar-got-it", "banner-dynamic-banner-7-close"):
        for el in visible(driver, f'[data-test-id="{tid}"]'):
            try:
                el.click(); time.sleep(0.4)
            except Exception:
                pass


def canvas_node(driver, name):
    nodes = [n for n in driver.find_elements(By.CSS_SELECTOR, '[data-test-id="canvas-node"]')
             if name in n.text]
    if len(nodes) != 1:
        raise RuntimeError(f"canvas node {name!r}: {len(nodes)} matches")
    return nodes[0]


def execute_from_trigger(driver, trigger_name):
    trig = canvas_node(driver, trigger_name)
    ActionChains(driver).move_to_element(trig).perform(); time.sleep(0.8)
    btn = driver.find_element(By.CSS_SELECTOR, f'[data-test-id="execute-workflow-button-{trigger_name}"]')
    btn.click()
    return btn


def wait_node_done(driver, name, timeout=60):
    """等節點出現 success 或 error 狀態。回傳 'success' / 'error' / 'timeout'。"""
    end = time.time() + timeout
    while time.time() < end:
        n = canvas_node(driver, name)
        if n.find_elements(By.CSS_SELECTOR, '[data-test-id="canvas-node-status-success"]'):
            return "success"
        if n.find_elements(By.CSS_SELECTOR, '[data-test-id="canvas-node-status-error"]'):
            return "error"
        time.sleep(0.5)
    return "timeout"


def open_ndv(driver, name):
    ActionChains(driver).double_click(canvas_node(driver, name)).perform()
    time.sleep(2)


def close_ndv(driver):
    for b in visible(driver, '[data-test-id="ndv-close-button"]'):
        b.click(); time.sleep(1); return


def read_output_json(driver):
    """在已開啟的 NDV 中把輸出面板切到 JSON，回傳 (raw_text, parsed 或 None, redacted)。"""
    out = driver.find_element(By.CSS_SELECTOR, '[data-test-id="output-panel"]')
    if out.find_elements(By.CSS_SELECTOR, '[data-test-id="ndv-data-redacted"]'):
        return out.text, None, True
    btns = [b for b in out.find_elements(By.CSS_SELECTOR, '[data-test-id="radio-button-json"]') if b.is_displayed()]
    if btns:
        btns[0].click(); time.sleep(1.2)
    cont = out.find_element(By.CSS_SELECTOR, '[data-test-id="ndv-data-container"]')
    raw = cont.text
    parsed = None
    try:
        parsed = json.loads(raw)
    except Exception:
        pass
    return raw, parsed, False
