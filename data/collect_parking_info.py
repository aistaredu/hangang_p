# =============================================================
# data/collect_parking_info.py
# 한강공원 주차장 11개소 기본 정보 → parking_info 테이블 INSERT
# =============================================================
# 📌 역할:
#   한강공원 주차장 11개소의 이름·지구명·총면수·위경도를
#   parking_info 테이블에 삽입합니다.
#
# 📌 데이터 출처:
#   서울 열린데이터광장 OA-21083 (주차장 정보)
#   + 카카오맵에서 직접 확인한 위도·경도 좌표
#
# 📌 실행 방법:
#   PyCharm 터미널에서: python data/collect_parking_info.py
#   또는 PyCharm에서 이 파일 우클릭 → Run
#
# 📌 실행 빈도:
#   주차장 정보는 거의 변하지 않으므로 처음 한 번만 실행합니다.
#   여러 번 실행해도 안전합니다 (멱등성: 기존 데이터 삭제 후 재삽입).
# =============================================================

import sys
import os

# ─────────────────────────────────────────────────────────────
# 프로젝트 루트를 Python 경로에 추가
#
# 이 파일은 data/ 폴더 안에 있어서 database/, models/ 폴더를
# 직접 import할 수 없습니다.
# sys.path.append()로 프로젝트 루트를 경로에 추가해야
# "from database.db_connection import ..." 같은 임포트가 동작합니다.
#
# os.path.abspath(__file__):
#   현재 파일의 절대 경로
#   예) C:\Users\student\Desktop\hangang_parking\data\collect_parking_info.py
#
# os.path.dirname() 1번:
#   파일이 있는 폴더 → C:\...\hangang_parking\data
#
# os.path.dirname() 2번:
#   그 상위 폴더 → C:\...\hangang_parking  ← 프로젝트 루트
#
# sys.path.append():
#   Python이 모듈을 찾는 경로 목록에 추가
# ─────────────────────────────────────────────────────────────
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 경로 추가 후 프로젝트 내 모듈을 임포트할 수 있습니다
from database.db_connection import SessionFactory  # 세션 팩토리 (DB 연결 도구)
from models.models import ParkingInfo              # 주차장 ORM 모델


# =============================================================
# 한강공원 주차장 11개소 데이터 (상수)
#
# capacity : OA-21083에서 확인한 총 주차면수
# lat, lng : 카카오맵에서 확인한 위도·경도
#            → 5회차 카카오맵 마커 위치로 사용됩니다
#
# 딕셔너리 리스트(list of dict) 형태로 관리합니다.
# 새 주차장이 생기면 이 리스트에 항목을 추가하면 됩니다.
# =============================================================
HANGANG_LOTS = [
    {"lot_name": "뚝섬한강공원주차장",   "district": "뚝섬지구",   "capacity": 458, "lat": 37.5302, "lng": 127.0688},
    {"lot_name": "여의도한강공원주차장",  "district": "여의도지구", "capacity": 532, "lat": 37.5285, "lng": 126.9337},
    {"lot_name": "반포한강공원주차장",   "district": "반포지구",   "capacity": 390, "lat": 37.5126, "lng": 126.9995},
    {"lot_name": "잠원한강공원주차장",   "district": "잠원지구",   "capacity": 155, "lat": 37.5166, "lng": 126.9994},
    {"lot_name": "망원한강공원주차장",   "district": "망원지구",   "capacity": 298, "lat": 37.5494, "lng": 126.8975},
    {"lot_name": "난지한강공원주차장",   "district": "난지지구",   "capacity": 610, "lat": 37.5663, "lng": 126.8906},
    {"lot_name": "강서한강공원주차장",   "district": "강서지구",   "capacity": 425, "lat": 37.5736, "lng": 126.8241},
    {"lot_name": "양화한강공원주차장",   "district": "양화지구",   "capacity": 124, "lat": 37.5454, "lng": 126.9101},
    {"lot_name": "이촌한강공원주차장",   "district": "이촌지구",   "capacity": 303, "lat": 37.5210, "lng": 126.9726},
    {"lot_name": "잠실한강공원주차장",   "district": "잠실지구",   "capacity": 390, "lat": 37.5200, "lng": 127.0818},
    {"lot_name": "광나루한강공원주차장", "district": "광나루지구", "capacity": 450, "lat": 37.5492, "lng": 127.1266},
]


# =============================================================
# insert_parking_info() — 주차장 데이터 INSERT
# =============================================================
def insert_parking_info():
    """
    HANGANG_LOTS 데이터를 parking_info 테이블에 삽입합니다.

    멱등성(Idempotency):
        같은 함수를 몇 번 실행해도 결과가 동일합니다.
        실행할 때마다 기존 데이터를 모두 삭제하고 새로 삽입하기 때문입니다.
        → 데이터를 수정하고 싶으면 HANGANG_LOTS를 바꾸고 다시 실행하면 됩니다.
    """

    # ── 세션 열기 ────────────────────────────────────────────
    # with SessionFactory() as session:
    #   with 문이 끝날 때 session.close()를 자동으로 호출합니다.
    #   try/finally를 따로 작성하지 않아도 세션이 안전하게 닫힙니다.
    with SessionFactory() as session:

        # ── 기존 데이터 삭제 ──────────────────────────────────
        # session.query(ParkingInfo).delete():
        #   SQL: DELETE FROM parking_info;
        #   parking_info 테이블의 모든 행을 삭제합니다.
        #   반환값: 삭제된 행의 수
        deleted = session.query(ParkingInfo).delete()
        if deleted:
            print(f"  기존 {deleted}개 레코드 삭제 (재실행으로 데이터 갱신)")

        # ── 새 데이터 INSERT ──────────────────────────────────
        for lot_data in HANGANG_LOTS:
            # ParkingInfo 객체 생성 — 아직 DB에 저장되지 않은 상태
            # 딕셔너리의 각 키를 ParkingInfo의 속성에 맞게 전달합니다.
            lot = ParkingInfo(
                lot_name=lot_data["lot_name"],
                district=lot_data["district"],
                capacity=lot_data["capacity"],
                lat     =lot_data["lat"],
                lng     =lot_data["lng"],
                # id, created_at 은 DB가 자동 생성 → 여기서 설정 안 함
            )

            # session.add(lot):
            #   세션에 객체를 등록합니다.
            #   아직 SQL INSERT가 실행되지 않은 상태입니다.
            #   (commit() 호출 시 실제로 DB에 저장됩니다)
            session.add(lot)
            print(f"  ✅ {lot_data['lot_name']} ({lot_data['capacity']}면)")

        # ── DB에 저장 ─────────────────────────────────────────
        # session.commit():
        #   세션에 add()된 모든 객체를 DB에 실제로 저장합니다.
        #   이 줄이 실행되는 순간 SQL INSERT 11개가 한꺼번에 실행됩니다.
        #   ⚠️ commit()을 호출하지 않으면 데이터가 저장되지 않습니다.
        session.commit()
        print(f"\n✅ parking_info INSERT 완료: {len(HANGANG_LOTS)}개소")


# =============================================================
# verify() — 삽입 결과 조회 & 출력
# =============================================================
def verify():
    """INSERT된 데이터를 조회해서 터미널에 출력합니다."""

    with SessionFactory() as session:
        from sqlalchemy import select

        # select(ParkingInfo).order_by(ParkingInfo.id):
        #   SQL: SELECT * FROM parking_info ORDER BY id;
        # .scalars().all():
        #   결과를 ParkingInfo 객체 리스트로 변환
        lots = session.execute(
            select(ParkingInfo).order_by(ParkingInfo.id)
        ).scalars().all()

        print(f"\n[parking_info 확인] 총 {len(lots)}개소")

        for lot in lots:
            # float(lot.lat): Numeric 타입을 float으로 변환해야 f-string에서 사용 가능
            # :.4f: 소수점 4자리까지 표시
            print(
                f"  {lot.id:>2}. "          # id (오른쪽 정렬 2자리)
                f"{lot.lot_name} "           # 주차장명
                f"({lot.capacity}면) "       # 총 주차면수
                f"[{float(lot.lat):.4f}, "   # 위도 소수점 4자리
                f"{float(lot.lng):.4f}]"     # 경도 소수점 4자리
            )


# =============================================================
# 직접 실행 시 동작
# python data/collect_parking_info.py 로 실행할 때만 동작합니다.
# 다른 파일에서 import 할 때는 실행되지 않습니다.
# =============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("한강공원 주차장 기본 정보 수집")
    print("=" * 55)
    insert_parking_info()  # 데이터 삽입
    verify()               # 결과 확인
