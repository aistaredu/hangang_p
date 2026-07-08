# database/orm.py
# SQLAlchemy ORM 베이스 클래스 정의
# 기존 수업의 orm.py와 동일한 구조

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# 이 클래스를 상속받는 모든 클래스는 데이터베이스 테이블로 취급한다
