# models/models.py
# ORM 모델 정의 (데이터를 데이터베이스 테이블과 연결할 수 있는 형태)
# 기존 수업의 models.py와 동일하게 Mapped + mapped_column 방식 사용
#
# ✅ 핵심 개념:
#   ORM 모델 = 파이썬 클래스로 DB 테이블을 표현
#   이 파일의 클래스 1개 = MySQL 테이블 1개
#   클래스 속성 1개 = 테이블 컬럼 1개

from datetime import datetime, date

from sqlalchemy import (
    Integer, String, Boolean,
    ForeignKey, DateTime, Date, Numeric,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
# Mapped      : 이 속성이 ORM에 의해 관리되는 칼럼임을 나타내는 타입 힌트
# mapped_column: 파이썬 클래스의 속성을 데이터베이스 칼럼으로 연결하는 함수

from database.orm import Base  # ORM 부모 클래스 — 이걸 상속해야 SQLAlchemy가 테이블로 인식


# ═════════════════════════════════════════════════════════════
# ParkingInfo — 주차장 기본 정보
# MySQL 테이블: parking_info
# 행 수: 11개 (한강공원 주차장 11개소, 거의 변하지 않음)
# ═════════════════════════════════════════════════════════════
class ParkingInfo(Base):
    # Base 클래스를 상속받은 클래스만 SQLAlchemy가 테이블로 인식
    __tablename__ = "parking_info"  # MySQL에 생성될 테이블 이름

    # ── 컬럼 정의 ─────────────────────────────────────────
    # Mapped[int]: 이 속성의 파이썬 타입이 int임을 선언
    # mapped_column(): 실제 DB 컬럼 설정
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,   # 기본키: 각 행을 고유하게 식별
        autoincrement=True, # INSERT 시 자동으로 1씩 증가 (1, 2, 3 ...)
    )
    lot_name: Mapped[str] = mapped_column(
        String(60),         # VARCHAR(60): 최대 60자 문자열
        nullable=False,     # NOT NULL: 반드시 값이 있어야 함
    )
    district: Mapped[str] = mapped_column(
        String(30),
        nullable=False,     # 지구명 예) 뚝섬지구
    )
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,     # 총 주차면수 예) 458
    )
    lat: Mapped[float] = mapped_column(
        Numeric(10, 7),     # DECIMAL(10,7): 소수점 7자리 — 위도 정밀도 확보
        nullable=False,     # 예) 37.5302000
    )
    lng: Mapped[float] = mapped_column(
        Numeric(10, 7),
        nullable=False,     # 예) 127.0688000
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),  # INSERT 시 MySQL 서버의 NOW() 자동 실행
        nullable=False,
    )

    # ── ORM 관계 설정 (Relationship) ──────────────────────
    # SQL JOIN 없이 관련 객체에 파이썬 속성으로 접근할 수 있게 해줍니다.
    #
    # 사용 예:
    #   lot = session.get(ParkingInfo, 1)
    #   lot.daily_records  → 이 주차장의 모든 일별 데이터 리스트
    #   lot.reservations   → 이 주차장의 모든 예약 리스트
    daily_records: Mapped[list["ParkingDaily"]] = relationship(
        back_populates="lot",          # ParkingDaily.lot 과 양방향 연결
        cascade="all, delete-orphan",  # 주차장 삭제 시 일별 데이터도 함께 삭제
    )
    reservations: Mapped[list["Reservation"]] = relationship(
        back_populates="lot",          # Reservation.lot 과 양방향 연결
    )


# ═════════════════════════════════════════════════════════════
# ParkingDaily — 일별 이용 현황 (ML 학습 핵심 데이터)
# MySQL 테이블: parking_daily
# 행 수: 약 12,000행 (11개소 × 3년 × 365일)
#
# ML 활용:
#   타겟 Y = daily_count / capacity × 100 = 혼잡도(%)
#   피처 X = lot_id, capacity, month, day_of_week, is_weekend ...
# ═════════════════════════════════════════════════════════════
class ParkingDaily(Base):
    __tablename__ = "parking_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    lot_id: Mapped[int] = mapped_column(
        ForeignKey("parking_info.id"),  # 외래키: parking_info 테이블의 id 참조
        nullable=False,                 # 어느 주차장 데이터인지 반드시 지정
    )
    use_date: Mapped[date] = mapped_column(
        Date,          # DATE 타입: 날짜만 저장 (시간 없음) 예) 2024-06-14
        nullable=False,
    )
    daily_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,  # 당일 총 입차 대수 예) 1203
    )

    # 같은 날(use_date) 같은 주차장(lot_id) 데이터는 1개만 허용
    # DB 수준에서 중복 INSERT를 방지합니다
    __table_args__ = (
        UniqueConstraint("lot_id", "use_date", name="uq_lot_date"),
    )

    # ORM 관계: daily.lot → 이 데이터가 속한 주차장 객체
    lot: Mapped["ParkingInfo"] = relationship(
        back_populates="daily_records",
    )


# ═════════════════════════════════════════════════════════════
# Holiday — 공휴일
# MySQL 테이블: holidays
# 행 수: 약 75개 (2022~2024년 한국 공휴일 + 대체공휴일)
#
# ML 활용:
#   use_date가 이 테이블에 있으면 is_holiday = 1
#   같은 화요일도 공휴일이면 혼잡도가 다르기 때문에 필요
# ═════════════════════════════════════════════════════════════
class Holiday(Base):
    __tablename__ = "holidays"

    holiday_date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,  # 날짜 자체가 기본키 — 중복 공휴일 방지
    )
    holiday_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,    # 예) "설날", "New Year's Day"
    )


# ═════════════════════════════════════════════════════════════
# User — 회원
# MySQL 테이블: user  (기존 수업과 동일하게 단수형)
# ═════════════════════════════════════════════════════════════
class User(Base):
    __tablename__ = "user"  # 기존 수업 컨벤션과 동일하게 단수형

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,    # UNIQUE: 같은 이메일로 중복 가입 불가
        index=True,     # INDEX 생성: 이메일로 조회할 때 속도 향상
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,  # bcrypt/argon2로 해싱된 비밀번호 (평문 저장 절대 금지!)
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="user",  # 회원가입 기본값: 일반 사용자
                         # "user": 일반 사용자 / "admin": 관리자
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # ORM 관계: user.reservations → 이 회원의 예약 목록
    reservations: Mapped[list["Reservation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",  # 회원 삭제 시 예약도 함께 삭제
    )


# ═════════════════════════════════════════════════════════════
# Reservation — 예약
# MySQL 테이블: reservation  (기존 수업 컨벤션과 동일하게 단수형)
# ═════════════════════════════════════════════════════════════
class Reservation(Base):
    __tablename__ = "reservation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"),          # user 테이블의 id 참조
        nullable=False,
    )
    lot_id: Mapped[int] = mapped_column(
        ForeignKey("parking_info.id"),  # parking_info 테이블의 id 참조
        nullable=False,
    )
    reserved_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,  # 예약 날짜 예) 2025-06-14
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",  # "active": 예약중 / "completed": 완료 / "cancelled": 취소
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # ORM 관계 양방향 연결
    # reservation.user → 예약한 회원 객체
    # reservation.lot  → 예약된 주차장 객체
    user: Mapped["User"] = relationship(back_populates="reservations")
    lot: Mapped["ParkingInfo"] = relationship(back_populates="reservations")
