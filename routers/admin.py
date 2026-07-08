# =============================================================
# routers/admin.py
# 관리자 전용 API — 통계·회원·예약 관리
# =============================================================
# 📌 제공 API 목록:
#   GET /admin/stats/summary   — 대시보드 요약 카드용 집계(회원/예약/오늘/활성)  ← 신규
#   GET /admin/stats/daily     — 요일별 평균 혼잡도 (막대그래프)
#   GET /admin/stats/monthly   — 월별 평균 혼잡도 (막대그래프)
#   GET /admin/stats/hourly    — 시간대별 예약 건수 (막대그래프)             ← 복구
#   GET /admin/users           — 회원 목록 (페이지네이션)
#   GET /admin/reservations    — 예약 목록 (페이지네이션)
#
# 📌 공통 보안 패턴:
#   get_admin_user_id()를 Depends()로 주입 → "JWT 검증 + 관리자 확인"을 재사용.
# =============================================================

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from starlette import status

from database.db_connection import get_session
from models.models import ParkingInfo, ParkingDaily, User, Reservation
from auth.jwt import decode_access_token

# tags=["관리자"]: Swagger UI(/docs)에서 이 그룹으로 묶여 표시됨
router = APIRouter(tags=["관리자"])

# auto_error=False: Authorization 헤더가 없어도 예외를 던지지 않고 None 반환
#   → 헤더 없음(로그인 안 됨)을 우리가 직접 401로 처리하기 위함
bearer = HTTPBearer(auto_error=False)


# =============================================================
# get_admin_user_id() — 관리자 권한 확인 공통 함수
# =============================================================
def get_admin_user_id(
    authorization: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> int:
    """
    JWT 토큰을 검증하고 관리자 권한을 확인한다.
    모든 관리자 API에서 Depends()로 재사용한다.

    Returns: 관리자 user_id
    Raises :
        401: 토큰 없음(로그인 안 됨)
        403: 관리자 아님(role != "admin")
    """
    # 헤더 자체가 없으면 로그인하지 않은 상태 → 401
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다",
        )
    # 토큰 해독 + 서명 검증. 내부 정보(user_id, role)를 꺼냄
    token_data = decode_access_token(authorization.credentials)
    # 로그인은 했지만 일반 회원이면 접근 금지 → 403
    if token_data["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다",
        )
    return token_data["user_id"]


# =============================================================
# GET /admin/stats/summary — 대시보드 요약 카드 집계  (신규)
# =============================================================
@router.get("/admin/stats/summary", status_code=status.HTTP_200_OK)
def get_summary_stats_handler(
    session : Session = Depends(get_session),
    admin_id: int     = Depends(get_admin_user_id),
):
    """
    대시보드 상단 4개 카드(총 회원/총 예약/오늘 예약/활성 예약)를
    '서버에서 직접 집계'해 반환한다.

    📌 왜 이 API가 필요한가:
      기존 프론트(admin.html)는 예약 전체를 size=1000으로 받아와
      JS에서 filter로 오늘·활성 건수를 셌다. 그 방식은
        - 예약이 1000건을 넘으면 초과분이 누락되어 숫자가 틀려지고
        - 매번 대량 데이터를 전송해 비효율적이다.
      → COUNT를 DB에서 계산하면 정확하고 가볍다.
    """
    # 총 회원 수: SELECT COUNT(id) FROM user
    total_users = session.scalar(select(func.count(User.id)))

    # 총 예약 수: SELECT COUNT(id) FROM reservation
    total_reservations = session.scalar(select(func.count(Reservation.id)))

    # 오늘 예약 수: reserved_date가 오늘(CURDATE())인 예약 개수
    #   func.current_date(): DB의 CURRENT_DATE / CURDATE()에 해당
    today_reservations = session.scalar(
        select(func.count(Reservation.id))
        .where(Reservation.reserved_date == func.current_date())
    )

    # 활성 예약 수: status가 'active'인 예약 개수
    active_reservations = session.scalar(
        select(func.count(Reservation.id))
        .where(Reservation.status == "active")
    )

    # scalar 결과가 None일 가능성(빈 테이블)에 대비해 or 0으로 방어
    return {
        "total_users"        : total_users or 0,
        "total_reservations" : total_reservations or 0,
        "today_reservations" : today_reservations or 0,
        "active_reservations": active_reservations or 0,
    }


# =============================================================
# GET /admin/stats/daily — 요일별 평균 혼잡도
# =============================================================
@router.get("/admin/stats/daily", status_code=status.HTTP_200_OK)
def get_daily_stats_handler(
    session : Session = Depends(get_session),
    admin_id: int     = Depends(get_admin_user_id),
):
    """
    요일별 평균 혼잡도(%)를 반환한다.
    admin.html의 '요일별' 막대그래프에 사용된다.

    📌 SQL 개념:
      SELECT DAYOFWEEK(use_date) AS day_of_week,
             ROUND(AVG(daily_count / capacity * 100), 1) AS avg_occupancy_pct
      FROM parking_daily JOIN parking_info ...
      GROUP BY DAYOFWEEK(use_date)
    """
    stmt = (
        select(
            # dayofweek(): 요일 숫자(1=일 ~ 7=토) 추출
            func.dayofweek(ParkingDaily.use_date).label("day_of_week"),
            # 회전율(이용률)% = 이용대수/총면수*100 의 평균 (100% 초과 정상)
            func.round(
                func.avg(ParkingDaily.daily_count / ParkingInfo.capacity * 100), 1
            ).label("avg_occupancy_pct"),
        )
        # 일별데이터에 주차장정보를 JOIN → capacity(총면수)를 쓸 수 있음
        .join(ParkingInfo, ParkingDaily.lot_id == ParkingInfo.id)
        # daily_count는 '하루 누적 이용대수(회전 포함)'라 100%를 넘는 게 정상이다.
        # (전체의 ~80%가 100% 초과) → 100% 초과를 제거하면 데이터 대부분을 버리므로
        # 제거하지 않고, 명백한 오류(0 이하, capacity 0)만 걸러 전체를 평균한다.
        .where(ParkingInfo.capacity > 0)
        .where(ParkingDaily.daily_count > 0)
        .group_by(func.dayofweek(ParkingDaily.use_date))   # 요일별로 묶기
        .order_by(func.dayofweek(ParkingDaily.use_date))   # 일→토 순 정렬
    )
    result = session.execute(stmt).all()

    # 요일 숫자를 한글로 바꾸기 위한 매핑
    day_names = {1: "일", 2: "월", 3: "화", 4: "수", 5: "목", 6: "금", 7: "토"}
    return [
        {
            "day_of_week"      : r.day_of_week,
            "day_name"         : day_names.get(r.day_of_week, ""),
            # 값이 None이면(데이터 없음) 0으로 방어
            "avg_occupancy_pct": float(r.avg_occupancy_pct or 0),
        }
        for r in result
    ]


# =============================================================
# GET /admin/stats/monthly — 월별 평균 혼잡도
# =============================================================
@router.get("/admin/stats/monthly", status_code=status.HTTP_200_OK)
def get_monthly_stats_handler(
    session : Session = Depends(get_session),
    admin_id: int     = Depends(get_admin_user_id),
):
    """
    월별 평균 혼잡도(%)를 반환한다.
    admin.html의 '월별' 막대그래프에 사용된다.
    (요일별과 구조 동일, month()만 다름)
    """
    stmt = (
        select(
            func.month(ParkingDaily.use_date).label("month"),   # 월(1~12) 추출
            func.round(
                func.avg(ParkingDaily.daily_count / ParkingInfo.capacity * 100), 1
            ).label("avg_occupancy_pct"),
        )
        .join(ParkingInfo, ParkingDaily.lot_id == ParkingInfo.id)
        # 회전율 평균(요일별과 동일 기준): 100% 초과는 정상이므로 제거하지 않음
        .where(ParkingInfo.capacity > 0)
        .where(ParkingDaily.daily_count > 0)
        .group_by(func.month(ParkingDaily.use_date))   # 월별로 묶기
        .order_by(func.month(ParkingDaily.use_date))   # 1→12월 정렬
    )
    result = session.execute(stmt).all()
    return [
        {"month": r.month, "avg_occupancy_pct": float(r.avg_occupancy_pct or 0)}
        for r in result
    ]


# =============================================================
# GET /admin/stats/hourly — 시간대별 예약 건수  (복구)
# =============================================================
@router.get("/admin/stats/hourly", status_code=status.HTTP_200_OK)
def get_hourly_stats_handler(
    session : Session = Depends(get_session),
    admin_id: int     = Depends(get_admin_user_id),
):
    """
    시간대별(0~23시) 예약 생성 건수를 반환한다.
    admin.html의 '시간대별' 막대그래프에 사용된다.

    📌 이 API는 프론트가 호출하는데 라우터에 빠져 있어 404가 났었다 → 복구.

    📌 SQL 개념:
      SELECT HOUR(created_at) AS hour, COUNT(*) AS count
      FROM reservation
      GROUP BY HOUR(created_at)

    📌 데이터가 없을 때:
      학습용 샘플 데이터로 그래프가 비어 보이지 않게 한다.
    """
    stmt = (
        select(
            func.hour(Reservation.created_at).label("hour"),   # 생성 시각의 '시(0~23)'
            func.count(Reservation.id).label("count"),         # 그 시간대 예약 개수
        )
        .group_by(func.hour(Reservation.created_at))
        .order_by(func.hour(Reservation.created_at))
    )
    result = session.execute(stmt).all()

    if result:
        # 실제 데이터가 있을 때: {시간: 건수} 딕셔너리로 변환
        hour_map = {r.hour: int(r.count) for r in result}
        # 0~23시를 모두 채운다(데이터 없는 시간은 0 → 그래프 빈칸 방지)
        return [{"hour": h, "avg_count": hour_map.get(h, 0)} for h in range(24)]
    else:
        # 데이터가 전혀 없을 때: 한강공원 이용 패턴을 흉내낸 샘플
        # 인덱스가 곧 시(0~23), 값이 예약 건수(오전 10시~오후 8시 집중)
        sample = [0,0,0,0,0,0,2,5,12,25,42,55,60,52,48,55,70,75,65,45,30,18,8,2]
        return [{"hour": h, "avg_count": sample[h]} for h in range(24)]


# =============================================================
# GET /admin/users — 회원 목록 (페이지네이션)
# =============================================================
@router.get("/admin/users", status_code=status.HTTP_200_OK)
def get_users_handler(
    # Query(): URL 쿼리 파라미터(?page=1&size=20). ge/le로 허용 범위 제한
    page    : int        = Query(default=1,  ge=1),
    size    : int        = Query(default=20, ge=1, le=100),
    search  : str | None = Query(default=None, description="이메일 또는 이름 검색"),
    session : Session    = Depends(get_session),
    admin_id: int        = Depends(get_admin_user_id),
):
    """
    전체 회원 목록을 페이지네이션으로 반환한다.
    search가 있으면 이메일/이름 부분일치로 검색한다.
    """
    # 기본 쿼리
    stmt = select(User)

    # ── 검색 조건(있을 때만) ────────────────────────────────
    # SQLAlchemy 2.x에서는 | 연산으로 OR 조건을 표현할 수 있음
    if search:
        like = f"%{search}%"   # 양쪽 % → 부분 일치(LIKE '%키워드%')
        stmt = stmt.where(User.email.like(like) | User.name.like(like))

    # ── 전체 건수(검색 조건 반영) ──────────────────────────
    # stmt.subquery()로 감싸 그 행 수를 세면, 검색 결과 총 개수를 정확히 구할 수 있음
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))

    # ── 페이지네이션 적용해 실제 목록 조회 ──────────────────
    users = session.execute(
        stmt.order_by(User.created_at.desc())   # 최근 가입순
            .offset((page - 1) * size)          # 앞 페이지 건너뛰기
            .limit(size)                        # 이번 페이지 개수
    ).scalars().all()

    return {
        "total": total or 0,
        "page" : page,
        "size" : size,
        "items": [
            {
                "id"        : u.id,
                "email"     : u.email,
                "name"      : u.name,
                "role"      : u.role,
                "created_at": u.created_at,
                # ⚠️ 비밀번호(hashed_password)는 절대 응답에 넣지 않음(보안)
            }
            for u in users
        ],
    }


# =============================================================
# GET /admin/reservations — 예약 목록 (페이지네이션)
# =============================================================
@router.get("/admin/reservations", status_code=status.HTTP_200_OK)
def get_reservations_handler(
    page    : int     = Query(default=1,  ge=1),
    size    : int     = Query(default=20, ge=1, le=100),
    session : Session = Depends(get_session),
    admin_id: int     = Depends(get_admin_user_id),
):
    """전체 예약 목록을 페이지네이션으로 반환한다."""
    # 전체 예약 건수(페이지 수 계산용)
    total = session.scalar(select(func.count(Reservation.id)))

    # 최근 예약순으로 이번 페이지 분량만 조회
    reservations = session.execute(
        select(Reservation)
        .order_by(Reservation.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).scalars().all()

    return {
        "total": total or 0,
        "page" : page,
        "size" : size,
        "items": [
            {
                "id"           : r.id,
                "user_id"      : r.user_id,
                "lot_id"       : r.lot_id,
                # r.lot: Reservation→ParkingInfo 관계로 주차장 이름을 바로 참조
                "lot_name"     : r.lot.lot_name,
                "reserved_date": str(r.reserved_date),   # date → 문자열
                "status"       : r.status,
                "created_at"   : r.created_at,
            }
            for r in reservations
        ],
    }
