"""以專用設定檔（chapter1\\chrome-profile）啟動 Chrome，開 remote debugging 9222，腳本結束後視窗保留。

之後可用 sel_run.py 反覆連上同一個視窗做檢查或盤點 data-test-id。
用法：python scripts\\selenium_tools\\sel_launch.py [網址]
關閉：用 sel_run.py 執行 driver.execute_cdp_cmd("Browser.close", {})（以 debuggerAddress 連上的 session，quit() 關不掉瀏覽器）
"""
import sys
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

ROOT = Path(__file__).resolve().parents[2]  # chapter1
url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5678/home/workflows"
opts = Options()
opts.add_argument(f"--user-data-dir={ROOT / 'chrome-profile'}")
opts.add_argument("--remote-debugging-port=9222")
opts.add_argument("--start-maximized")
opts.add_experimental_option("detach", True)
driver = webdriver.Chrome(options=opts)  # 不指定路徑 → Selenium Manager 自動取得對應版本的 ChromeDriver
driver.get(url)
print("launched:", driver.current_url, driver.capabilities.get("browserVersion"))
