#!/usr/bin/env python3
"""
EV Charging AutoRefund - Python版 (修正版)
等同 Java AutoRefund.java，支援你的 EV 充電退款工作流
依賴: pip install python-dotenv requests loguru
"""

import os
import sys
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import requests
from dotenv import load_dotenv
from loguru import logger

# 全域變數
auth_token: Optional[str] = None

# 配置
load_dotenv()
BASE_URL = os.getenv("BASE_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD_HASH = os.getenv("PASSWORD_HASH")
SELLER_NUMBER = os.getenv("SELLER_NUMBER")
COOKIE_VALUE = os.getenv("COOKIE")

# 必要檢查
required = ["BASE_URL", "USERNAME"]
missing = [k for k, v in locals().items() if isinstance(k, str) and k in required and v is None]
if missing:
    print(f"❌ .env missing: {', '.join(missing)}")  # logger 未初始化前用 print
    sys.exit(1)

LOG_DIR = Path.home() / "evcharging_logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(LOG_DIR / "bill_refund.log", rotation="1 day", level="INFO", 
           format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

def login() -> Optional[str]:
    """登入取得 auth token"""
    global auth_token
    url = f"{BASE_URL}/api/config-service/user/login"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "origin": BASE_URL,
        "cookie": f"LIFF_STORE={COOKIE_VALUE}",
        "referer": f"{BASE_URL}/login",
    }
    payload = {
        "account": USERNAME,
        "password": PASSWORD_HASH,
        "sellerNumber": SELLER_NUMBER,
        "smsCaptchaPass": True,
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("data"):
            token = data["data"]
            logger.info("✅ Login: {}", token[:20] + "...")
            auth_token = token  # 更新全域
            return token
        logger.error("❌ No token: {}", data)
        return None
        
    except requests.RequestException as e:
        logger.error("Login HTTP fail: {}", e)
        return None
    except Exception as e:
        logger.error("Login fail: {}", e)
        return None

def fetch_bills(token: str) -> Optional[Dict[str, Any]]:
    """抓取昨日至今日 billStatus=14 訂單"""
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = date.today().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/api/statistics-service/billDetailStatisticsController/page"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": token,
        "cookie": f"LIFF_STORE={COOKIE_VALUE}",
    }
    payload = {
        "stationIds": [1227],
        "memberCategorys": [1, 0],
        "billStatus": [14],
        "timeS": f"{yesterday} 00:00:00",
        "timeE": f"{today} 23:59:59",
        "current": 1,
        "pageSize": 50,
        "busIdType": 1,
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        total = data.get("totalCount", 0)
        logger.info("🈶 Bills OK, total: {}", total)
        return data
        
    except requests.RequestException as e:
        logger.error("Fetch bills HTTP fail: {}", e)
        return None
    except Exception as e:
        logger.error("Fetch bills fail: {}", e)
        return None

def process_refunds(bill_data: Dict[str, Any]):
    """處理退款，跳過 actualMoney=0"""
    total = bill_data.get("totalCount", 0)
    logger.info("📊 {} bills found", total)
    if total == 0:
        logger.info("❌ No bills to process")
        return
    
    bills = bill_data.get("data", [])
    if not isinstance(bills, list):
        logger.warning("⚠️ bills.data is not list: {}", type(bills))
        return
        
    success, failed, skipped = 0, 0, 0
    
    for bill in bills:
        bill_id = bill.get("id")
        if not bill_id or not isinstance(bill_id, (int, str)):
            logger.warning("⚠️ Invalid bill_id: {}", bill_id)
            continue
            
        bill_id_int = int(bill_id)
        amt = bill.get("actualMoney")
        
        if amt == 0 or amt is None:
            logger.info("🙈 {}: ${} (skipped)", bill_id_int, amt)
            skipped += 1
            continue
        
        logger.info("💰 Processing {}: ${}", bill_id_int, amt)
        if refund_bill(bill_id_int, int(amt)):
            success += 1
        else:
            failed += 1
    
    logger.info("🎉 Success:{}, Failed:{}, Skipped:{}", success, failed, skipped)

def refund_bill(bill_id: int, amount: int) -> bool:
    """執行單筆退款"""
    if not auth_token:
        logger.error("❌ No auth_token for refund")
        return False
        
    url = f"{BASE_URL}/api/bill-service/bill/billRefund"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": auth_token,
        "cookie": f"LIFF_STORE={COOKIE_VALUE}",
    }
    payload = {
        "billId": bill_id,
        "memberId": None,
        "refundMoney": amount,
        "note": f"python-refund-{bill_id}-{date.today().strftime('%Y%m%d')}",
        "refundPowerDiscount": 0,
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        body = resp.text[:200]  # 限制長度
        
        if 200 <= resp.status_code < 300:
            logger.success("    ✓ {} [{}] {}", bill_id, resp.status_code, body)
            return True
        else:
            logger.error("    ❌ {} [{}] {}", bill_id, resp.status_code, body)
            return False
            
    except requests.RequestException as e:
        logger.error("    ❌ {} Request error: {}", bill_id, str(e)[:100])
        return False
    except Exception as e:
        logger.error("    ❌ {} Unexpected: {}", bill_id, str(e))
        return False

if __name__ == "__main__":
    logger.info("🚀 Python AutoRefund v2.0 - 昨天至今")
    
    if not login():
        logger.error("😫 Login failed")
        sys.exit(1)
    
    bill_data = fetch_bills(auth_token)
    if bill_data:
        process_refunds(bill_data)
    else:
        logger.error("😫 No bill data")
    
    logger.info("🅾️ Done - {}", date.today())
