// =============================================================
// static/js/api.js — 공통 API 호출 유틸리티
// =============================================================
// 📌 역할:
//   모든 HTML 파일(index.html, mypage.html 등)에서
//   fetch API를 직접 작성하지 않고 이 파일의 함수를 불러서 사용합니다.
//
// 📌 사용 방법:
//   HTML 파일에서 Bootstrap JS 다음에 로드합니다.
//   <script src="/static/js/api.js"></script>
//
//   그 다음 script 블록에서 아래처럼 사용합니다.
//   const lots = await apiGet("/parking-lots?page=1&size=9");
//   const user = await apiPost("/users/login", { email, password });
//
// 📌 이 파일이 제공하는 것:
//   1) 서버 주소(BASE_URL) 한 곳에서 관리
//   2) JWT 토큰 localStorage 저장/읽기/삭제
//   3) Authorization 헤더 자동 첨부
//   4) GET / POST / PATCH / DELETE 공통 fetch 함수
//   5) Bootstrap Toast 알림 함수
// =============================================================


// ─────────────────────────────────────────────────────────────
// 서버 기본 주소 설정
//
// 개발 환경: http://127.0.0.1:8000
// 배포 환경(Railway): https://프로젝트명.up.railway.app
//
// 배포 시 이 한 줄만 바꾸면 모든 API 호출 주소가 자동으로 변경됩니다.
// ─────────────────────────────────────────────────────────────
const BASE_URL = "http://127.0.0.1:8000";


// =============================================================
// JWT 토큰 관리 함수 4개
// =============================================================
// 📌 localStorage란?
//   브라우저에 내장된 키-값 저장소입니다.
//   브라우저를 닫고 다시 열어도 데이터가 유지됩니다.
//   같은 출처(http://127.0.0.1:8000)에서만 접근 가능합니다.
//   F12 → Application → Local Storage 에서 직접 확인 가능합니다.
// =============================================================

/**
 * 로그인 성공 후 JWT 토큰을 localStorage에 저장합니다.
 * 이후 모든 API 호출의 Authorization 헤더에 자동으로 포함됩니다.
 */
function saveToken(token) {
    localStorage.setItem("access_token", token);
    // "access_token"은 키 이름 (임의로 정한 문자열)
    // token은 "eyJhbGci..." 형태의 JWT 문자열
}

/**
 * localStorage에서 JWT 토큰을 읽어옵니다.
 * 토큰이 없으면 null을 반환합니다.
 */
function getToken() {
    return localStorage.getItem("access_token");
    // 값이 없으면 null 반환
}

/**
 * 로그아웃 시 localStorage에서 JWT 토큰을 삭제합니다.
 * 삭제 후에는 isLoggedIn()이 false를 반환합니다.
 */
function removeToken() {
    localStorage.removeItem("access_token");
}

/**
 * 로그인 여부를 확인합니다.
 * localStorage에 access_token이 있으면 true, 없으면 false를 반환합니다.
 *
 * 사용 예시:
 *   if (isLoggedIn()) {
 *       // 로그인 상태 처리
 *   }
 */
function isLoggedIn() {
    return getToken() !== null;
    // getToken()이 null이면 → false (비로그인)
    // getToken()이 "eyJhbGci..." 이면 → true (로그인)
}


// =============================================================
// 공통 HTTP 헤더 생성
// =============================================================
/**
 * 모든 API 요청에 공통으로 들어가는 헤더를 만듭니다.
 * 로그인 상태이면 Authorization 헤더를 자동으로 추가합니다.
 *
 * 반환 예시 (비로그인):
 *   { "Content-Type": "application/json" }
 *
 * 반환 예시 (로그인):
 *   { "Content-Type": "application/json", "Authorization": "Bearer eyJhbGci..." }
 */
function getHeaders() {
    const headers = {
        "Content-Type": "application/json",
        // Content-Type: 요청 본문이 JSON 형식임을 서버에 알림
        // 이게 없으면 서버가 본문을 읽지 못해서 422 에러 발생
    };

    const token = getToken();
    if (token) {
        // Bearer 인증 방식:
        // HTTPBearer() 미들웨어가 "Authorization" 헤더에서
        // "Bearer " 뒤의 토큰 문자열을 자동으로 추출합니다.
        headers["Authorization"] = `Bearer ${token}`;
        // 예시: "Authorization": "Bearer eyJhbGciOiJIUzI1NiIs..."
    }

    return headers;
}


// =============================================================
// GET 요청 — 데이터 조회
// =============================================================
/**
 * HTTP GET 요청을 보내고 JSON 응답을 반환합니다.
 *
 * @param {string} path - API 경로 (예: "/parking-lots?page=1&size=9")
 * @returns {Promise<any>} - 서버 응답 JSON
 *
 * 사용 예시:
 *   const data = await apiGet("/parking-lots?page=1&size=9");
 *   console.log(data.total);  // 11
 *   console.log(data.items);  // [{id:1, lot_name:...}, ...]
 */
async function apiGet(path) {
    // async 함수: await 키워드를 사용해 비동기 작업을 동기처럼 작성
    // await: 서버 응답이 올 때까지 이 줄에서 기다림 (브라우저는 멈추지 않음)
    try {
        const response = await fetch(`${BASE_URL}${path}`, {
            // fetch(): 브라우저 내장 HTTP 요청 함수
            // `${BASE_URL}${path}`: 템플릿 리터럴 — "http://127.0.0.1:8000/parking-lots?..."
            method : "GET",
            headers: getHeaders(),  // Content-Type + Authorization 헤더
        });

        // response.ok: HTTP 상태코드가 200~299이면 true, 그 외는 false
        if (!response.ok) {
            const error = await response.json();
            // FastAPI의 HTTPException detail 메시지를 오류로 던짐
            // 예: { "detail": "주차장을 찾을 수 없습니다" }
            throw new Error(error.detail || `오류: ${response.status}`);
        }

        return await response.json();
        // response.json(): 응답 본문을 JSON → JavaScript 객체로 파싱

    } catch (error) {
        // 네트워크 오류(서버 꺼짐), HTTP 오류 모두 여기서 처리
        console.error(`GET ${path} 실패:`, error.message);
        throw error;
        // throw: 오류를 다시 던져서 호출한 곳(loadParkingLots 등)에서도 처리 가능
    }
}


// =============================================================
// POST 요청 — 데이터 생성
// =============================================================
/**
 * HTTP POST 요청을 보내고 JSON 응답을 반환합니다.
 *
 * @param {string} path - API 경로 (예: "/users/login")
 * @param {object} body - 요청 본문 (JavaScript 객체)
 * @returns {Promise<any>} - 서버 응답 JSON
 *
 * 사용 예시:
 *   const data = await apiPost("/users/login", { email: "a@b.com", password: "Test1234!" });
 *   console.log(data.access_token);  // "eyJhbGci..."
 */
async function apiPost(path, body) {
    try {
        const response = await fetch(`${BASE_URL}${path}`, {
            method : "POST",
            headers: getHeaders(),
            body   : JSON.stringify(body),
            // JSON.stringify(): JavaScript 객체 → JSON 문자열 변환
            // { email: "a@b.com" } → '{"email":"a@b.com"}'
            // 서버가 Content-Type: application/json 을 보고 이 문자열을 파싱
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `오류: ${response.status}`);
        }

        // 201 Created는 본문이 있는 경우도 있고 없는 경우도 있음
        // response.text()로 먼저 읽고 내용이 있으면 JSON 파싱
        const text = await response.text();
        return text ? JSON.parse(text) : null;

    } catch (error) {
        console.error(`POST ${path} 실패:`, error.message);
        throw error;
    }
}


// =============================================================
// PATCH 요청 — 데이터 수정
// =============================================================
/**
 * HTTP PATCH 요청을 보내고 JSON 응답을 반환합니다.
 * 수정할 필드만 포함해서 보냅니다.
 *
 * @param {string} path - API 경로 (예: "/parking-lots/1")
 * @param {object} body - 수정할 필드만 포함한 객체
 */
async function apiPatch(path, body) {
    try {
        const response = await fetch(`${BASE_URL}${path}`, {
            method : "PATCH",
            headers: getHeaders(),
            body   : JSON.stringify(body),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `오류: ${response.status}`);
        }

        return await response.json();

    } catch (error) {
        console.error(`PATCH ${path} 실패:`, error.message);
        throw error;
    }
}


// =============================================================
// DELETE 요청 — 데이터 삭제
// =============================================================
/**
 * HTTP DELETE 요청을 보냅니다.
 * 204 No Content: 삭제 성공 시 응답 본문 없음
 *
 * @param {string} path - API 경로 (예: "/reservations/1")
 * @returns {Promise<boolean>} - 삭제 성공 시 true
 */
async function apiDelete(path) {
    try {
        const response = await fetch(`${BASE_URL}${path}`, {
            method : "DELETE",
            headers: getHeaders(),
            // DELETE는 body 없음
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `오류: ${response.status}`);
        }

        return true;  // 204 No Content → 본문 없이 성공 반환

    } catch (error) {
        console.error(`DELETE ${path} 실패:`, error.message);
        throw error;
    }
}


// =============================================================
// JWT 페이로드 해독 함수 (role / user_id 읽기)
// =============================================================
/**
 * JWT 토큰의 가운데(payload) 부분을 해독해 객체로 반환합니다.
 * JWT는 "헤더.페이로드.서명" 세 부분이 점(.)으로 이어진 구조이고,
 * 가운데 페이로드에 user_id, role 등이 Base64로 담겨 있습니다.
 *
 * @returns {object|null} - 예: { user_id: 1, role: "admin" } / 토큰 없으면 null
 *
 * ⚠️ 주의: 이건 '읽기'일 뿐 서명 검증이 아닙니다.
 *   화면 표시용으로만 쓰고, 실제 권한 판단은 서버가 합니다.
 */
function getPayload() {
    const token = getToken();
    if (!token) return null;
    try {
        // JWT payload는 'Base64URL'로 인코딩되어 있다(표준 Base64와 다름):
        //   - '-'를 '+'로, '_'를 '/'로 치환
        //   - 길이가 4의 배수가 되도록 '=' 패딩 보충
        //   atob()는 표준 Base64만 처리하므로 이 변환을 먼저 해야 한다.
        //   (변환 없이 atob를 쓰면 특정 토큰에서 디코딩이 실패해 null이 되고,
        //    그 결과 isAdmin()이 false가 되어 관리자 메뉴가 안 나타난다)
        let base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
        while (base64.length % 4) base64 += "=";
        // atob 후 UTF-8 복원(한글 등 멀티바이트 안전)
        const json = decodeURIComponent(
            atob(base64).split("").map(
                c => "%" + c.charCodeAt(0).toString(16).padStart(2, "0")
            ).join("")
        );
        return JSON.parse(json);
    } catch {
        return null;
    }
}

/**
 * 현재 로그인한 사용자의 역할(role)을 반환합니다.
 * 예: "admin" 또는 "user". 비로그인이면 null.
 */
function getUserRole() {
    const payload = getPayload();
    return payload ? payload.role : null;
}

/**
 * 현재 로그인한 사용자가 관리자인지 여부를 반환합니다.
 */
function isAdmin() {
    return getUserRole() === "admin";
}

/**
 * 화면에 표시할 사용자 이름을 반환합니다.
 * 로그인 시 저장해 둔 user_name이 있으면 그것을, 없으면 "사용자".
 */
function getUserName() {
    return localStorage.getItem("user_name") || "사용자";
}


// =============================================================
// Toast 알림 함수 (Bootstrap 5 Toast 컴포넌트)
// =============================================================
/**
 * 화면 오른쪽 하단에 잠깐 나타났다 사라지는 알림을 표시합니다.
 * 3회차 로그인 성공/실패 알림에 사용합니다.
 *
 * @param {string} message - 표시할 메시지
 * @param {string} type    - "success"(초록) / "danger"(빨강) / "warning"(노랑)
 *
 * 사용 예시:
 *   showToast("로그인 성공!", "success");
 *   showToast("비밀번호가 틀렸습니다.", "danger");
 */
function showToast(message, type = "success") {
    // 이미 표시 중인 Toast가 있으면 먼저 제거 (중복 방지)
    const existing = document.getElementById("liveToast");
    if (existing) existing.remove();

    // Toast HTML을 동적으로 생성해서 body 끝에 추가
    // ✅ 버그 수정: "end:1rem" → "right:1rem" (CSS 표준 속성명)
    //   "end:"는 CSS에서 유효하지 않습니다. Bootstrap의 end-0 클래스와 혼동하지 마세요.
    const toastHtml = `
        <div id="liveToast"
             class="toast align-items-center text-bg-${type} border-0"
             role="alert"
             style="position:fixed; bottom:1rem; right:1rem; z-index:9999;">
             <!-- position:fixed: 스크롤해도 항상 같은 위치에 표시 -->
             <!-- z-index:9999: Modal(1055)보다 위에 표시 -->
            <div class="d-flex">
                <div class="toast-body fw-bold">${message}</div>
                <button type="button"
                        class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast"
                        aria-label="닫기">
                </button>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML("beforeend", toastHtml);
    // insertAdjacentHTML("beforeend", ...): body 태그 닫히기 직전에 HTML 삽입

    // Bootstrap Toast 인스턴스 생성 후 표시
    const toastEl = document.getElementById("liveToast");
    const toast   = new bootstrap.Toast(toastEl, { delay: 3000 });
    // delay: 3000ms(3초) 후 자동으로 닫힘
    toast.show();
}
