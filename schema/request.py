# =============================================================
# schema/request.py
# API 요청 본문 검증 모델
# 기존 수업의 request.py와 동일한 구조 (Pydantic BaseModel)
# =============================================================
# 📌 핵심 개념:
#   요청 모델(Request) = 클라이언트 → 서버로 보내는 데이터 구조
#   응답 모델(Response) = 서버 → 클라이언트로 돌려주는 데이터 구조
#   둘은 반드시 분리해야 합니다.
#
# 📌 Pydantic이 자동으로 해주는 것:
#   - 타입 검증: int 필드에 문자열이 오면 422 에러
#   - 규칙 검증: min_length, gt, ge 등 조건 위반 시 422 에러
#   - JSON ↔ Python 객체 자동 변환
# =============================================================

import re
from datetime import date
from pydantic import BaseModel, EmailStr, Field, field_validator


# =============================================================
# 주차장 요청 모델 (2회차)
# =============================================================

class ParkingCreateRequest(BaseModel):
    """
    주차장 등록 요청 모델 (POST /parking-lots)
    id, created_at은 DB 자동 생성이므로 포함하지 않습니다.
    """
    lot_name: str   = Field(..., min_length=1, max_length=60,  description="주차장명")
    district: str   = Field(..., min_length=1, max_length=30,  description="지구명")
    capacity: int   = Field(..., gt=0,                         description="총 주차면수 (0보다 커야 함)")
    # gt=0: greater than 0 — 0 이하 입력 시 422 자동 반환
    lat     : float = Field(..., ge=-90,  le=90,               description="위도 (-90 ~ 90)")
    # ge: greater than or equal (이상) / le: less than or equal (이하)
    lng     : float = Field(..., ge=-180, le=180,              description="경도 (-180 ~ 180)")


class ParkingUpdateRequest(BaseModel):
    """
    주차장 수정 요청 모델 (PATCH /parking-lots/{id})
    수정할 필드만 선택적으로 전송합니다.
    None인 필드는 model_dump(exclude_unset=True)로 제외 → 기존값 유지
    """
    lot_name: str   | None = None
    district: str   | None = None
    capacity: int   | None = Field(None, gt=0)
    lat     : float | None = Field(None, ge=-90,  le=90)
    lng     : float | None = Field(None, ge=-180, le=180)


# =============================================================
# 회원 요청 모델 (3회차)
# =============================================================

class UserSignUpRequest(BaseModel):
    """회원가입 요청 모델"""
    email   : EmailStr = Field(..., description="사용자 이메일 주소")
    # EmailStr: pydantic 이메일 전용 타입 — @, 도메인 등 형식 자동 검증
    password: str      = Field(..., min_length=8, description="비밀번호(평문 입력)")
    # min_length=8: 8자 미만 입력 시 422 자동 반환
    name    : str      = Field(..., min_length=1, max_length=50, description="이름")

    @field_validator("password")
    # @field_validator: password 필드에 값이 입력될 때 이 함수를 자동으로 실행
    def validate_password(cls, value):
        # cls: 클래스 자신 (인스턴스가 아님)
        # value: password 필드에 실제 입력된 값
        if not re.search(r"[A-Z]", value):
            raise ValueError("비밀번호에는 대문자가 최소 1개 포함되어야 합니다.")
        if not re.search(r"[a-z]", value):
            raise ValueError("비밀번호에는 소문자가 최소 1개 포함되어야 합니다.")
        if not re.search(r"[0-9]", value):
            raise ValueError("비밀번호에는 숫자가 최소 1개 포함되어야 합니다.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
            raise ValueError("비밀번호에는 특수문자가 최소 1개 포함되어야 합니다.")
        return value
        # 검증 실패 시 422 Unprocessable Entity 자동 반환


class UserLoginRequest(BaseModel):
    """로그인 요청 모델"""
    email   : EmailStr = Field(..., description="사용자 이메일 주소")
    password: str      = Field(..., min_length=8, description="비밀번호(평문 입력)")


# =============================================================
# 예약 요청 모델 (4회차)
# =============================================================

class ReservationCreateRequest(BaseModel):
    """
    예약 생성 요청 모델 (POST /reservations)

    user_id는 요청 본문에 포함하지 않습니다.
    → JWT 토큰에서 서버가 직접 추출합니다.
    → 클라이언트가 다른 사람의 user_id를 넣어서 예약할 수 없습니다.
    """
    lot_id       : int  = Field(..., ge=1, le=11, description="예약할 주차장 ID (1~11)")
    # ge=1, le=11: 1 이상 11 이하 — 한강공원 주차장 ID 범위
    reserved_date: date = Field(...,              description="예약 날짜 (YYYY-MM-DD)")
    # date 타입: "2025-06-14" 형태의 문자열을 date 객체로 자동 변환
    # 잘못된 날짜 형식("20250614", "abc" 등) 입력 시 422 자동 반환


class ReservationUpdateRequest(BaseModel):
    """
    예약 상태 수정 요청 모델
    status만 수정 가능 (lot_id, reserved_date는 수정 불가)
    """
    status: str | None = None
    # 허용값: "active" / "completed" / "cancelled"
    # None이면 수정하지 않음


# =============================================================
# ML 예측 요청 모델 (5회차)
# =============================================================

class PredictRequest(BaseModel):
    """ML 혼잡도 예측 요청 모델"""
    lot_id     : int  = Field(..., ge=1, le=11, description="주차장 ID (1~11)")
    target_date: date = Field(...,              description="예측할 날짜 (YYYY-MM-DD)")
