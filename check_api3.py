import requests, json

API_KEY = "69614e464561697339334d6d50716c"

# 날짜 조건으로 조회 가능한지 확인
# 서울 열린데이터광장 방식: URL에 날짜 파라미터 추가
tests = [
    # 방법1: 쿼리 파라미터
    f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/TbUseDaystatusView/1/3/?DT=20220101",
    # 방법2: URL 경로에 날짜
    f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/TbUseDaystatusView/1/3/20220101/",
    # 방법3: 슬래시로 날짜 범위
    f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/TbUseDaystatusView/1/3/20220101/20220101/",
]

for url in tests:
    print(f"\n테스트 URL: {url}")
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        rows = data.get("TbUseDaystatusView", {}).get("row", [])
        if rows:
            print(f"  ✅ 성공! 날짜: {rows[0].get('DT')} / 주차장: {rows[0].get('PKLT_NM')}")
        else:
            result = data.get("TbUseDaystatusView", {}).get("RESULT", data.get("RESULT", {}))
            print(f"  ❌ row 없음: {result}")
    except Exception as e:
        print(f"  ❌ 오류: {e}")
