# autoRefund.py - EV Charging AutoRefund Script

## Overview
This Python script automates the refund process for EV charging bills with a specific status (billStatus=14) on an EV charging platform. 
"It logs into the system, fetches bills from the previous day, and processes refunds for qualifying bills with positive amounts. 

The script is designed for use in EV charging station management systems, likely integrating with OCPP-compliant platforms, 
and handles authentication, API calls, and logging robustly. 

## Features
- Secure login using username, password hash, and seller number from environment variables.
- Fetches bills filtered by station ID (1227), member categories (1,0), and date range (yesterday to today).
- Processes refunds only for bills with actualMoney > 0, skipping others.
- Comprehensive logging to `~/evcharging/logs/billrefund.log` with daily rotation.
- Error handling for HTTP failures, invalid data, and authentication issues. 
- Required packages (install via pip):
  ```
  pip install python-dotenv requests loguru
  ``` 

## Installation
1. Clone or download the script.
2. Create a `.env` file in the same directory with the following variables:
   ```
   BASEURL=https://your-platform-url.com
   USERNAME=your_username
   PASSWORDHASH=your_password_hash
   SELLERNUMBER=your_seller_number
   LIFFSTORECOOKIEVALUE=your_cookie_value
   ```
3. Ensure the log directory exists or let the script create `~/evcharging/logs/`.
4. Make executable: `chmod +x autoRefund.py`. 

## Usage
Run the script from the command line:
```
python autoRefund.py
```
- It logs in automatically.
- Fetches and processes bills (up to pageSize=50).
- Outputs success/failed/skipped counts.
- Version: v2.0 (as per script). 
Key hardcoded values (customize in code if needed):
- `stationIds: [1227]`
- `billStatus: 14`
- `pageSize: 50`
- Date range: Yesterday 00:00:00 to today 23:59:59
- Refund note: `python-refund-billid-YYYYMMDD`
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/config-service/user/login` | POST | Authentication  |
| `/api/statistics-service/billDetailStatisticsController/page` | POST | Fetch bills   |
| `/api/bill-service/bill/{billId}/refund` | POST | Process refund   |

## Logging
- Logs to `~/evcharging/logs/billrefund.log`.
- Levels: INFO and above.
- Format: `{time:YYYY-MM-DD HH:mm:ss} [{level}] {message}` 

## Troubleshooting
- **Login failed**: Check `.env` vars (BASEURL, USERNAME required).
- **No bills**: Verify stationIds, date range, billStatus.
- **HTTP errors**: Ensure cookie and auth token validity.
- **Permissions**: Run with sufficient access for sellerNumber. 

## Notes
- Tailored for production EV charging environments in Taiwan (e.g., HDRE-like systems).
- Test in staging before production.
- Complies with PCI DSS indirectly via secure handling; audit payment flows separately. 
