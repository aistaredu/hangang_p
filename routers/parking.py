# routers/parking.py
# 주차장 관련 API — CRUD 5개
# 기존 수업의 todo.py와 동일한 구조
#
# ✅ 2회차 버그 수정:
#   1) POST body 타입: ParkingInfoResponse → ParkingCreateRequest (응답모델을 요청에 쓰면 안 됨)
#   2) PATCH body 타입: dict → ParkingUpdateRequest (Pydantic 검증 없는 dict 제거)
#   3) PATCH setattr 범위: id·created_at 수정 못 하도록 허용 필드 명시
#   4) GET 목록: 페이지네이션 추가 (page, size 파라미터)
#
# 📌 라우터(router): 관련 API들을 한 파일로 묶은 단위
# 📌 라우팅(routing): 요청(HTTP메서드+URL)을 어떤 함수가 처리할지 연결하는 과정

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from starlette import status

from database.db_connection import get_session
from models.models import ParkingInfo
from schema.request import ParkingCreateRequest, ParkingUpdateRequest
from schema.response import ParkingInfoResponse, ParkingListResponse
from auth.jwt import decode_access_token

# APIRouter: main.py의 app 대신 라우터에 API를 등록
# tags=["주차장"]: Swagger UI(/docs)에서 이 그룹 이름으로 묶임
router = APIRouter(tags=["주차장"])

# HTTPBearer(): 요청 헤더의 'Authorization: Bearer <토큰>' 을 자동으로 파싱하는 객체
# auto_error=False: Authorization 헤더가 없어도 오류 없이 None 반환
#   → 없으면 None, 있으면 HTTPAuthorizationCredentials 객체 반환
bearer = HTTPBearer(auto_error=False)


# ═════════════════════════════════════════════════════════════
# 전체 주차장 목록 조회 (페이지네이션 포함)
# GET /parking-lots?page=1&size=9
# 로그인 불필요 — 누구나 조회 가능
# ═════════════════════════════════════════════════════════════
@router.get(
    "/parking-lots",
    response_model=ParkingListResponse,   # 목록 + 총 개수 + 페이지 정보 반환
    status_code=status.HTTP_200_OK,
)
def get_parking_lots_handler(
    # Query(): URL 쿼리 파라미터 — ?page=1&size=9 형태로 전달
    # ge=1: page는 1 이상만 허용
    page: int = Query(default=1,  ge=1,  description="페이지 번호 (기본: 1)"),
    size: int = Query(default=9,  ge=1,  le=100, description="페이지당 항목 수 (기본: 9)"),
    session: Session = Depends(get_session),
):
    # ── 전체 주차장 수 조회 ─────────────────────────────────
    # func.count(): SQL의 COUNT() 함수
    # session.scalar(): 단일 값(숫자)을 반환하는 쿼리에 사용
    # SQL: SELECT COUNT(id) FROM parking_info;
    total = session.scalar(select(func.count(ParkingInfo.id)))

    # ── 페이지네이션 계산 ────────────────────────────────────
    # offset: 몇 번째 행부터 가져올지 (0-based)
    # 예) page=2, size=9 → offset=9 → 10번째 행부터 9개 가져옴
    offset = (page - 1) * size

    # ── 데이터 조회 ──────────────────────────────────────────
    # .offset(offset): 앞의 offset개 행 건너뜀 (SQL: OFFSET n)
    # .limit(size): 최대 size개만 가져옴 (SQL: LIMIT n)
    stmt = (
        select(ParkingInfo)
        .order_by(ParkingInfo.id)  # id 오름차순 정렬
        .offset(offset)
        .limit(size)
    )
    # session.execute(stmt): 쿼리를 실제 DB에 전달해 실행
    # .scalars().all(): 결과를 ORM 객체 리스트로 변환
    lots = session.execute(stmt).scalars().all()

    # ParkingListResponse 형태로 반환
    # total: 프론트에서 "총 N개" 표시 및 페이지 수 계산에 사용
    return ParkingListResponse(total=total, page=page, size=size, items=lots)


# ═════════════════════════════════════════════════════════════
# 단일 주차장 조회
# GET /parking-lots/{lot_id}
# ═════════════════════════════════════════════════════════════
@router.get(
    "/parking-lots/{lot_id}",  # {lot_id}: 경로 변수 — URL에서 추출해 함수 매개변수로 전달
    response_model=ParkingInfoResponse,
    status_code=status.HTTP_200_OK,
)
def get_parking_lot_handler(
    lot_id : int,              # 경로 변수는 함수 매개변수 이름과 일치해야 함
    session: Session = Depends(get_session),
):
    # select(ParkingInfo).where(...): SQL의 WHERE 절
    # SQL: SELECT * FROM parking_info WHERE id = lot_id;
    stmt = select(ParkingInfo).where(ParkingInfo.id == lot_id)

    # .scalars().first(): 첫 번째 결과만 반환, 없으면 None
    lot = session.execute(stmt).scalars().first()

    if lot:
        return lot

    # 조회 실패 시 예외 처리 — 기존 수업의 raise HTTPException 패턴과 동일
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="주차장을 찾을 수 없습니다",
    )


# ═════════════════════════════════════════════════════════════
# 주차장 등록 (관리자 전용)
# POST /parking-lots
#
# ✅ 버그 수정: body 타입을 ParkingInfoResponse → ParkingCreateRequest 로 변경
#   - ParkingInfoResponse는 응답 모델 (id, created_at 포함)
#   - id, created_at은 DB가 자동 생성하므로 요청 body에 있으면 안 됨
#   - ParkingCreateRequest는 클라이언트가 직접 보내야 할 필드만 정의
# ═════════════════════════════════════════════════════════════
@router.post(
    "/parking-lots",
    response_model=ParkingInfoResponse,
    status_code=status.HTTP_201_CREATED,  # 생성 성공: 201 Created
)
def create_parking_lot_handler(
    body   : ParkingCreateRequest,        # ✅ 수정: 요청 전용 모델 사용
    session: Session = Depends(get_session),
    # Depends(bearer): 요청 전에 HTTPBearer를 먼저 실행 → Authorization 헤더 파싱
    # 헤더가 있으면 HTTPAuthorizationCredentials 객체, 없으면 None
    authorization: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    # ── 관리자 권한 확인 ──────────────────────────────────────
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다",
        )
    # authorization.credentials: 실제 JWT 토큰 문자열
    token_data = decode_access_token(authorization.credentials)
    if token_data["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다",
            # 401: 인증 안 됨 (로그인 필요)
            # 403: 인증은 됐지만 권한 없음 (로그인은 했지만 관리자 아님)
        )

    # ── 주차장 객체 생성 & 저장 ───────────────────────────────
    # body.lot_name 등: Pydantic이 이미 타입·규칙 검증을 완료한 값
    lot = ParkingInfo(
        lot_name=body.lot_name,
        district=body.district,
        capacity=body.capacity,
        lat=body.lat,
        lng=body.lng,
        # id, created_at은 DB가 자동 생성 → 여기서 설정 안 함
    )
    session.add(lot)      # 세션에 등록 (아직 DB에 저장 안 됨)
    session.commit()      # DB에 실제 저장 (SQL INSERT 실행)
    session.refresh(lot)  # DB가 생성한 id, created_at 값을 lot 객체에 반영
    return lot


# ═════════════════════════════════════════════════════════════
# 주차장 수정 (관리자 전용)
# PATCH /parking-lots/{lot_id}
#
# ✅ 버그 수정 2가지:
#   1) body 타입: dict → ParkingUpdateRequest (Pydantic 검증 적용)
#   2) 수정 허용 필드 명시: id, created_at은 수정 불가
# ═════════════════════════════════════════════════════════════
@router.patch(
    "/parking-lots/{lot_id}",
    response_model=ParkingInfoResponse,
    status_code=status.HTTP_200_OK,
)
def update_parking_lot_handler(
    lot_id : int,
    body   : ParkingUpdateRequest,         # ✅ 수정: dict 대신 Pydantic 스키마 사용
    session: Session = Depends(get_session),
    authorization: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    # 관리자 권한 확인
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다")
    token_data = decode_access_token(authorization.credentials)
    if token_data["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다")

    stmt = select(ParkingInfo).where(ParkingInfo.id == lot_id)
    lot  = session.execute(stmt).scalars().first()

    if lot:
        # ── ✅ 수정 허용 필드만 선택적으로 업데이트 ───────────
        # ParkingUpdateRequest에 정의된 필드만 수정 가능
        # id, created_at은 ParkingUpdateRequest에 없으므로 수정 불가
        # body.model_dump(): Pydantic 모델을 dict로 변환
        # exclude_unset=True: 클라이언트가 실제로 보낸 필드만 포함 (None으로 보낸 것 제외)
        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(lot, key, value)  # lot.lot_name = value 와 동일

        session.commit()  # 변경사항 DB에 저장
        return lot

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="주차장을 찾을 수 없습니다")


# ═════════════════════════════════════════════════════════════
# 주차장 삭제 (관리자 전용)
# DELETE /parking-lots/{lot_id}
# ═════════════════════════════════════════════════════════════
@router.delete(
    "/parking-lots/{lot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # 204 No Content: 요청은 성공했지만 반환할 본문이 없음
    # 삭제 성공 후 응답 본문이 없는 것이 REST 표준
)
def delete_parking_lot_handler(
    lot_id : int,
    session: Session = Depends(get_session),
    authorization: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    # 관리자 권한 확인
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다")
    token_data = decode_access_token(authorization.credentials)
    if token_data["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다")

    stmt = select(ParkingInfo).where(ParkingInfo.id == lot_id)
    lot  = session.execute(stmt).scalars().first()

    if lot:
        session.delete(lot)  # 세션에서 삭제 대상으로 지정
        session.commit()     # DB에서 실제 삭제 (SQL DELETE 실행)
        return               # 204이므로 본문 없이 반환

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="주차장을 찾을 수 없습니다")
