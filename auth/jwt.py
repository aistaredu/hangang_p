# =============================================================
# auth/jwt.py
# JWT 토큰 생성 & 검증 모듈
# 기존 수업의 jwt.py와 동일한 구조
# =============================================================
# 📌 JWT(JSON Web Token)란?
#   서버가 사용자를 인식할 수 있도록 발급하는 서명된 토큰입니다.
#   세션 방식과 달리 서버가 상태를 저장하지 않아도 됩니다.
#
# 📌 JWT 구조 (점(.)으로 구분된 3부분):
#   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9   ← 헤더 (Base64 인코딩)
#   .eyJ1c2VyX2lkIjoxLCJyb2xlIjoidXNlciJ9  ← 페이로드 (Base64 인코딩)
#   .SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV    ← 서명 (SECRET_KEY로 서명)
#
#   헤더   : 알고리즘 정보 (HS256)
#   페이로드: user_id, role, exp (만료시각) 등 실제 데이터
#   서명   : 헤더+페이로드를 SECRET_KEY로 서명한 값
#            → 서버만 검증 가능, 위조 방지
#
# 📌 인증 흐름:
#   로그인 → 서버가 JWT 발급 → 클라이언트 localStorage 저장
#   → 이후 API 요청마다 Authorization: Bearer {JWT} 헤더 전송
#   → 서버가 서명 검증 + 만료시각 확인 → 통과하면 처리
#
# 📌 설치: pip install PyJWT
# =============================================================

import jwt  # PyJWT 라이브러리
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from dotenv import load_dotenv
import os

load_dotenv()  # .env 파일 로드 → SECRET_KEY 읽기

# ─────────────────────────────────────────────────────────────
# 시크릿 키 & 알고리즘 설정
#
# SECRET_KEY:
#   토큰 서명에 사용하는 비밀 키입니다.
#   이 키가 노출되면 누구나 유효한 토큰을 위조할 수 있으므로
#   절대 코드에 직접 쓰지 않고 .env에서 관리합니다.
#
# ALGORITHM = "HS256":
#   HMAC-SHA256 방식 — 대칭키 서명 알고리즘
#   SECRET_KEY 하나로 서명 생성과 검증을 모두 합니다.
#   (RS256은 비대칭키: 개인키로 서명, 공개키로 검증)
# ─────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "hangang-secret-key")
ALGORITHM  = "HS256"


def create_access_token(user_id: int, role: str, expires_minutes: int = 60) -> str:
    """
    JWT 액세스 토큰을 생성합니다. 로그인 성공 시 호출됩니다.

    Args:
        user_id        : DB의 User.id 값 — 이 토큰이 누구의 것인지 식별
        role           : "user" 또는 "admin" — API 접근 권한 제어에 사용
        expires_minutes: 토큰 유효 시간 (분 단위, 기본 60분)

    Returns:
        JWT 토큰 문자열 (예: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    """

    # ── 페이로드(Payload) 구성 ───────────────────────────────
    # 페이로드: 토큰에 담을 데이터 (누구나 Base64 디코딩으로 읽을 수 있음)
    # → 민감 정보(비밀번호 등)는 절대 포함하면 안 됩니다.
    payload = {
        "user_id": user_id,   # 사용자 식별 정보 — 어느 사용자의 토큰인지
        "role"   : role,      # 권한 — 관리자 API 접근 제어에 사용

        # exp(expiration): 토큰 만료 시각
        # datetime.now(timezone.utc): 현재 UTC 시각
        # timedelta(minutes=60): 60분을 나타내는 기간 객체
        # → 지금으로부터 60분 후가 만료 시각
        # jwt.decode()가 exp를 자동으로 검사하여 만료 시 예외 발생
        "exp"    : datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }

    # ── 토큰 생성 & 반환 ──────────────────────────────────────
    # jwt.encode():
    #   payload를 Base64 인코딩하고 SECRET_KEY로 서명해서 JWT 문자열 반환
    #   위조 방지: SECRET_KEY를 모르면 유효한 서명을 만들 수 없음
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    JWT 토큰을 검증하고 페이로드를 추출합니다.
    인증이 필요한 API에서 토큰 유효성 확인 시 호출됩니다.

    Args:
        token: Authorization 헤더에서 추출한 JWT 문자열

    Returns:
        {"user_id": int, "role": str} — 토큰에서 추출한 사용자 정보

    Raises:
        HTTPException(401): 토큰 만료 또는 서명 불일치 시
    """
    try:
        # jwt.decode():
        #   1) 서명 검증: SECRET_KEY로 서명이 유효한지 확인
        #   2) 만료 시각 검사: exp가 현재 시각보다 과거이면 만료 오류
        #   3) 위 두 가지 통과 시 페이로드(dict) 반환
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        return {
            "user_id": payload["user_id"],
            "role"   : payload.get("role", "user"),  # role이 없으면 기본값 "user"
        }

    except jwt.ExpiredSignatureError:
        # 토큰의 exp가 현재 시각보다 과거 → 만료된 토큰
        # 클라이언트는 다시 로그인해서 새 토큰을 받아야 합니다.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )

    except jwt.InvalidTokenError:
        # 서명이 맞지 않거나 형식이 잘못된 토큰
        # 토큰을 위조하거나 임의로 변경한 경우 발생합니다.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
