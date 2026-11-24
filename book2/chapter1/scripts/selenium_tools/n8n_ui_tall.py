"""JSON 檢視是虛擬捲動，只會畫出看得到的行；暫時把 viewport 拉高讓整段 JSON 都畫出來再讀。"""
import time

import n8n_ui as ui


def read_output_json_tall(driver, node_name, height=4200):
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride",
                           {"width": 1920, "height": height, "deviceScaleFactor": 1, "mobile": False})
    time.sleep(1.5)
    try:
        ui.open_ndv(driver, node_name)
        raw, parsed, redacted = ui.read_output_json(driver)
        ui.close_ndv(driver)
    finally:
        driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
        time.sleep(1)
    return raw, parsed, redacted
