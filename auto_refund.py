#!/usr/bin/env python3
import requests
import json
from datetime import date
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load hidden config from .env
load_dotenv()

# Hidden config (never logged/visible)
BASE_URL = os.getenv('BASE_URL')
USERNAME = os.getenv('USERNAME')
PASSWORD_HASH = os.getenv('PASSWORD_HASH')
SELLER_NUMBER = os.getenv('SELLER_NUMBER')
COOKIE_VALUE = os.getenv('COOKIE')

if not all([BASE_URL, USERNAME, PASSWORD_HASH]):
    print("❌ Missing .env config!")
    sys.exit(1)

# LOGGING (user home)
LOG_DIR = Path.home() / "evcharging_logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'bill_refund.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

print(f"📝 Logs: {LOG_DIR / 'bill_refund.log'}")

session = requests.Session()
cookies = {'LIFF_STORE': COOKIE_VALUE}
auth_token = None

class AuthManager:
    @staticmethod
    def login():
        global auth_token
        login_url = f"{BASE_URL}/api/config-service/user/login"
        login_headers = {
            'accept': 'application/json', 'accept-language': 'zh-TW', 'content-type': 'application/json',
            'origin': BASE_URL, 'priority': 'u=1, i', 'referer': f'{BASE_URL}/login',
            'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"macOS"', 'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
        }
        
        login_payload = {
            "account": USERNAME,
            "password": PASSWORD_HASH,
            "sellerNumber": SELLER_NUMBER,
            "smsCaptchaPass": True
        }
        
        try:
            logger.info("🔐 Logging in...")
            response = session.post(login_url, headers=login_headers, json=login_payload, cookies=cookies)
            response.raise_for_status()
            
            login_data = response.json()
            if 'data' in login_data and login_data['data']:
                auth_token = login_data['data']
                session.cookies.update(response.cookies)
                cookies.update(response.cookies)
                logger.info(f"✅ Login OK! Token: {auth_token[:20]}...")
                return True
            else:
                logger.error(f"❌ No token: {login_data}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return False

def get_headers():
    global auth_token
    return {
        'accept': 'application/json', 'accept-language': 'zh-TW', 'authorization': auth_token,
        'content-type': 'application/json', 'origin': BASE_URL, 'priority': 'u=1, i',
        'referer': f'{BASE_URL}/Operation/ChargingOrder/OrderManagement',
        'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
        'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"macOS"', 'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
    }

def get_today_range():
    today = date.today().strftime("%Y-%m-%d")
    return f"{today} 00:00:00", f"{today} 23:59:59"

def fetch_bills():
    url = f"{BASE_URL}/api/statistics-service/billDetailStatisticsController/page"
    time_s, time_e = get_today_range()
    payload = {
        "stationIds": [1227], "fleetIds": None, "memberCategorys": [1, 0], "billStatus": [14],
        "pileIds": None, "groupIds": None, "timeS": time_s, "timeE": time_e,
        "current": 1, "total": 0, "pageSize": 50, "busIdType": 1
    }
    
    try:
        resp = session.post(url, headers=get_headers(), json=payload, cookies=cookies)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"✅ Bills: {time_s} → {time_e}")
        return data
    except Exception as e:
        logger.error(f"❌ Fetch failed: {e}")
        return None

def refund_bill(bill_id, amount):
    url = f"{BASE_URL}/api/bill-service/bill/billRefund"
    payload = {"billId": bill_id, "memberId": None, "refundMoney": int(amount), "note": "auto-refund", "refundPowerDiscount": 0}
    
    try:
        resp = session.post(url, headers=get_headers(), json=payload, cookies=cookies)
        resp.raise_for_status()
        logger.info(f"    ✓ Refunded: {bill_id}")
        return True
    except Exception as e:
        logger.error(f"    ❌ Refund {bill_id}: {e}")
        return False

def process_refunds(bill_data):
    total = bill_data.get('totalCount', 0)
    logger.info(f"📊 {total} bills")
    
    if total == 0:
        logger.info("ℹ️ No refunds needed")
        return
    
    data = bill_data.get('data', [])
    success, failed = 0, 0
    
    for bill in data:
        bid = bill.get('id')
        amt = bill.get('actualMoney')
        if bid and amt is not None:
            logger.info(f"🔄 {bid}: ${amt}")
            if refund_bill(bid, amt):
                success += 1
            else:
                failed += 1
    
    logger.info(f"📈 Success: {success}, Failed: {failed}")

def main():
    today = date.today().strftime("%Y-%m-%d")
    logger.info(f"🚀 Auto-refund {today}")
    
    if not AuthManager.login():
        logger.error("💥 Login failed")
        return
    
    bill_data = fetch_bills()
    if bill_data:
        process_refunds(bill_data)
    logger.info("🏁 Done!")

if __name__ == "__main__":
    main()
