# database/db_connection.py
# 데이터베이스 연결 설정
# 기존 수업의 db_connection.py와 동일한 구조

from sqlalchemy import create_engine       # 엔진(engine): 데이터베이스와의 실제 연결을 관리하는 객체
from sqlalchemy.orm import sessionmaker    # 세션(session): ORM이 데이터베이스와 상호작용할 때 사용하는 작업 단위
from dotenv import load_dotenv
import os

load_dotenv()  # .env 파일 로드 → os.getenv()로 값을 읽을 수 있게 된다

# ─────────────────────────────────────────────────────────────
# 데이터베이스 연결 URL 구성
# 형식: mysql+pymysql://사용자명:비밀번호@호스트:포트/데이터베이스명
# ─────────────────────────────────────────────────────────────
DATABASE_URL = (
    f"mysql+pymysql://"
    f"{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '3306')}"
    f"/{os.getenv('DB_NAME')}?charset=utf8mb4"
)

# ─────────────────────────────────────────────────────────────
# 엔진 생성
# 데이터베이스와 통신할 수 있는 엔진
# echo=True: 실행되는 SQL 쿼리가 터미널 로그로 출력됨
# ─────────────────────────────────────────────────────────────
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# ─────────────────────────────────────────────────────────────
# 세션 팩토리 생성
# 세션을 찍어내는 "틀(Factory)" — SessionFactory()를 호출할 때마다 새 세션 생성
#
# ✅ 수정 포인트: expire_on_commit=True (기본값 유지)
#   False로 설정하면 commit() 후에도 객체 속성이 메모리에 남아 있어서
#   session.refresh()를 호출해도 DB 최신값이 반영되지 않는 문제가 생깁니다.
#   회원가입 응답에서 created_at이 None으로 나오는 원인이 됩니다.
#   True(기본값)로 두면 commit() 후 객체를 다시 읽을 때 DB에서 최신값을 가져옵니다.
# ─────────────────────────────────────────────────────────────
SessionFactory = sessionmaker(
    autocommit=False,  # 개발자가 commit()을 호출해야 변경 사항이 확정됨
    autoflush=False,   # 개발자가 flush()를 호출해야 쿼리가 실행됨
    bind=engine,       # 이 세션이 사용할 데이터베이스 엔진 지정
    # expire_on_commit=True  ← 기본값 사용 (명시하지 않아도 됨)
    # commit() 이후 접근 시 DB에서 최신값을 자동으로 다시 읽어옴
)

# ─────────────────────────────────────────────────────────────
# 세션 생성 함수
# 요청이 들어올 때마다 새로운 데이터베이스 세션을 생성하고
# API 처리가 끝나면 자동으로 세션을 정리 (with 문이 처리)
#
# 라우터에서 Depends(get_session)으로 주입받아 사용:
#   def get_todos(session = Depends(get_session)):
#       ...
# ─────────────────────────────────────────────────────────────
def get_session():
    with SessionFactory() as session:
        yield session
