# =============================================================
# auth/password.py
# 비밀번호 해싱 & 검증 모듈
# 기존 수업의 password.py와 동일한 구조 (pwdlib 사용)
# =============================================================
# 📌 왜 비밀번호를 해싱하는가?
#   DB가 해킹당하면 평문 비밀번호는 즉시 유출됩니다.
#   해싱하면 해시값만 저장되므로, 원본 비밀번호를 알아낼 수 없습니다.
#
#   해싱(Hashing) vs 암호화(Encryption) 차이:
#     암호화: 키로 암호화 → 키로 복호화 (양방향)
#     해싱  : 입력 → 해시값 (단방향, 복호화 불가)
#
# 📌 argon2 알고리즘 선택 이유:
#   - 2015년 Password Hashing Competition 1위 수상
#   - bcrypt보다 메모리 사용량이 많아 GPU 브루트포스 공격에 강함
#   - FastAPI 공식 문서도 pwdlib + argon2 권장 (2024년부터)
#
# 📌 설치:
#   pip install "pwdlib[argon2]"
#   (대괄호 안이 알고리즘 드라이버 — argon2 설치 포함)
# =============================================================

from pwdlib import PasswordHash
# PasswordHash: 비밀번호 해싱과 검증 로직을 하나의 객체로 관리
# 알고리즘 선택, 솔트 생성, 해싱, 검증을 내부에서 자동 처리


# ─────────────────────────────────────────────────────────────
# 해셔 인스턴스 생성
#
# PasswordHash.recommended():
#   현재 권장하는 알고리즘(argon2)으로 설정된 해셔 객체를 생성합니다.
#   라이브러리가 업데이트되면 더 안전한 알고리즘으로 자동 전환됩니다.
#
# 모듈 수준에서 한 번만 생성합니다.
# 매 요청마다 생성하면 불필요한 메모리 낭비가 발생합니다.
# ─────────────────────────────────────────────────────────────
password_hasher = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """
    평문 비밀번호를 argon2 해시값으로 변환합니다.
    회원가입 시 사용합니다.

    Args:
        plain_password: 사용자가 입력한 원본 비밀번호 (예: "Test1234!")

    Returns:
        해시 문자열 (예: "$argon2id$v=19$m=65536,t=3,p=4$...")
        매번 실행해도 다른 해시값이 나옵니다. (솔트가 무작위로 추가되기 때문)

    동작 원리:
        1) 무작위 솔트(salt) 생성
        2) 솔트 + 비밀번호를 argon2 알고리즘으로 해싱
        3) 알고리즘 정보 + 솔트 + 해시값을 하나의 문자열로 조합해서 반환

    솔트(Salt):
        같은 비밀번호라도 매번 다른 해시값이 나오게 하는 무작위 값
        레인보우 테이블 공격(미리 만들어둔 해시 테이블)을 방어합니다.
    """
    return password_hasher.hash(plain_password)
    # 해시값만 DB에 저장합니다.
    # 평문 비밀번호는 이 함수가 끝나면 메모리에서 사라집니다.


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    입력한 비밀번호가 DB에 저장된 해시값과 일치하는지 검증합니다.
    로그인 시 사용합니다.

    Args:
        plain_password  : 사용자가 로그인 시 입력한 비밀번호 (예: "Test1234!")
        hashed_password : DB에 저장된 해시 문자열

    Returns:
        True : 비밀번호 일치 → 로그인 성공
        False: 비밀번호 불일치 → 로그인 실패

    동작 원리:
        1) hashed_password에서 솔트와 알고리즘 정보를 추출
        2) 같은 솔트로 plain_password를 다시 해싱
        3) 새로 만든 해시값과 hashed_password를 비교
        (역방향 복호화가 아닌, 같은 방향으로 다시 해싱해서 비교)
    """
    return password_hasher.verify(plain_password, hashed_password)
