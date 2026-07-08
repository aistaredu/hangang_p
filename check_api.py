import requests

API_KEY = "69614e464561697339334d6d50716c"
url = f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/TbUseDaystatusView/1/3/"

res = requests.get(url, timeout=10)
import json
print(json.dumps(res.json(), ensure_ascii=False, indent=2))
