# =============================================================
# data/collect_parking_daily.py
# TbUseDaystatusView API → parking_daily INSERT
# =============================================================
# 📌 API 특성:
#   - 날짜 파라미터 미지원 → 페이지네이션으로 전체 수집
#   - 총 약 61,739건 / 1000건씩 나눠서 호출
#   - 세부 주차장(뚝섬1~4)을 공원 단위로 합산
#
# 📌 실행:
#   python data/collect_parking_daily.py
# =============================================================

import sys, os, time, argparse
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from sqlalchemy import select
from database.db_connection import SessionFactory
from models.models import ParkingInfo, ParkingDaily

load_dotenv()
API_KEY = os.getenv("SEOUL_API_KEY")
BASE_URL = f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/TbUseDaystatusView"

# =============================================================
# 세부 주차장명 → parking_info.id 매핑
# API 응답의 PKLT_NM 값을 그대로 키로 사용
# =============================================================
LOT_NAME_MAP = {
    # 뚝섬 (lot_id=1)
    "뚝섬1주차장"       : 1,
    "뚝섬2주차장"       : 1,
    "뚝섬3주차장"       : 1,
    "뚝섬4주차장"       : 1,

    # 여의도 (lot_id=2)
    "여의도1주차장"      : 2,
    "여의도2주차장"      : 2,
    "여의도3주차장"      : 2,
    "여의도4주차장"      : 2,
    "여의도5주차장"      : 2,

    # 반포 (lot_id=3)
    "반포1주차장"       : 3,
    "반포2,3주차장"     : 3,

    # 잠원 (lot_id=4)
    "잠원1주차장"       : 4,
    "잠원2-6주차장"     : 4,

    # 망원 (lot_id=5)
    "망원1주차장"       : 5,
    "망원2주차장"       : 5,

    # 난지 (lot_id=6)
    "난지1,2,3,4주차장" : 6,

    # 강서 (lot_id=7)
    "강서1주차장"       : 7,

    # 양화 (lot_id=8)
    "양화1주차장"       : 8,
    "양화2주차장"       : 8,
    "양화3주차장"       : 8,

    # 이촌 (lot_id=9)
    "이촌1주차장"       : 9,
    "이촌2주차장"       : 9,
    "이촌3주차장"       : 9,

    # 잠실 (lot_id=10)
    "잠실1주차장"       : 10,
    "잠실2,3주차장"     : 10,

    # 광나루 (lot_id=11)
    "광나루1,2주차장"   : 11,
    "광나루3주차장"     : 11,
    "광나루4주차장"     : 11,
}


def fetch_page(start: int, end: int) -> list:
    """
    API 페이지 1건 호출
    start~end: 조회할 행 범위 (1-based)
    반환: row 리스트
    """
    url = f"{BASE_URL}/{start}/{end}/"
    try:
        res  = requests.get(url, timeout=30)
        data = res.json()
        rows = data.get("TbUseDaystatusView", {}).get("row", [])
        return rows
    except Exception as e:
        print(f"  ⚠️  {start}~{end} 호출 오류: {e}")
        return []


def get_total_count() -> int:
    """전체 데이터 건수 조회"""
    url  = f"{BASE_URL}/1/1/"
    res  = requests.get(url, timeout=10)
    data = res.json()
    return data.get("TbUseDaystatusView", {}).get("list_total_count", 0)


def rows_to_daily(rows: list) -> dict:
    """
    row 리스트를 (lot_id, date) → 합산 이용대수 딕셔너리로 변환
    세부 주차장(뚝섬1~4)을 공원 단위로 합산합니다.

    반환: { (lot_id, date): total_count }
    """
    daily = defaultdict(int)

    for row in rows:
        lot_name  = str(row.get("PKLT_NM", "")).strip()
        count_raw = row.get("PRK_CNTOM", 0)  # 이용대수
        dt_str    = str(row.get("DT", ""))    # "2026/06/21" 형식

        lot_id = LOT_NAME_MAP.get(lot_name)
        if not lot_id:
            continue  # 매핑 안 되는 주차장 스킵

        try:
            use_date    = datetime.strptime(dt_str, "%Y/%m/%d").date()
            daily_count = int(float(count_raw))
        except (ValueError, TypeError):
            continue

        # 같은 (lot_id, date)는 합산 (뚝섬1+뚝섬2+뚝섬3+뚝섬4 → 뚝섬 전체)
        daily[(lot_id, use_date)] += daily_count

    return daily


def insert_daily(daily: dict, session) -> tuple:
    """
    (lot_id, date) → count 딕셔너리를 DB에 INSERT
    반환: (inserted, skipped)
    """
    inserted = 0
    skipped  = 0

    for (lot_id, use_date), daily_count in daily.items():
        # 중복 확인
        stmt   = select(ParkingDaily).where(
            ParkingDaily.lot_id   == lot_id,
            ParkingDaily.use_date == use_date,
        )
        exists = session.scalar(stmt)

        if exists:
            skipped += 1
            continue

        session.add(ParkingDaily(
            lot_id      =lot_id,
            use_date    =use_date,
            daily_count =daily_count,
        ))
        inserted += 1

    return inserted, skipped


def collect():
    """전체 데이터 수집 메인 함수"""
    print("=" * 60)
    print("한강공원 주차장 일별 데이터 수집")
    print("서비스: TbUseDaystatusView")
    print("=" * 60)

    # 전체 건수 확인
    total = get_total_count()
    page_size = 1000
    total_pages = (total + page_size - 1) // page_size
    print(f"총 {total:,}건 / {page_size}건씩 {total_pages}페이지")
    print("-" * 60)

    total_inserted = 0
    total_skipped  = 0

    with SessionFactory() as session:
        for page in range(total_pages):
            start = page * page_size + 1
            end   = min(start + page_size - 1, total)

            # API 호출
            rows = fetch_page(start, end)
            if not rows:
                print(f"  [{page+1}/{total_pages}] 데이터 없음, 스킵")
                continue

            # 공원 단위 합산
            daily = rows_to_daily(rows)

            # DB INSERT
            ins, skp = insert_daily(daily, session)
            session.commit()

            total_inserted += ins
            total_skipped  += skp

            # 진행 상황
            pct = (page + 1) / total_pages * 100
            bar = "█" * int(pct / 5)
            print(f"  [{bar:<20}] {page+1}/{total_pages} | +{ins}건 삽입 | {skp}건 스킵", end="\r")

            time.sleep(0.1)  # API 부하 방지

    print(f"\n\n✅ 수집 완료! 삽입 {total_inserted:,}건 / 스킵 {total_skipped:,}건")
    verify()


def verify():
    """수집 결과 요약"""
    from sqlalchemy import func

    with SessionFactory() as session:
        result = session.execute(
            select(
                ParkingInfo.lot_name,
                func.count(ParkingDaily.id).label("days"),
                func.min(ParkingDaily.use_date).label("first"),
                func.max(ParkingDaily.use_date).label("last"),
                func.round(func.avg(ParkingDaily.daily_count)).label("avg"),
            )
            .join(ParkingDaily, ParkingInfo.id == ParkingDaily.lot_id)
            .group_by(ParkingInfo.id, ParkingInfo.lot_name)
            .order_by(ParkingInfo.id)
        ).all()

        if not result:
            print("[결과] 데이터 없음")
            return

        print("\n[parking_daily 수집 결과]")
        print(f"{'주차장명':<25} | {'일수':>5} | {'시작일':>12} | {'종료일':>12} | {'일평균':>7}")
        print("-" * 72)
        for r in result:
            print(
                f"  {r.lot_name:<23} | "
                f"{r.days:>5}일 | "
                f"{str(r.first):>12} | "
                f"{str(r.last):>12} | "
                f"{int(r.avg):>6}대"
            )

        total = session.scalar(select(func.count(ParkingDaily.id)))
        print(f"\n총 {total:,}행")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="한강공원 주차장 일별 데이터 수집")
    parser.add_argument("--verify", action="store_true", help="DB 현황만 확인")
    args = parser.parse_args()

    if args.verify:
        verify()
    else:
        collect()
