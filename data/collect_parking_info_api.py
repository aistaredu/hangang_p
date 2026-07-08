# =============================================================
# python data/collect_parking_info_api.py --update-only ㅌㅓ미널에서 실행
# 한강공원 주차장 11개소 기본 정보 → parking_info 테이블 INSERT
# =============================================================
# 📌 역할:
#   TbParkingInfoView API에서 실제 주차면수(PRK_CNT)를 읽어
#   LOT_NAME_MAP으로 공원 단위 합산 후 parking_info 테이블에 저장합니다.
#
# 📌 수정 이유:
#   기존 코드는 capacity를 직접 하드코딩했는데,
#   API 실제값과 달라서 occupancy_pct = daily_count / capacity × 100이
#   100%를 훨씬 초과하는 문제가 발생했습니다.
#   예) 기존 강서: 425면 → API 실제: 99면 → 500% 초과 발생
#
# 📌 해결 방법:
#   TbParkingInfoView API에서 PRK_CNT(실제 총면수)를 직접 읽어서
#   collect_parking_daily.py와 동일한 LOT_NAME_MAP으로 공원별 합산합니다.
#
# 📌 실행 방법:
#   python data/collect_parking_info.py
#
# 📌 실행 빈도:
#   주차장 면수가 변경될 때마다 재실행합니다.
#   여러 번 실행해도 안전합니다 (기존 데이터 삭제 후 재삽입).
# =============================================================

import sys
import os
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict

# ─────────────────────────────────────────────────────────────
# 프로젝트 루트를 Python 경로에 추가
# ─────────────────────────────────────────────────────────────
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from database.db_connection import SessionFactory
from models.models import ParkingInfo
from sqlalchemy import select

load_dotenv()

# =============================================================
# API 설정
# =============================================================
API_KEY  = os.getenv("SEOUL_API_KEY")
BASE_URL = f"http://openapi.seoul.go.kr:8088/{API_KEY}/xml/TbParkingInfoView"


# =============================================================
# LOT_NAME_MAP — 세부 주차장명 → parking_info.id 매핑
# =============================================================
# 📌 collect_parking_daily.py의 LOT_NAME_MAP과 반드시 동일해야 합니다.
#   두 파일이 같은 매핑을 공유해야 lot_id가 일치합니다.
#
# 📌 매핑 원칙:
#   API의 PKLT_TYPE 값을 그대로 키로 사용합니다.
#   같은 lot_id로 묶인 세부 주차장의 PRK_CNT를 합산합니다.
#   예) 뚝섬1+뚝섬2+뚝섬3+뚝섬4 → lot_id=1 뚝섬 전체 면수
LOT_NAME_MAP = {
    # 뚝섬 (lot_id=1)
    "뚝섬1주차장"       : 1,
    "뚝섬2주차장"       : 1,
    "뚝섬3주차장"       : 1,
    "뚝섬4주차장"       : 1,

    # 여의도 (lot_id=2)
    "여의도1주차장"     : 2,
    "여의도2주차장"     : 2,
    "여의도3주차장"     : 2,
    "여의도4주차장"     : 2,
    "여의도5주차장"     : 2,

    # 반포 (lot_id=3)
    "반포1주차장"       : 3,
    "반포2,3주차장"     : 3,

    # 잠원 (lot_id=4)
    "잠원1주차장"       : 4,
    "잠원2-6주차장"     : 4,

    # 망원 (lot_id=5)
    "망원1주차장"       : 5,
    "망원2주차장"       : 5,
    "망원4주차장"       : 5,

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
    "이촌4주차장"       : 9,

    # 잠실 (lot_id=10)
    "잠실1주차장"       : 10,
    "잠실2,3주차장"     : 10,

    # 광나루 (lot_id=11)
    "광나루1,2주차장"   : 11,
    "광나루3주차장"     : 11,
    "광나루4주차장"     : 11,
}

# lot_id → 공원명 매핑 (parking_info.lot_name에 저장될 이름)
LOT_INFO = {
    1 : {"lot_name": "뚝섬한강공원주차장",   "district": "뚝섬지구",   "lat": 37.5302, "lng": 127.0688},
    2 : {"lot_name": "여의도한강공원주차장",  "district": "여의도지구", "lat": 37.5285, "lng": 126.9337},
    3 : {"lot_name": "반포한강공원주차장",   "district": "반포지구",   "lat": 37.5126, "lng": 126.9995},
    4 : {"lot_name": "잠원한강공원주차장",   "district": "잠원지구",   "lat": 37.5166, "lng": 126.9994},
    5 : {"lot_name": "망원한강공원주차장",   "district": "망원지구",   "lat": 37.5494, "lng": 126.8975},
    6 : {"lot_name": "난지한강공원주차장",   "district": "난지지구",   "lat": 37.5663, "lng": 126.8906},
    7 : {"lot_name": "강서한강공원주차장",   "district": "강서지구",   "lat": 37.5736, "lng": 126.8241},
    8 : {"lot_name": "양화한강공원주차장",   "district": "양화지구",   "lat": 37.5454, "lng": 126.9101},
    9 : {"lot_name": "이촌한강공원주차장",   "district": "이촌지구",   "lat": 37.5210, "lng": 126.9726},
    10: {"lot_name": "잠실한강공원주차장",   "district": "잠실지구",   "lat": 37.5200, "lng": 127.0818},
    11: {"lot_name": "광나루한강공원주차장", "district": "광나루지구", "lat": 37.5492, "lng": 127.1266},
}


# =============================================================
# fetch_capacity_from_api() — API에서 공원별 실제 총면수 합산
# =============================================================
def fetch_capacity_from_api() -> dict:
    """
    TbParkingInfoView API에서 전체 데이터를 가져와
    공원 단위 총면수(lot_id → capacity)를 반환합니다.

    📌 API 응답 구조:
      <TbParkingInfoView>
        <list_total_count>30</list_total_count>
        <row>
          <PKLT_TYPE>강서1주차장</PKLT_TYPE>  ← LOT_NAME_MAP 키
          <PRK_CNT>99</PRK_CNT>               ← 이 값을 합산
        </row>
        ...
      </TbParkingInfoView>

    Returns:
        { lot_id: total_capacity }
        예) { 1: 458, 2: 532, ..., 7: 99, 11: 389 }
    """
    # 1) 전체 건수 확인 (1건만 조회해서 list_total_count 읽기)
    url_check = f"{BASE_URL}/1/1/"
    print("  API 전체 건수 확인 중...")
    res        = requests.get(url_check, timeout=15)
    root       = ET.fromstring(res.text)
    total      = int(root.findtext("list_total_count", "0"))
    print(f"  → 총 {total}개 주차장 데이터")

    # 2) 전체 데이터 한 번에 조회
    url_all = f"{BASE_URL}/1/{total}/"
    print(f"  전체 {total}건 조회 중...")
    res2  = requests.get(url_all, timeout=30)
    root2 = ET.fromstring(res2.text)
    rows  = root2.findall("row")
    print(f"  → {len(rows)}개 row 수신")

    # 3) LOT_NAME_MAP으로 공원별 합산
    # defaultdict(int): 키가 없으면 자동으로 0으로 초기화
    capacity_by_lot = defaultdict(int)
    unmatched = []  # 매핑 안 된 주차장 (경고용)

    for row in rows:
        pklt_name = row.findtext("PKLT_TYPE", "").strip()
        prk_cnt   = row.findtext("PRK_CNT", "0").strip()

        lot_id = LOT_NAME_MAP.get(pklt_name)
        if not lot_id:
            unmatched.append(pklt_name)
            continue

        try:
            capacity_by_lot[lot_id] += int(prk_cnt)
        except ValueError:
            continue

    if unmatched:
        print(f"  ⚠️  LOT_NAME_MAP 미매핑 주차장: {unmatched}")

    return dict(capacity_by_lot)


# =============================================================
# insert_parking_info() — 주차장 데이터 INSERT
# =============================================================
def insert_parking_info(capacity_map: dict):
    """
    API에서 구한 실제 면수(capacity_map)로 parking_info 테이블을 채웁니다.

    ⚠️ 주의: parking_daily 테이블이 parking_info.id를 외래키로 참조하므로
       parking_daily에 데이터가 이미 있으면 DELETE 시 IntegrityError가 발생합니다.
       이 경우 update_capacity_only()를 사용해야 합니다.

    Args:
        capacity_map: { lot_id: actual_capacity }  (fetch_capacity_from_api 반환값)
    """
    from sqlalchemy.exc import IntegrityError

    with SessionFactory() as session:

        # 기존 데이터 삭제 (멱등성 보장)
        try:
            deleted = session.query(ParkingInfo).delete()
            if deleted:
                print(f"  기존 {deleted}개 레코드 삭제")
        except IntegrityError:
            # FK 제약 위반: parking_daily가 parking_info를 참조 중
            session.rollback()
            print("\n❌ DELETE 실패: parking_daily가 parking_info를 참조하고 있습니다.")
            print("   (외래키 제약: parking_daily.lot_id → parking_info.id)")
            print("\n   해결 방법:")
            print("   python data/collect_parking_info_api.py --update-only")
            print("   ↑ capacity 컬럼만 안전하게 업데이트합니다.\n")
            return  # 함수 종료 (INSERT 진행하지 않음)

        for lot_id, info in LOT_INFO.items():
            # API에서 가져온 실제 면수 사용
            # API 호출 실패 등으로 lot_id가 없으면 0 (경고 발생)
            actual_capacity = capacity_map.get(lot_id, 0)

            if actual_capacity == 0:
                print(f"  ⚠️  lot_id={lot_id} {info['lot_name']}: 면수 0 (API 미매핑 확인 필요)")

            lot = ParkingInfo(
                lot_name = info["lot_name"],
                district = info["district"],
                capacity = actual_capacity,  # ← API 실제 면수
                lat      = info["lat"],
                lng      = info["lng"],
            )
            session.add(lot)
            print(f"  ✅ {info['lot_name']} → {actual_capacity}면")

        session.commit()
        print(f"\n✅ parking_info INSERT 완료: {len(LOT_INFO)}개소")


# =============================================================
# update_capacity_only() — 기존 DB의 면수만 업데이트 (데이터 유지)
# =============================================================
def update_capacity_only(capacity_map: dict):
    """
    parking_info 테이블의 capacity 컬럼만 업데이트합니다.
    parking_daily 등 연관 데이터는 그대로 유지됩니다.

    📌 insert_parking_info()와의 차이:
      insert: 기존 전체 삭제 후 재삽입 (parking_daily FK 주의)
      update: capacity 컬럼만 수정 → parking_daily 데이터 보존

    📌 사용 시나리오:
      이미 parking_daily에 수만 건 데이터가 있는 상황에서
      capacity만 올바른 값으로 수정할 때 사용합니다.
    """
    print("\n[capacity 업데이트 모드]")
    print("parking_daily 데이터를 유지하면서 면수만 수정합니다.\n")

    with SessionFactory() as session:
        lots = session.execute(
            select(ParkingInfo).order_by(ParkingInfo.id)
        ).scalars().all()

        if not lots:
            print("❌ parking_info 테이블이 비어있습니다.")
            print("   먼저 python data/collect_parking_info.py 를 실행하세요.")
            return

        for lot in lots:
            old_cap    = lot.capacity
            new_cap    = capacity_map.get(lot.id, 0)

            if new_cap == 0:
                print(f"  ⚠️  {lot.lot_name}: 매핑 없음, 스킵")
                continue

            if old_cap == new_cap:
                print(f"  ✅ {lot.lot_name}: {old_cap}면 (변경 없음)")
            else:
                lot.capacity = new_cap
                print(f"  🔄 {lot.lot_name}: {old_cap}면 → {new_cap}면 (수정)")

        session.commit()
        print("\n✅ capacity 업데이트 완료")


# =============================================================
# verify() — 저장된 면수 확인
# =============================================================
def verify():
    """parking_info 테이블 현황을 출력합니다."""
    with SessionFactory() as session:
        lots = session.execute(
            select(ParkingInfo).order_by(ParkingInfo.id)
        ).scalars().all()

        print(f"\n[parking_info 현황] 총 {len(lots)}개소")
        print(f"  {'ID':>3}  {'주차장명':<25} {'면수':>6}  {'위도':>9}  {'경도':>10}")
        print("  " + "-" * 60)

        for lot in lots:
            print(
                f"  {lot.id:>3}. "
                f"{lot.lot_name:<24} "
                f"{lot.capacity:>5}면  "
                f"{float(lot.lat):>9.4f}  "
                f"{float(lot.lng):>10.4f}"
            )


# =============================================================
# 실행
# =============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="한강공원 주차장 정보 수집")
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="capacity만 업데이트 (parking_daily 데이터 보존)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="DB 현황만 확인"
    )
    args = parser.parse_args()

    print("=" * 55)
    print("한강공원 주차장 기본 정보 수집")
    print("=" * 55)

    if args.verify:
        # 현황 확인만
        verify()

    elif args.update_only:
        # capacity만 업데이트 (parking_daily 데이터 보존)
        print("\n1) API에서 실제 면수 가져오는 중...")
        capacity_map = fetch_capacity_from_api()
        print("\n2) capacity 업데이트 중...")
        update_capacity_only(capacity_map)
        verify()

    else:
        # 기본: 전체 재삽입 시도
        # 📌 FK 제약 안전장치:
        #   parking_daily에 이미 데이터가 있으면 parking_info를 DELETE할 수 없습니다
        #   (외래키 제약 위반: parking_daily.lot_id → parking_info.id)
        #   이 경우 자동으로 update_capacity_only()로 전환합니다.
        from models.models import ParkingDaily
        with SessionFactory() as session:
            daily_count = session.query(ParkingDaily).count()

        print("\n1) API에서 실제 면수 가져오는 중...")
        capacity_map = fetch_capacity_from_api()

        print("\n2) 공원별 합산 면수:")
        for lot_id, cap in sorted(capacity_map.items()):
            lot_name = LOT_INFO.get(lot_id, {}).get("lot_name", f"lot_id={lot_id}")
            print(f"   {lot_name}: {cap}면")

        if daily_count > 0:
            # parking_daily에 데이터가 있음 → DELETE 불가능
            # → capacity만 UPDATE하는 안전한 방식으로 자동 전환
            print(f"\n⚠️  parking_daily에 {daily_count:,}건 데이터 존재")
            print("   외래키 제약으로 인해 전체 재삽입이 불가능합니다.")
            print("   capacity만 안전하게 업데이트합니다. (--update-only와 동일 동작)\n")
            update_capacity_only(capacity_map)
        else:
            # parking_daily가 비어있음 → 안전하게 DELETE 후 재삽입 가능
            print("\n3) parking_info INSERT 중...")
            insert_parking_info(capacity_map)

        verify()
