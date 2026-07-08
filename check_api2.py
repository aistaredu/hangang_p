import requests, json

API_KEY = "69614e464561697339334d6d50716c"

# 전체 데이터에서 PKLT_NM 목록 확인 (1~1000건)
url = f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/TbUseDaystatusView/1/1000/"
res = requests.get(url, timeout=30)
data = res.json()
rows = data["TbUseDaystatusView"]["row"]

# 고유 주차장명과 날짜 확인
names = sorted(set(r["PKLT_NM"] for r in rows))
dates = sorted(set(r["DT"] for r in rows))

print(f"총 {len(rows)}건")
print(f"\n날짜 범위: {dates[0]} ~ {dates[-1]}")
print(f"\n주차장명 목록 ({len(names)}개):")
for n in names:
    print(f"  {n}")
