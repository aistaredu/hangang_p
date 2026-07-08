# =============================================================
# ml/train.py
# 한강공원 주차장 혼잡도 예측 ML 모델 학습
# PyCaret AutoML (5회차)
# =============================================================
# 📌 역할:
#   parking_daily + parking_info + holidays 테이블에서 학습 데이터를 구성하고
#   PyCaret으로 여러 ML 알고리즘을 자동 비교 후
#   최적 모델을 models_pkl/hangang_parking.pkl 로 저장합니다.
#
# 📌 실행 방법 (PyCharm 터미널):
#   python ml/train.py
#
# 📌 학습 피처 X (입력):
#   lot_id      : 주차장 ID (1~11)
#   capacity    : 총 주차면수
#   month       : 월 (1~12) — 계절성 반영
#   day_of_week : 요일 (1=일 ~ 7=토, MySQL DAYOFWEEK 기준)
#   is_weekend  : 주말 여부 (0/1)
#   week_of_year: 연간 주차 (1~53)
#   is_holiday  : 공휴일 여부 (0/1) — holidays 테이블 LEFT JOIN
#
# 📌 예측 타겟 Y (출력):
#   occupancy_pct: 혼잡도 % = daily_count / capacity × 100
#                  0% = 빈 주차장 / 100% = 만차
#
# 📌 실행 전 확인:
#   1) parking_daily 테이블에 데이터가 있어야 합니다.
#      → python data/collect_parking_daily.py 먼저 실행
#   2) 패키지 설치 확인
#      → pip install pycaret scikit-learn==1.5.2 pandas joblib
# =============================================================

import sys
import os

# ─────────────────────────────────────────────────────────────
# 프로젝트 루트를 Python 경로에 추가
# ml/ 폴더에서 database/, models/ 임포트를 위해 필요
# ─────────────────────────────────────────────────────────────
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd          # 데이터프레임 조작
import joblib                # 학습된 모델 파일(.pkl)로 저장/로드
from pathlib import Path     # 파일 경로 객체 (os.path보다 직관적)
from dotenv import load_dotenv
from sqlalchemy import text  # 원시 SQL 실행용

from database.db_connection import engine  # DB 엔진 (쿼리 실행)

load_dotenv()  # .env 파일 로드 → DB 접속 정보 읽기


# =============================================================
# 모델 저장 경로 상수 (save_model, verify_model에서 공통 사용)
# =============================================================
# 📌 상수로 한 곳에서 관리하는 이유:
#   save_model()과 verify_model()이 서로 다른 경로를 사용하면
#   저장은 됐는데 검증에서 파일을 못 찾는 문제가 생깁니다.
#   하나의 상수를 공유하면 이 문제를 원천 차단합니다.
MODEL_PATH = Path("models_pkl") / "hangang_parking.pkl"

# 피처 컬럼 순서 상수 (학습 시와 예측 시 반드시 동일해야 함)
# 📌 predict.py에서 X를 만들 때도 이 순서를 따라야 합니다.
FEATURE_COLUMNS = [
    "lot_id",
    "capacity",
    "month",
    "day_of_week",
    "is_weekend",
    "week_of_year",
    "is_holiday",
]


# =============================================================
# 1단계: DB에서 학습 데이터 추출
# =============================================================
def load_data() -> pd.DataFrame:
    """
    DB 테이블 3개를 JOIN해서 ML 학습에 사용할 데이터프레임을 만듭니다.

    JOIN 구조:
        parking_daily (메인)
        ├── INNER JOIN parking_info  → capacity(총면수) 가져오기
        └── LEFT JOIN holidays       → is_holiday(공휴일 여부) 확인

    LEFT JOIN을 쓰는 이유:
        공휴일이 아닌 날은 holidays 테이블에 행이 없습니다.
        INNER JOIN 하면 공휴일이 아닌 날 데이터가 모두 사라집니다.
        LEFT JOIN + COALESCE(h.holiday_date IS NOT NULL, 0) 으로
        공휴일이면 1, 아니면 0을 채웁니다.
    """
    # ── SQL 쿼리: 피처 + 타겟 한 번에 추출 ────────────────────
    # DAYOFWEEK(): 1=일, 2=월 ... 7=토  (MySQL 기준)
    # WEEKOFYEAR(): 해당 날짜가 연간 몇 번째 주인지 (1~53)
    # COALESCE(값, 기본값): 값이 NULL이면 기본값 반환
    sql = """
        SELECT
            d.lot_id,
            i.capacity,
            MONTH(d.use_date)                          AS month,
            DAYOFWEEK(d.use_date)                      AS day_of_week,
            CASE WHEN DAYOFWEEK(d.use_date) IN (1,7)
                 THEN 1 ELSE 0 END                     AS is_weekend,
            WEEKOFYEAR(d.use_date)                     AS week_of_year,
            COALESCE(h.holiday_date IS NOT NULL, 0)    AS is_holiday,
            ROUND(d.daily_count / i.capacity * 100, 2) AS occupancy_pct
        FROM parking_daily d
        INNER JOIN parking_info i ON d.lot_id   = i.id
        LEFT  JOIN holidays     h ON d.use_date = h.holiday_date
        WHERE d.daily_count > 0
          AND i.capacity    > 0
        ORDER BY d.use_date, d.lot_id
    """
    # text(): SQLAlchemy에서 원시 SQL 문자열을 실행할 때 사용
    # pd.read_sql(): SQL 결과를 바로 DataFrame으로 변환
    df = pd.read_sql(text(sql), engine)

    print(f"✅ 데이터 로드 완료: {len(df):,}행 × {len(df.columns)}열")
    print(f"   occupancy_pct 범위: {df['occupancy_pct'].min():.1f}% "
          f"~ {df['occupancy_pct'].max():.1f}%")
    print(f"   평균 혼잡도: {df['occupancy_pct'].mean():.1f}%")

    # ── 이상치 제거 ───────────────────────────────────────────
    # 📌 문제: daily_count가 capacity를 초과하는 데이터가 존재합니다.
    #   예) daily_count=20,000 / capacity=458 → 혼잡도 4354%
    #   이는 데이터 오류(연간 누적 입력 등)로 추정됩니다.
    #   100%를 초과하는 데이터는 ML 모델 학습에 방해가 됩니다.
    #
    # 📌 해결: occupancy_pct > 100 인 행을 제거합니다.
    before = len(df)
    df = df[df["occupancy_pct"] <= 100].copy()
    # .copy(): 원본 DataFrame과 분리된 새 DataFrame 생성
    # (SettingWithCopyWarning 방지)
    removed = before - len(df)

    print(f"\n   이상치 제거: {removed:,}행 제거 "
          f"({removed/before*100:.1f}%)")
    print(f"   최종 학습 데이터: {len(df):,}행")
    print(f"   정제 후 범위: {df['occupancy_pct'].min():.1f}% "
          f"~ {df['occupancy_pct'].max():.1f}%")
    print(f"   정제 후 평균: {df['occupancy_pct'].mean():.1f}%")

    return df


# =============================================================
# 2단계: PyCaret으로 AutoML 학습
# =============================================================
def train(df: pd.DataFrame):
    """
    PyCaret AutoML로 여러 회귀 모델을 자동 비교하고
    최적 모델을 파이프라인으로 묶어 반환합니다.

    📌 PyCaret 동작 방식:
        setup() → compare_models() → finalize_model()
        setup()에서 전처리 파이프라인을 구성합니다.
        compare_models()에서 10개 이상의 알고리즘을 교차검증으로 비교합니다.
        finalize_model()에서 전체 데이터로 최종 학습합니다.

    📌 MLflow 실험 추적은 8회차(train_mlflow.py)에서 다룹니다.
    """
    # PyCaret regression 모듈 임포트
    # (import 문을 함수 안에 두는 이유: pycaret은 import 시 초기화 작업이 많아
    #  모듈 최상단에 두면 다른 코드 실행 시도 느려질 수 있음)
    from pycaret.regression import (
        setup,           # 전처리 파이프라인 구성
        compare_models,  # 여러 알고리즘 자동 비교
        finalize_model,  # 전체 데이터로 최종 학습 (교차검증용 holdout 포함)
        pull,            # 마지막 실행 결과를 DataFrame으로 가져오기
    )

    print("\n" + "=" * 55)
    print("PyCaret AutoML 학습 시작")
    print("=" * 55)

    # ── setup(): 전처리 파이프라인 구성 ──────────────────────
    # data       : 학습 데이터프레임 (피처 + 타겟 모두 포함)
    # target     : 예측할 컬럼 이름 (Y) — 나머지는 자동으로 X 취급
    # session_id : 재현성을 위한 랜덤 시드 (같은 숫자 = 같은 Train/Test 분할)
    # verbose    : False → 불필요한 중간 출력 숨김
    setup(
        data       = df,
        target     = "occupancy_pct",
        session_id = 42,
        verbose    = False,
    )
    print("✅ setup() 완료 — 전처리 파이프라인 구성")

    # ── compare_models(): 알고리즘 자동 비교 ──────────────────
    # n_select = 1 : 가장 좋은 1개 모델만 반환
    # sort     = "R2": R2(결정계수) 기준으로 내림차순 정렬
    #   R2 해석: 1.0 = 완벽한 예측 / 0.0 = 평균값만 예측
    # 비교 알고리즘(자동 선택):
    #   Linear Regression, Ridge, Lasso
    #   Random Forest, Extra Trees
    #   Gradient Boosting, LightGBM, XGBoost
    #   K-Nearest Neighbors 등
    print("\n여러 알고리즘 자동 비교 중... (2~5분 소요)")
    best = compare_models(
        n_select = 1,
        sort     = "R2",   # R2 기준 최적 모델 선택
        verbose  = True,   # 비교 결과 테이블 출력
    )

    # pull(): 방금 실행한 compare_models() 결과 테이블 가져오기
    comparison_df = pull()
    print("\n[모델 비교 결과 (상위 5개)]")
    # R2, RMSE, MAE 컬럼만 보기 좋게 출력
    display_cols = [c for c in ["Model", "R2", "RMSE", "MAE"]
                    if c in comparison_df.columns]
    print(comparison_df[display_cols].head())

    # ── finalize_model(): 전체 데이터로 최종 학습 ─────────────
    # compare_models()는 교차검증을 위해 일부 데이터를 holdout으로 뺍니다.
    # finalize_model()은 holdout 포함 전체 데이터로 다시 학습합니다.
    # → 더 많은 데이터로 학습 → 배포 환경에서 더 좋은 성능
    print("\n전체 데이터로 최종 학습 중...")
    final_model = finalize_model(best)
    print(f"✅ 최종 모델: {type(final_model).__name__}")

    return final_model


# =============================================================
# 3단계: 모델 저장
# =============================================================
def save_model(model):
    """
    학습된 모델을 pkl 파일로 저장합니다.

    📌 joblib vs pickle:
        joblib이 numpy 배열(scikit-learn 모델 내부)을 더 효율적으로 직렬화합니다.
        scikit-learn 공식 문서도 joblib 사용을 권장합니다.

    📌 저장 경로: MODEL_PATH 상수 사용 (verify_model과 동일 경로 보장)
        → main.py lifespan에서 서버 시작 시 자동 로드
    """
    # 저장 폴더가 없으면 자동 생성
    MODEL_PATH.parent.mkdir(exist_ok=True)
    # MODEL_PATH.parent: "models_pkl" 폴더
    # exist_ok=True: 이미 있어도 오류 없음

    # joblib.dump(객체, 경로): 객체를 pkl 파일로 직렬화해서 저장
    joblib.dump(model, MODEL_PATH)

    # 파일 크기 확인
    size_kb = MODEL_PATH.stat().st_size / 1024
    print(f"\n✅ 모델 저장 완료: {MODEL_PATH} ({size_kb:.1f} KB)")


# =============================================================
# 4단계: 모델 검증 (저장된 파일 로드 후 예측 테스트)
# =============================================================
def verify_model():
    """
    저장된 pkl 파일을 로드해서 예측이 정상 동작하는지 확인합니다.
    이 과정이 성공해야 FastAPI predict API에서 정상 사용 가능합니다.

    📌 핵심: PyCaret 모델은 학습 시 DataFrame으로 피처를 받았으므로
       predict() 호출 시에도 반드시 DataFrame을 넘겨야 합니다.
       리스트([case])를 넘기면 컬럼명 정보가 없어서 KeyError가 발생합니다.
    """
    if not MODEL_PATH.exists():
        print("❌ 모델 파일 없음 — save_model()이 먼저 실행되어야 합니다.")
        return

    # joblib.load(경로): pkl 파일 → 파이썬 객체로 역직렬화
    model = joblib.load(MODEL_PATH)
    print(f"\n✅ 모델 로드 성공: {type(model).__name__}")

    # ── 예측 테스트 ────────────────────────────────────────────
    # 📌 predict.py의 X 구성과 완전히 동일한 형태로 테스트해야 합니다.
    #
    # 📌 model.predict() 입력 형식:
    #   ❌ model.predict([case])
    #      → 리스트: 컬럼명 없음 → PyCaret 파이프라인에서 KeyError 발생
    #
    #   ✅ model.predict(pd.DataFrame([case], columns=FEATURE_COLUMNS))
    #      → DataFrame: 컬럼명 포함 → 정상 동작
    #
    # FEATURE_COLUMNS 순서: lot_id, capacity, month, day_of_week,
    #                        is_weekend, week_of_year, is_holiday
    test_cases = [
        ([1, 458, 6, 6, 1, 25, 0], "뚝섬 6월 토요일"),
        ([2, 532, 1, 2, 0, 2,  0], "여의도 1월 월요일"),
        ([6, 610, 8, 7, 1, 32, 0], "난지 8월 일요일"),
    ]

    print("\n[예측 테스트]")
    for case, label in test_cases:
        # ✅ 수정: 리스트 → DataFrame으로 변환 (컬럼명 포함)
        X    = pd.DataFrame([case], columns=FEATURE_COLUMNS)
        pred = float(model.predict(X)[0])
        pred = max(0.0, min(100.0, pred))  # 0~100% 범위 클리핑
        print(f"  {label}: 혼잡도 {pred:.1f}%")


# =============================================================
# 실행
# =============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("한강공원 주차장 혼잡도 예측 모델 학습")
    print("=" * 55)

    # 1) DB에서 학습 데이터 로드 + 이상치 제거
    df = load_data()

    if len(df) < 100:
        # 학습 데이터가 너무 적으면 모델 성능이 의미 없음
        print(f"❌ 학습 데이터 부족: {len(df)}행")
        print("   python data/collect_parking_daily.py 를 먼저 실행하세요.")
        exit(1)

    # 2) PyCaret AutoML 학습
    model = train(df)

    # 3) 모델 저장
    save_model(model)

    # 4) 저장된 모델 검증
    verify_model()

    print("\n🎉 완료! FastAPI 서버를 재시작하면 새 모델이 자동 로드됩니다.")
    print("   python main.py")
