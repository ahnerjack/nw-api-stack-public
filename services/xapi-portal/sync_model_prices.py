#!/usr/bin/env python3
import runpy, json, sys
ns=runpy.run_path("/opt/xapi-portal/xapi_portal.py", run_name="xapi_price_sync")
res=ns["sync_model_prices"]()
print(json.dumps(res, ensure_ascii=False))
sys.exit(0 if res.get("ok") else 1)
