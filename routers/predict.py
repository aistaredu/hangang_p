# =============================================================
# routers/predict.py
# ML 혼잡도 예측 API
# =============================================================
# 📌 5회차에서 완성되는 API:
#   POST /predict → 주차장 ID + 날짜 입력 → 혼잡도 % + 잔여 면수 반환
#
# 📌 ML 모델 접근 방식:
#   모델은 main.py의 lifespan에서 서버 시작 시 한 번 로드됩니다.
#   각 요청에서 request.app.state.ml_model 로 접근합니다.
#   요청마다 모델을 파일에서 읽으면 매우 느리므로 이 방식을 사용합니다.
#
# 📌 피처 구성 (학습 시와 완전히 동일해야 함):
#   [lot_id, capacity, month, day_of_week, is_weekend, week_of_year, is_holiday]
#   순서가 다르면 예측값이 엉뚱하게 나옵니다.
# =============================================================

from datetime import date
import numpy as np              # 로그 타깃 역변환(np.expm1)에 사용
import holidays as kr_holidays  # 한국 공휴일 계산 라이브러리

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from database.db_connection import get_session
from models.models import ParkingInfo
from schema.request import PredictRequest
# PredictResponse는 더 이상 사용하지 않음(딕셔너리로 반환). 스키마를 갱신해 다시 쓸 수도 있음.

# APIRouter: 관련 API를 하나의 파일로 묶은 단위
# tags=["예측"]: Swagger UI(/docs)에서 "예측" 그룹으로 분류
router = APIRouter(tags=["예측"])


# =============================================================
# 혼잡도 예측 API
# POST /predict
# =============================================================
@router.post(
    "/predict",
    # response_model 제거: 예측 성격이 '일 이용대수 + 회전율 + 붐빔등급'으로 바뀌어
    #   기존 PredictResponse 스키마와 필드가 달라졌기 때문(딕셔너리로 직접 반환).
    #   스키마를 새로 맞추려면 schema/response.py에 PredictResponse를 아래 필드로 갱신하면 됨:
    #   lot_id, lot_name, target_date, capacity, predicted_count,
    #   turnover_pct, congestion, remaining_spaces(Optional[int])
    status_code=status.HTTP_200_OK,
)
def predict_handler(
    body   : PredictRequest,             # { lot_id: int, target_date: date }
    request: Request,                    # app.state.ml_model 접근용 — FastAPI Request 객체
    session: Session = Depends(get_session),
):
    """
    주차장 ID와 날짜를 받아서 ML 모델로 혼잡도를 예측합니다.

    처리 순서:
        1) 서버에 ML 모델이 로드되어 있는지 확인
        2) 주차장 정보(capacity 등) DB에서 조회
        3) 날짜 → 피처 벡터 자동 계산
        4) 모델.predict(X) 호출
        5) 혼잡도% + 잔여 면수 계산 후 반환
    """

    # ── 1) ML 모델 확인 ───────────────────────────────────────
    # main.py lifespan에서 app.state.ml_model 에 로드됩니다.
    # getattr(객체, 속성명, 기본값): 속성이 없을 때 기본값 반환 (AttributeError 방지)
    loaded = getattr(request.app.state, "ml_model", None)
    if loaded is None:
        # 503 Service Unavailable: 서버는 살아있지만 서비스 불가 상태
        # models_pkl/hangang_parking.pkl 파일이 없거나 로드 실패 시 발생
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML 모델이 로드되지 않았습니다. ml/train.py 를 먼저 실행하세요.",
        )

    # 📌 저장 방식에 따라 두 가지 형태가 올 수 있음:
    #   (A) 모델 객체만 저장한 경우            → loaded 자체가 추정기
    #   (B) 딕셔너리(bundle)로 저장한 경우      → { "model": 추정기, "log_target": ..., ... }
    #       (train_optuna_ensemble.ipynb가 이 방식으로 저장함)
    # isinstance로 판별해 어떤 방식이든 안전하게 동작하게 한다.
    if isinstance(loaded, dict):
        model      = loaded["model"]                    # 실제 추정기 꺼내기
        log_target = loaded.get("log_target", False)    # 로그 타깃 학습 여부
    else:
        model      = loaded
        log_target = False

    # ── 2) 주차장 정보 조회 ────────────────────────────────────
    # capacity(총 주차면수)를 피처와 잔여 면수 계산에 사용합니다.
    stmt = select(ParkingInfo).where(ParkingInfo.id == body.lot_id)
    lot  = session.scalar(stmt)  # 없으면 None
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="주차장을 찾을 수 없습니다",
        )

    # ── 3) 날짜 → 피처 자동 계산 ─────────────────────────────
    target = body.target_date  # date 객체 (예: date(2025, 8, 15))

    # ── 요일 계산: 학습 SQL의 DAYOFWEEK()와 반드시 동일해야 함 ──
    # 학습 데이터는 MySQL DAYOFWEEK() 기준: 1=일, 2=월, 3=화, ..., 7=토
    # Python isoweekday()는 1=월 ~ 7=일 이라 체계가 다르므로 변환한다.
    #   변환식: (isoweekday % 7) + 1
    #   검산) 일(7)→(7%7)+1=1, 월(1)→2, 화(2)→3, ..., 토(6)→7  ✓ DAYOFWEEK와 일치
    iso          = target.isoweekday()           # 1(월) ~ 7(일)
    day_of_week  = (iso % 7) + 1                  # 1(일) ~ 7(토)  ← DAYOFWEEK 체계
    # 주말도 학습과 동일하게: 일요일(1) · 토요일(7)  (학습 SQL: IN (1,7))
    is_weekend   = 1 if day_of_week in (1, 7) else 0
    week_of_year = target.isocalendar()[1]       # 연간 몇 번째 주 (1~53)

    # 공휴일 여부 확인
    # kr_holidays.KR(): 한국 공휴일 딕셔너리 생성 (대체공휴일 포함)
    # target in kr_holidays.KR(): 해당 날짜가 공휴일이면 True
    is_holiday = 1 if target in kr_holidays.KR() else 0

    # ── 4) 피처 벡터 구성 ────────────────────────────────────
    # 학습 시 사용한 피처 순서와 반드시 동일해야 합니다.
    # ml/train.py의 SELECT 컬럼 순서: lot_id, capacity, month, day_of_week,
    #                                  is_weekend, week_of_year, is_holiday
    X = [[
        body.lot_id,        # 주차장 ID (1~11)
        int(lot.capacity),  # 총 주차면수 (Decimal → int 변환)
        target.month,       # 월 (1~12)
        day_of_week,        # 요일 (1~7)
        is_weekend,         # 주말 여부 (0/1)
        week_of_year,       # 연간 주차 (1~53)
        is_holiday,         # 공휴일 여부 (0/1)
    ]]
    # X 형태: [[1, 458, 8, 5, 0, 33, 1]]
    # 2차원 리스트인 이유: scikit-learn은 (n_samples, n_features) 형태를 요구

    # ── 5) 예측 실행: 타깃은 '일 이용대수(daily_count)' ──────────
    # model.predict(X): 예측값 1개 반환 → [0]으로 추출
    raw_pred = float(model.predict(X)[0])

    # 로그 타깃으로 학습한 모델이면 np.expm1로 역변환(baseline은 log_target=False)
    if log_target:
        raw_pred = float(np.expm1(raw_pred))

    # 예측 이용대수: 음수 방지 + 정수 반올림
    predicted_count = max(0, int(round(raw_pred)))

    # ── 6) 회전율 · 붐빔 등급 · 잔여 자리 계산 ────────────────
    capacity = int(lot.capacity)
    # 회전율(%) = 예측 이용대수 / 총 면수 * 100  (100% 초과 = 하루 중 회전 발생)
    turnover_pct = (predicted_count / capacity * 100) if capacity > 0 else 0.0

    # 붐빔 4단계 (고정 구간: 100 / 200 / 350%)
    if turnover_pct <= 100:
        congestion = "여유"
    elif turnover_pct <= 200:
        congestion = "보통"
    elif turnover_pct <= 350:
        congestion = "붐빔"
    else:
        congestion = "매우 붐빔"

    # 잔여 자리: 회전율 100% 이하일 때만 추정 가능
    #   (100% 이하 = 하루 총 이용이 면수 이하 → 만차가 안 났다고 볼 수 있어
    #    capacity - 예측대수를 '여유 자리'로 추정)
    #   100% 초과 = 하루 중 회전이 일어나 특정 시점 잔여를 알 수 없음 → None
    if turnover_pct <= 100:
        remaining_spaces = capacity - predicted_count
    else:
        remaining_spaces = None

    # ── 7) 응답 반환 ─────────────────────────────────────────
    # 📌 이 데이터(일 누적 이용대수)로는 '정확한 순간 잔여'를 알 수 없어,
    #    회전율 100% 이하인 날만 잔여를 '추정'해서 준다(remaining_spaces=None이면 추정 불가).
    return {
        "lot_id"          : body.lot_id,
        "lot_name"        : lot.lot_name,
        "target_date"     : str(body.target_date),
        "capacity"        : capacity,
        "predicted_count" : predicted_count,          # 예측 일 이용대수
        "turnover_pct"    : round(turnover_pct, 1),   # 회전율(%)
        "congestion"      : congestion,               # 붐빔 4단계
        "remaining_spaces": remaining_spaces,         # 잔여 자리(추정) / 회전 시 None
    }
