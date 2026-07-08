# =============================================================
# routers/reservation.py
# 예약 관련 API — 생성 · 목록 조회 · 취소
# 기존 수업의 todo.py 구조와 동일 (JWT Bearer 인증 적용)
# =============================================================
# 📌 4회차에서 완성되는 API:
#   POST   /reservations              → 예약 생성 (로그인 필수)
#   GET    /reservations/me           → 내 예약 목록 (상태 필터)
#   DELETE /reservations/{id}         → 예약 취소 (본인만)
#
# 📌 보안 설계 원칙:
#   모든 API에 JWT 토큰 검증이 있습니다.
#   GET/DELETE 모두 user_id 조건을 추가해서
#   다른 사람의 예약에 접근하거나 취소할 수 없습니다.
#   (기존 수업 todo.py의 user_id 조건과 동일한 패턴)
# =============================================================

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from database.db_connection import get_session
from models.models          import Reservation, ParkingInfo
from schema.request         import ReservationCreateRequest
from schema.response        import ReservationResponse, ReservationDetailResponse
from auth.jwt               import decode_access_token

# APIRouter: main.py의 app 대신 라우터에 API를 등록
# tags=["예약"]: Swagger UI에서 "예약" 그룹으로 묶임
router = APIRouter(tags=["예약"])

# HTTPBearer(auto_error=False):
#   - Authorization: Bearer {토큰} 헤더를 자동으로 파싱합니다.
#   - auto_error=False: 헤더가 없어도 오류를 내지 않고 None을 반환합니다.
#     → 있으면 HTTPAuthorizationCredentials 객체, 없으면 None
#     → None이면 코드에서 직접 401 처리
bearer = HTTPBearer(auto_error=False)


# =============================================================
# 예약 생성
# POST /reservations
# 로그인 필수 — JWT 토큰으로 user_id 추출
# =============================================================
@router.post(
    "/reservations",
    response_model=ReservationResponse,  # 생성된 예약 정보 반환
    status_code=status.HTTP_201_CREATED, # 리소스 생성 성공: 201
)
def create_reservation_handler(
    body   : ReservationCreateRequest,   # lot_id, reserved_date 검증
    session: Session = Depends(get_session),
    # Depends(bearer): 요청 처리 전에 HTTPBearer를 먼저 실행 → Authorization 헤더 파싱
    # 기존 수업 todo.py의 Depends(bearer) 패턴과 동일
    authorization: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    """
    예약 생성 처리 순서:
        1) JWT 토큰에서 user_id 추출 (로그인 확인)
        2) 주차장 존재 여부 확인
        3) Reservation 객체 생성 & DB 저장
        4) 생성된 예약 정보 반환
    """

    # ── 1) 로그인 확인 ────────────────────────────────────────
    # authorization이 None이면 Authorization 헤더가 없는 것 → 비로그인
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다",
        )
    # authorization.credentials: Authorization 헤더에서 추출한 JWT 토큰 문자열
    # decode_access_token(): 서명 검증 + 만료 확인 후 payload 반환
    token_data = decode_access_token(authorization.credentials)
    user_id    = token_data["user_id"]  # 토큰에서 사용자 ID 추출

    # ── 2) 주차장 존재 여부 확인 ─────────────────────────────
    # 존재하지 않는 주차장에 예약을 만들면 안 됩니다.
    # SQL: SELECT * FROM parking_info WHERE id = body.lot_id LIMIT 1;
    stmt = select(ParkingInfo).where(ParkingInfo.id == body.lot_id)
    lot  = session.scalar(stmt)  # 없으면 None 반환
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="주차장을 찾을 수 없습니다",
        )

    # ── 3) 예약 객체 생성 & DB 저장 ─────────────────────────
    # user_id는 클라이언트가 보내는 것이 아니라 JWT에서 추출합니다.
    # → 클라이언트가 다른 사람의 user_id로 예약을 만들 수 없습니다.
    reservation = Reservation(
        user_id      =user_id,             # JWT에서 추출 (클라이언트 입력값 아님)
        lot_id       =body.lot_id,         # 클라이언트 입력값
        reserved_date=body.reserved_date,  # 클라이언트 입력값
        status       ="active",            # 초기 상태: 예약중
        # id, created_at은 DB가 자동 생성
    )
    session.add(reservation)      # 세션에 등록 (SQL INSERT 아직 실행 안 됨)
    session.commit()              # SQL INSERT 실행 → DB에 저장
    session.refresh(reservation)  # DB가 생성한 id, created_at 값 반영

    return reservation  # ReservationResponse 형식으로 자동 변환


# =============================================================
# 내 예약 목록 조회
# GET /reservations/me
# GET /reservations/me?reservation_status=active   (상태 필터)
# GET /reservations/me?reservation_status=cancelled
# 로그인 필수
# =============================================================
@router.get(
    "/reservations/me",
    response_model=list[ReservationDetailResponse],  # 주차장명 포함한 상세 응답
    status_code=status.HTTP_200_OK,
)
def get_my_reservations_handler(
    # 쿼리 파라미터: URL에 ?reservation_status=active 형태로 전달
    # 기본값이 None이므로 파라미터를 생략하면 전체 예약 목록 반환
    reservation_status: str | None = None,
    session: Session = Depends(get_session),
    authorization: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    """
    내 예약 목록 조회.
    reservation_status 파라미터로 상태별 필터링 가능:
        미입력   → 전체 예약 목록
        active   → 예약중만
        cancelled → 취소된 것만
        completed → 완료된 것만
    """

    # 로그인 확인 — 기존 수업 todo.py 패턴과 동일
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다")
    token_data = decode_access_token(authorization.credentials)
    user_id    = token_data["user_id"]

    # ── 내 예약만 조회 ────────────────────────────────────────
    # where(Reservation.user_id == user_id):
    #   로그인한 사람의 예약만 가져옵니다.
    #   다른 사람의 예약은 절대 조회되지 않습니다.
    #   기존 수업 todo.py의 where(Todo.user_id == user_id) 패턴과 동일
    stmt = select(Reservation).where(Reservation.user_id == user_id)

    # ── 상태 필터 (선택적 추가 조건) ─────────────────────────
    if reservation_status:
        # reservation_status가 있을 때만 WHERE 조건 추가
        # SQL: ... AND status = 'active'
        stmt = stmt.where(Reservation.status == reservation_status)

    # ── 최신 예약 먼저 정렬 ──────────────────────────────────
    # SQL: ORDER BY created_at DESC
    stmt = stmt.order_by(Reservation.created_at.desc())

    # 쿼리 실행 → ORM 객체 리스트로 변환
    # .scalars().all(): 결과를 Reservation 객체 리스트로 반환
    reservations = session.execute(stmt).scalars().all()

    # ── 응답 데이터 조합 ─────────────────────────────────────
    # ReservationDetailResponse에는 lot_name이 포함되어 있습니다.
    # ORM relationship(r.lot)으로 주차장 정보를 추가 쿼리 없이 접근합니다.
    #
    # r.lot:
    #   Reservation 모델의 relationship("ParkingInfo") 덕분에
    #   r.lot으로 ParkingInfo 객체에 바로 접근 가능합니다.
    #   SQL로는 JOIN이 필요하지만 ORM은 속성 접근으로 처리합니다.
    result = []
    for r in reservations:
        result.append(ReservationDetailResponse(
            id           =r.id,
            lot_id       =r.lot_id,
            lot_name     =r.lot.lot_name,  # ORM relationship → ParkingInfo.lot_name
            reserved_date=r.reserved_date,
            status       =r.status,
            created_at   =r.created_at,
        ))
    return result


# =============================================================
# 예약 취소
# DELETE /reservations/{reservation_id}
# 본인 예약만 취소 가능 — 소프트 삭제 (DB에서 삭제 아닌 상태 변경)
# =============================================================
@router.delete(
    "/reservations/{reservation_id}",  # {reservation_id}: 경로 변수
    status_code=status.HTTP_204_NO_CONTENT,
    # 204 No Content: 처리는 성공했지만 반환할 본문이 없음
    # 삭제(취소) 성공 후 응답 본문이 없는 것이 REST 표준
)
def cancel_reservation_handler(
    reservation_id: int,   # URL의 {reservation_id} 값이 자동으로 매핑됨
    session: Session = Depends(get_session),
    authorization: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    """
    예약 취소 (소프트 삭제):
        실제로 DB에서 삭제하지 않고 status를 'cancelled'로 변경합니다.
        이력 보존이 가능하고, 실수로 취소했을 때 복구할 수 있습니다.

    보안:
        user_id 조건을 추가해서 본인 예약만 취소 가능합니다.
        기존 수업 todo.py의 where(Todo.user_id == user_id) 패턴과 동일
    """

    # 로그인 확인
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다")
    token_data = decode_access_token(authorization.credentials)
    user_id    = token_data["user_id"]

    # ── 본인 예약 조회 ────────────────────────────────────────
    # 두 가지 조건을 동시에 만족해야 합니다:
    #   1) reservation.id == reservation_id (해당 예약)
    #   2) reservation.user_id == user_id   (본인 예약)
    # 두 조건 중 하나라도 만족 안 하면 None → 404 반환
    # → 다른 사람 예약 ID를 넣어도 취소할 수 없습니다.
    stmt = select(Reservation).where(
        Reservation.id      == reservation_id,
        Reservation.user_id == user_id,  # 본인 예약만
    )
    reservation = session.execute(stmt).scalars().first()

    if reservation:
        # ── 취소 가능한 상태인지 확인 ────────────────────────
        # active 상태가 아니면 이미 취소됐거나 완료된 예약
        # cancelled나 completed는 다시 취소할 수 없습니다.
        if reservation.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="취소 가능한 예약이 아닙니다",
                # 400 Bad Request: 요청 자체는 맞지만 처리할 수 없는 상태
            )

        # ── 소프트 삭제 (상태만 변경) ────────────────────────
        # session.delete(reservation) 으로 실제 삭제하지 않고
        # status 컬럼만 'cancelled'로 변경합니다.
        # SQL: UPDATE reservation SET status = 'cancelled' WHERE id = reservation_id;
        reservation.status = "cancelled"
        session.commit()   # 변경사항 DB에 저장

        return             # 204이므로 본문 없이 반환

    # 해당 예약이 없거나 본인 예약이 아닌 경우
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="예약을 찾을 수 없습니다",
    )
