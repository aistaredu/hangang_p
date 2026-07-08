# main.py
# 한강공원 주차장 예측 웹앱 — FastAPI 진입점
# 기존 수업의 main.py와 동일한 구조
#
# 실행: python main.py  또는  fastapi dev main.py
import os
import joblib
from pathlib import Path
from contextlib import asynccontextmanager  # 파이썬 비동기 컨텍스트 매니저
                                            # 애플리케이션 시작과 종료 시점에 실행할 코드를 정의

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

# DB 엔진과 ORM Base 클래스
from database.db_connection import engine
from database.orm import Base

# ─────────────────────────────────────────────────────────────
# ✅ 버그 수정 1: ORM 모델 임포트
#
# 반드시 이 줄이 있어야 테이블이 생성됩니다!
# Base.metadata.create_all()은 Base를 상속받은 클래스들을 찾아서 테이블을 만드는데,
# 해당 클래스들이 임포트되어 있지 않으면 Base.metadata가 아무것도 모릅니다.
# 모델을 임포트해야 Base.metadata에 테이블 정보가 등록됩니다.
#
# ❌ 임포트 없을 때: create_all() 실행 → 아무 테이블도 생성 안 됨
# ✅ 임포트 있을 때: create_all() 실행 → 5개 테이블 모두 생성됨
# ─────────────────────────────────────────────────────────────
from models.models import ParkingInfo, ParkingDaily, Holiday, User, Reservation

# 라우터 임포트 (회차별로 주석 해제)
from routers.user        import router as user_router
from routers.parking     import router as parking_router
from routers.reservation import router as reservation_router
from routers.predict     import router as predict_router
from routers.admin       import router as admin_router


# ─────────────────────────────────────────────────────────────
# lifespan — 서버 시작/종료 처리
# 기존 수업의 lifespan 패턴과 동일
#
# ✅ 버그 수정 2: lifespan 함수에 app: FastAPI 매개변수 추가
#
# 기존 수업 코드에 있던 버그:
#   @asynccontextmanager
#   async def lifespan():       ← app 매개변수 없음
#       ...
#   app = FastAPI()             ← lifespan= 미등록
#
# 이렇게 하면 lifespan이 서버 시작 시 실행되지 않아서
# create_all()이 호출되지 않고, 테이블이 생성되지 않습니다.
#
# ✅ 올바른 방법:
#   1) 함수 매개변수에 app: FastAPI 반드시 추가
#   2) FastAPI(lifespan=lifespan) 으로 반드시 등록
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):   # ← app: FastAPI 매개변수 필수!
    # ── 서버 시작 시 실행 ─────────────────────────────────
    # 테이블 생성 지시: 이미 존재하는 테이블은 건너뛰고 없는 테이블만 생성
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ DB 테이블 자동 생성 완료")
    except Exception as e:
        print(f"⚠️ DB 초기화 실패(앱은 계속 실행): {e}")
    # → MySQL에 아래 5개 테이블이 자동 생성됩니다:
    #   parking_info, parking_daily, holidays, user, reservation

    # ── ML 모델 로드 ───────────────────────────────────────
    # 기존 수업 주석의 ML 모델 로드 패턴 적용:
    # "서버를 시작할 때 머신러닝 모델이 메모리에 준비되고
    #  이후 각 API 요청에서는 이미 로드된 모델을 바로 사용할 수 있다"
    #
    # app.state: FastAPI 앱 전체에서 공유하는 저장 공간
    # → 모든 라우터에서 request.app.state.ml_model 로 접근 가능
    model_path = Path("models_pkl/hangang_parking.pkl")
    if model_path.exists():
        app.state.ml_model = joblib.load(model_path)
        print(f"✅ ML 모델 로드 완료: {model_path}")
    else:
        app.state.ml_model = None
        print(f"⚠️  ML 모델 없음 → 5회차에서 생성 예정: {model_path}")

    yield  # yield를 기준으로 시작/종료 코드를 나눈다

    # ── 서버 종료 시 실행 ─────────────────────────────────
    print("서버 종료")


# ─────────────────────────────────────────────────────────────
# FastAPI 앱 생성
#
# ✅ 버그 수정 2 (계속): lifespan=lifespan 반드시 전달
# FastAPI()에 lifespan을 등록해야 서버 시작 시 lifespan 함수가 실행됩니다.
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title      = "한강공원 주차장 예측 API",
    description= "FastAPI + SQLAlchemy ORM + PyCaret ML",
    version    = "1.0.0",
    lifespan   = lifespan,  # ← 반드시 등록! 없으면 테이블 생성 안 됨
)


# ─────────────────────────────────────────────────────────────
# 라우터 등록
# 기존 수업의 app.include_router() 패턴과 동일
# 관련 API들을 기능별 파일로 분리해서 관리
# ─────────────────────────────────────────────────────────────

# ── 2회차: 주차장 CRUD ──────────────────────────────────────
app.include_router(parking_router)

# ── 3회차: 회원가입·로그인 ─────────────────────────────────
app.include_router(user_router)

# ── 4회차: 예약 CRUD ────────────────────────────────────────
app.include_router(reservation_router)

# ── 5회차: ML 예측 ──────────────────────────────────────────
app.include_router(predict_router)

# ── 7회차: 관리자 API ───────────────────────────────────────
app.include_router(admin_router)


# ─────────────────────────────────────────────────────────────
# 미들웨어 등록
# 미들웨어: 요청이 처리되기 전과 응답이 반환되기 전에 동작하는 계층
#          모든 요청과 응답에 공통으로 적용되는 처리를 담당
# ─────────────────────────────────────────────────────────────

# CORS 미들웨어: 브라우저가 다른 출처(포트) 서버에 요청하는 것을 허용
# 예) index.html(5500)에서 FastAPI(8000)으로 fetch 요청 시 브라우저가 차단 → 이걸 풀어줌
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처 허용 (개발용, 배포 시 도메인 지정)
    allow_methods=["*"],
    allow_headers=["*"],
)

# 세션 미들웨어: 요청 처리 과정에서 세션을 생성하고 쿠키를 통해 세션을 유지
# 서버만 알고 있는 secret_key로 세션 쿠키를 서명하고 검증
# pip install itsdangerous  ← 쿠키에 저장되는 세션 데이터를 서명하는 라이브러리
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "hangang-session-secret"),
)


# ─────────────────────────────────────────────────────────────
# 정적 파일 서빙
# static/ 폴더의 HTML/CSS/JS 파일을 웹에서 접근 가능하게 제공
# 예) static/index.html → http://127.0.0.1:8000/static/index.html
# ─────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


# ─────────────────────────────────────────────────────────────
# 기본 엔드포인트
# ─────────────────────────────────────────────────────────────
@app.get("/", tags=["기본"])
def root():
    return {"message": "한강공원 주차장 예측 API", "docs": "/docs"}


@app.get("/health", tags=["기본"])
def health():
    """헬스 체크 — Railway 배포 플랫폼이 서버 상태 확인 시 사용"""
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────
# 직접 실행 시 uvicorn 서버 시작
# python main.py 로 실행할 때만 동작
# (다른 파일에서 import main 할 때는 실행되지 않음)
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
