# =============================================================
# data/insert_holidays.py
# 한국 공휴일 자동 삽입 → holidays 테이블
# =============================================================
# 📌 역할:
#   Python의 holidays 라이브러리를 사용해
#   2022~2024년 한국 공휴일(대체공휴일 포함)을
#   holidays 테이블에 자동으로 삽입합니다.
#
# 📌 왜 공휴일 데이터가 필요한가?
#   한강공원 주차장 혼잡도는 공휴일에 크게 달라집니다.
#   같은 화요일이라도 공휴일 화요일은 주말처럼 혼잡합니다.
#   ML 모델이 이 차이를 학습하려면 is_holiday 피처가 필요합니다.
#
#   ML 학습 쿼리에서 사용 방식:
#     LEFT JOIN holidays h ON parking_daily.use_date = h.holiday_date
#     → h.holiday_date IS NOT NULL 이면 is_holiday = 1
#
# 📌 실행 방법:
#   python data/insert_holidays.py
#
# 📌 실행 빈도:
#   처음 한 번만 실행합니다.
#   여러 번 실행해도 안전합니다 (중복 확인 후 스킵).
# =============================================================

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
# (data/ 폴더에서 database/, models/ 임포트를 위해 필요)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# holidays 라이브러리를 'kr_holidays_lib'라는 별칭으로 임포트
# → 아래에서 정의할 Holiday ORM 클래스와 이름이 겹치는 것을 방지
import holidays as kr_holidays_lib

from sqlalchemy import select, func           # ORM 쿼리 도구
from database.db_connection import SessionFactory
from models.models import Holiday             # 공휴일 ORM 모델


# =============================================================
# insert_holidays() — 공휴일 데이터 INSERT
# =============================================================
def insert_holidays(years: list = [2022, 2023, 2024]):
    """
    지정한 연도의 한국 공휴일을 holidays 테이블에 삽입합니다.

    Args:
        years: 삽입할 연도 리스트 (기본: 2022, 2023, 2024년)
               예) [2025, 2026] 처럼 변경하면 다른 연도도 추가 가능

    특징:
        - 대체공휴일 자동 포함 (설날·추석이 주말과 겹치는 경우)
        - 이미 있는 날짜는 스킵 (중복 방지)
        - 여러 번 실행해도 데이터가 늘어나지 않음 (멱등성)
    """

    # ── 공휴일 딕셔너리 생성 ──────────────────────────────────
    # holidays.KR(years=[...]):
    #   한국 공휴일을 자동 계산해서 딕셔너리로 반환합니다.
    #   형식: {날짜객체: "공휴일이름", ...}
    #   예)  {date(2024, 1, 1): "New Year's Day",
    #         date(2024, 2, 9): "Korean New Year",
    #         date(2024, 2, 12): "Korean New Year (substituted)", ...}
    #
    #   대체공휴일(substituted)도 자동으로 포함됩니다.
    #   예) 설날이 일요일이면 그 다음 날 월요일이 대체공휴일로 생성됩니다.
    kr = kr_holidays_lib.KR(years=years)

    with SessionFactory() as session:
        inserted = 0  # 새로 삽입한 개수 카운터
        skipped  = 0  # 이미 있어서 스킵한 개수 카운터

        # sorted(kr.items()):
        #   딕셔너리의 (날짜, 이름) 쌍을 날짜 오름차순으로 정렬해서 반복
        #   정렬하지 않으면 순서가 불규칙할 수 있습니다.
        for d, name in sorted(kr.items()):
            # d    : 날짜 객체  예) date(2024, 1, 1)
            # name : 공휴일 이름  예) "New Year's Day"

            # ── 중복 확인 ────────────────────────────────────
            # 같은 날짜가 이미 테이블에 있는지 확인합니다.
            # select(Holiday).where(...): 해당 날짜의 행 조회 쿼리 생성
            # session.scalar(): 단일 값 반환 (있으면 Holiday 객체, 없으면 None)
            # SQL: SELECT * FROM holidays WHERE holiday_date = d LIMIT 1;
            stmt   = select(Holiday).where(Holiday.holiday_date == d)
            exists = session.scalar(stmt)

            if exists:
                # 이미 있으면 INSERT하지 않고 다음으로 넘어갑니다.
                skipped += 1
                continue  # for 루프의 다음 반복으로 이동

            # ── 새 공휴일 객체 생성 & 세션에 추가 ────────────
            # Holiday 객체를 생성하고 세션에 등록합니다.
            # 아직 SQL INSERT가 실행되지 않은 상태입니다.
            session.add(Holiday(holiday_date=d, holiday_name=name))
            inserted += 1
            print(f"  ✅ {d} : {name}")

        # ── 한 번에 DB에 저장 ─────────────────────────────────
        # 루프 안에서 매번 commit하면 DB I/O가 많아져 느립니다.
        # 모든 객체를 세션에 add()한 뒤 마지막에 한 번만 commit합니다.
        # → SQL INSERT 여러 개를 묶어서 한 번의 트랜잭션으로 처리합니다.
        session.commit()
        print(
            f"\n✅ 완료: {inserted}개 삽입 / "
            f"{skipped}개 스킵 "
            f"({years[0]}~{years[-1]}년)"
        )


# =============================================================
# verify() — 삽입 결과 연도별 집계 확인
# =============================================================
def verify():
    """삽입된 공휴일을 연도별로 집계해서 출력합니다."""

    with SessionFactory() as session:
        # ── 연도별 집계 쿼리 ──────────────────────────────────
        # func.year(): SQL의 YEAR() 함수 — 날짜에서 연도만 추출
        #   예) date(2024, 1, 1) → 2024
        # func.count(): SQL의 COUNT() 함수 — 행 수 집계
        # .label("별칭"): 쿼리 결과 컬럼에 이름을 붙입니다
        #   (row.year, row.count 처럼 접근하기 위해 필요)
        #
        # SQL로 표현하면:
        #   SELECT YEAR(holiday_date) AS year, COUNT(*) AS count
        #   FROM holidays
        #   GROUP BY YEAR(holiday_date)
        #   ORDER BY YEAR(holiday_date);
        result = session.execute(
            select(
                func.year(Holiday.holiday_date).label("year"),   # 연도 추출
                func.count(Holiday.holiday_date).label("count"), # 해당 연도 공휴일 수
            )
            .group_by(func.year(Holiday.holiday_date))   # 연도별로 묶기
            .order_by(func.year(Holiday.holiday_date))   # 연도 오름차순 정렬
        ).all()
        # .all(): 결과를 Row 객체 리스트로 반환
        #   각 Row는 row.year, row.count 처럼 접근 가능

        print("\n[공휴일 연도별 현황]")
        total = 0
        for row in result:
            print(f"  {row.year}년: {row.count}일")
            total += row.count
        print(f"  합계: {total}일")


# =============================================================
# 직접 실행 시 동작
# =============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("한국 공휴일 삽입 (2022~2024년)")
    print("=" * 55)
    insert_holidays()  # 공휴일 삽입
    verify()           # 결과 확인
