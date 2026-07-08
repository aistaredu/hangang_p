# =============================================================
# routers/user.py
# 회원 관련 API — 회원가입, 로그인
# 기존 수업의 user.py와 동일한 구조
# =============================================================
# 📌 3회차에서 완성되는 API:
#   POST /users/signup  → 회원가입
#   POST /users/login   → 로그인 + JWT 토큰 발급
#
# 📌 인증 흐름:
#   회원가입 → 비밀번호 해싱 → DB 저장
#   로그인   → 비밀번호 검증 → JWT 토큰 발급 → 클라이언트가 localStorage 저장
#   이후 API → Authorization: Bearer {토큰} 헤더 첨부 → 서버 검증
# =============================================================

from fastapi import APIRouter, status, HTTPException, Depends, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from schema.request  import UserSignUpRequest, UserLoginRequest
from schema.response import UserSignUpResponse
from database.db_connection import get_session
from models.models import User
from auth.password import hash_password, verify_password
from auth.jwt      import create_access_token

# APIRouter: main.py의 app 대신 라우터에 API를 등록
# tags=["User"]: Swagger UI(/docs)에서 "User" 그룹으로 묶임
router = APIRouter(tags=["User"])


# =============================================================
# 백그라운드 태스크 — 회원가입 환영 이메일
# 기존 수업의 BackgroundTasks 패턴과 동일
# =============================================================
def send_welcome_email(email: str):
    """
    회원가입 성공 후 환영 이메일을 발송하는 함수입니다.
    BackgroundTasks로 등록되어 응답 반환 후 백그라운드에서 실행됩니다.

    BackgroundTasks의 특징:
        - API 응답을 먼저 클라이언트에 보내고, 그 뒤에 이 함수가 실행됩니다.
        - 이메일 발송 같이 시간이 걸리는 작업을 응답 지연 없이 처리할 수 있습니다.
        - 실제 이메일 발송은 smtplib 등을 사용하지만, 여기서는 print로 대체합니다.
    """
    import time
    time.sleep(5)  # 이메일 발송 시간 시뮬레이션 (실제는 SMTP 요청)
    print(f"Send Welcome Email to {email}...")


# =============================================================
# 회원가입
# POST /users/signup
# =============================================================
@router.post(
    "/users/signup",
    status_code=status.HTTP_201_CREATED,   # 리소스 생성 성공: 201
    response_model=UserSignUpResponse,     # 응답에서 hashed_password 제외
)
def signup_user_handler(
    body            : UserSignUpRequest,   # Pydantic이 이메일 형식·비밀번호 규칙 자동 검증
    background_tasks: BackgroundTasks,     # 응답 후 백그라운드 작업 실행을 위한 주입
    session         : Session = Depends(get_session),
):
    """
    회원가입 처리 순서:
        1) 이메일 중복 검사
        2) 비밀번호 해시 생성
        3) User 객체 생성 & DB 저장
        4) 환영 이메일 백그라운드 등록
        5) 응답 반환 (hashed_password 제외)
    """

    # ── 1) 이메일 중복 검사 ───────────────────────────────────
    # select(User).where(User.email == body.email):
    #   SQL: SELECT * FROM user WHERE email = '{body.email}' LIMIT 1;
    # session.scalar(): 단일 결과 반환 — 있으면 User 객체, 없으면 None
    stmt          = select(User).where(User.email == body.email)
    existing_user = session.scalar(stmt)

    if existing_user:
        # 409 Conflict: 이미 존재하는 리소스와 충돌
        # 401(인증 실패)이 아닌 409를 쓰는 이유:
        #   "이메일이 이미 존재한다"는 것은 인증 문제가 아닌 데이터 충돌 문제이기 때문
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용중인 이메일입니다",
        )

    # ── 2) 비밀번호 해시 생성 ─────────────────────────────────
    # hash_password(): auth/password.py에서 가져온 함수
    # 평문 비밀번호 → argon2 해시값으로 변환
    # 예) "Test1234!" → "$argon2id$v=19$m=65536,..."
    # 해시값만 DB에 저장되므로, 비밀번호 원본은 어디에도 남지 않습니다.
    hashed_password = hash_password(body.password)

    # ── 3) User 객체 생성 & DB 저장 ──────────────────────────
    user = User(
        email          =str(body.email),    # EmailStr → str 변환
        hashed_password=hashed_password,    # 해시값 저장 (평문 저장 금지!)
        name           =body.name,
        role           ="user",             # 회원가입 기본 권한: 일반 사용자
        # id, created_at은 DB가 자동 생성
    )
    session.add(user)      # 세션에 등록 (아직 SQL INSERT 실행 전)
    session.commit()       # SQL INSERT 실행 → DB에 실제 저장
    session.refresh(user)  # DB가 생성한 id, created_at 값을 user 객체에 반영

    # ── 4) 백그라운드 태스크 등록 ────────────────────────────
    # add_task(함수, 인자): 응답 반환 후 백그라운드에서 실행될 함수 등록
    # 클라이언트는 이메일 발송을 기다리지 않고 즉시 응답을 받습니다.
    background_tasks.add_task(send_welcome_email, user.email)

    # ── 5) 응답 반환 ─────────────────────────────────────────
    # response_model=UserSignUpResponse 에 의해
    # hashed_password, role 등 민감 정보는 자동으로 제외됩니다.
    # UserSignUpResponse에 정의된 필드(id, email, name, created_at)만 반환됩니다.
    return user


# =============================================================
# 로그인 (JWT 방식 — JSON Web Token)
# POST /users/login
# =============================================================
@router.post(
    "/users/login",
    status_code=status.HTTP_200_OK,
)
def login_user_handler(
    body   : UserLoginRequest,
    session: Session = Depends(get_session),
):
    """
    로그인 처리 순서:
        1) 이메일로 사용자 조회
        2) 비밀번호 검증
        3) JWT 액세스 토큰 생성 & 반환

    반환값: {"access_token": "eyJhbGci..."}
    클라이언트는 이 토큰을 localStorage에 저장해서 이후 API 호출 시 사용합니다.
    """

    # ── 1) 이메일로 사용자 조회 ───────────────────────────────
    stmt = select(User).where(User.email == body.email)
    user = session.scalar(stmt)

    # 이메일이 존재하지 않는 경우
    # ⚠️ "이메일이 틀렸습니다" 대신 "이메일 또는 비밀번호가 올바르지 않습니다"를 쓰는 이유:
    #   어떤 정보가 틀렸는지 알려주면 공격자가 이메일 존재 여부를 알 수 있기 때문
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다",
        )

    # ── 2) 비밀번호 검증 ──────────────────────────────────────
    # verify_password(): auth/password.py에서 가져온 함수
    # 입력한 평문 비밀번호를 같은 방식으로 해싱해서 DB 해시값과 비교합니다.
    # 해싱은 단방향(복호화 불가)이므로 DB 해시값을 역으로 풀 수 없습니다.
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다",
        )

    # ── 3) JWT 토큰 생성 & 반환 ───────────────────────────────
    # create_access_token(): auth/jwt.py에서 가져온 함수
    # payload에 user_id와 role을 담아서 토큰을 생성합니다.
    # expires_minutes=60: 60분 후 만료 (만료 후 재로그인 필요)
    access_token = create_access_token(
        user_id        =user.id,
        role           =user.role,   # "user" or "admin" — 관리자 API 접근 제어에 사용
        expires_minutes=60,
    )

    # dict를 반환하면 FastAPI가 자동으로 JSON으로 변환합니다.
    # 클라이언트(JS)에서 data.access_token 으로 접근합니다.
    return {"access_token": access_token}

# ─────────────────────────────────────────────────────────────
# JWT 로그아웃에 대해:
#   JWT는 서버가 상태를 저장하지 않는 stateless 방식입니다.
#   발급된 토큰은 만료 전까지 항상 유효하므로, 서버에서 즉시 무효화하기 어렵습니다.
#   일반적인 해결책:
#     1) 클라이언트에서 localStorage의 토큰 삭제 (가장 단순)
#     2) 토큰 만료 시간을 짧게 설정 (10~15분)
#     3) Redis에 블랙리스트 저장 (가장 안전, 복잡도 높음)
#   이 프로젝트에서는 1번 방법을 사용합니다.
# ─────────────────────────────────────────────────────────────
