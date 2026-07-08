# schema/response.py
# API 응답 본문 모델
#
# ✅ 핵심 수정: model_config = ConfigDict(from_attributes=True) 추가
#
# 📌 from_attributes=True 가 필요한 이유:
#   FastAPI는 라우터 함수에서 ORM 객체(ParkingInfo, User 등)를 반환합니다.
#   Pydantic v2는 기본적으로 dict만 받을 수 있습니다.
#   from_attributes=True 를 설정해야 ORM 객체의 속성을 읽어서
#   자동으로 JSON으로 변환할 수 있습니다.
#
#   ❌ 없을 때: "Input should be a valid dictionary or instance of ..."
#   ✅ 있을 때: ORM 객체 → Pydantic 모델 → JSON 자동 변환

from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


# =============================================================
# 공통 기반 클래스
# =============================================================
class BaseResponse(BaseModel):
    """
    모든 응답 모델의 부모 클래스
    from_attributes=True: ORM 객체를 Pydantic이 직접 읽을 수 있게 허용
    여기 한 번만 설정하면 상속받는 모든 클래스에 자동 적용됩니다.
    """
    model_config = ConfigDict(from_attributes=True)
    # ConfigDict: Pydantic v2의 모델 설정 방식
    # from_attributes=True:
    #   obj.id, obj.lot_name 처럼 객체의 속성(attribute)으로 값을 읽도록 허용
    #   SQLAlchemy ORM 객체와 함께 사용할 때 필수


# =============================================================
# 주차장 응답 모델
# =============================================================

class ParkingInfoResponse(BaseResponse):
    """
    주차장 단일 조회 응답 모델
    ORM ParkingInfo 객체를 JSON으로 변환할 때 사용
    """
    id      : int
    lot_name: str
    district: str
    capacity: int
    lat     : float
    lng     : float


class ParkingListResponse(BaseResponse):
    """
    주차장 목록 + 페이지네이션 응답 모델
    GET /parking-lots?page=1&size=9 에서 사용
    """
    total: int
    page : int
    size : int
    items: list[ParkingInfoResponse]


# =============================================================
# 회원 응답 모델
# =============================================================

class UserSignUpResponse(BaseResponse):
    """
    회원가입 성공 응답 모델
    hashed_password 등 민감 정보는 절대 포함하지 않음
    """
    id        : int
    email     : str
    name      : str
    created_at: datetime


# =============================================================
# 예약 응답 모델
# =============================================================

class ReservationResponse(BaseResponse):
    """예약 생성 응답 모델"""
    id           : int
    lot_id       : int
    reserved_date: date
    status       : str
    created_at   : datetime


class ReservationDetailResponse(BaseResponse):
    """
    내 예약 목록 응답 모델
    ORM relationship으로 가져온 주차장명(lot_name)도 포함
    """
    id           : int
    lot_id       : int
    lot_name     : str
    reserved_date: date
    status       : str
    created_at   : datetime


# =============================================================
# ML 예측 응답 모델
# =============================================================

class PredictResponse(BaseResponse):
    """ML 예측 결과 응답 모델"""
    lot_id          : int
    lot_name        : str
    target_date     : date
    capacity        : int
    predicted_spaces: int
    occupancy_pct   : float
