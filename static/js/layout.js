// =============================================================
// static/js/layout.js — 모든 페이지 공통 navbar / footer
// =============================================================
// 📌 역할:
//   index / predict / mypage / admin 페이지에 반복되던
//   navbar와 footer를 이 파일 한 곳에서 관리합니다.
//   navbar를 바꿀 일이 생기면 이 파일만 수정하면 모든 페이지에 반영됩니다.
//
// 📌 로드 순서 (각 HTML에서):
//   Bootstrap JS → api.js → layout.js → (페이지별 스크립트)
//   api.js의 isLoggedIn / isAdmin / getUserName / removeToken 을 사용하므로
//   반드시 api.js 다음에 로드해야 합니다.
//
// 📌 사용법 (각 HTML):
//   <body> 맨 위:   <div id="navbar-placeholder"></div>
//   </body> 앞:     <div id="footer-placeholder"></div>
//   이 파일이 위 두 자리표시자를 찾아 navbar/footer를 채워 넣습니다.
// =============================================================


// ─────────────────────────────────────────────────────────────
// 공통 메뉴 정의 — 여기만 고치면 모든 페이지 메뉴가 함께 바뀜
// ─────────────────────────────────────────────────────────────
// href : 이동할 경로 / label : 표시 글자 / admin : 관리자 전용 여부
const NAV_ITEMS = [
    { href: "/static/index.html",   label: "지도" },
    { href: "/static/predict.html", label: "예측하기" },
    { href: "/static/mypage.html",  label: "내 예약" },
    { href: "/static/admin.html",   label: "관리자", admin: true },  // 관리자만 노출
];


// ─────────────────────────────────────────────────────────────
// navbar HTML 문자열 생성
// ─────────────────────────────────────────────────────────────
function renderNavbar() {
    // 현재 페이지 경로 → 해당 메뉴에 active 표시용
    const path = window.location.pathname;

    // 관리자 여부에 따라 메뉴 목록을 필터링
    //   admin:true 항목은 isAdmin()이 true일 때만 포함
    const admin = (typeof isAdmin === "function") && isAdmin();

    const menuHtml = NAV_ITEMS
        .filter(item => !item.admin || admin)   // 관리자 전용은 관리자만
        .map(item => {
            // 현재 페이지면 active 클래스 부여
            const active = path.endsWith(item.href.split("/").pop()) ? "active" : "";
            return `<li class="nav-item">
                        <a class="nav-link ${active}" href="${item.href}">${item.label}</a>
                    </li>`;
        })
        .join("");

    return `
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/static/index.html">
                🅿 한강공원 주차 예측
            </a>
            <button class="navbar-toggler" type="button"
                    data-bs-toggle="collapse" data-bs-target="#navMenu">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navMenu">
                <ul class="navbar-nav me-auto">
                    ${menuHtml}
                </ul>
                <div class="d-flex gap-2 align-items-center" id="authButtons">
                    <span class="navbar-text d-none text-light small" id="userNameDisplay"></span>
                    <button class="btn btn-outline-light btn-sm d-none" id="logoutBtn">
                        로그아웃
                    </button>
                    <!-- 로그인 버튼: 로그인 모달을 여는 트리거 -->
                    <button class="btn btn-outline-light btn-sm"
                            id="loginBtn"
                            data-bs-toggle="modal"
                            data-bs-target="#authModal">
                        로그인
                    </button>
                </div>
            </div>
        </div>
    </nav>`;
}


// ─────────────────────────────────────────────────────────────
// footer HTML 문자열 생성
// ─────────────────────────────────────────────────────────────
function renderFooter() {
    const year = new Date().getFullYear();   // 올해 연도 자동 표시
    return `
    <footer class="bg-light border-top mt-5 py-3">
        <div class="container text-center text-muted small">
            한강공원 주차장 예측 서비스 | 데이터: 서울 열린데이터광장 | © ${year}
        </div>
    </footer>`;
}


// ─────────────────────────────────────────────────────────────
// 로그인/회원가입 모달 HTML (모든 페이지 공통)
// ─────────────────────────────────────────────────────────────
function renderAuthModal() {
    return `
    <div class="modal fade" id="authModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header border-0 pb-0">
            <h5 class="modal-title fw-bold">🅿 한강공원 주차 예측</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body pt-0">
            <ul class="nav nav-tabs nav-fill mb-3">
              <li class="nav-item">
                <button class="nav-link active fw-bold" data-bs-toggle="tab" data-bs-target="#loginPane">로그인</button>
              </li>
              <li class="nav-item">
                <button class="nav-link fw-bold" data-bs-toggle="tab" data-bs-target="#signupPane">회원가입</button>
              </li>
            </ul>
            <div class="tab-content">
              <div class="tab-pane fade show active" id="loginPane">
                <div class="mb-3">
                  <label class="form-label fw-bold">이메일</label>
                  <input type="email" class="form-control" id="loginEmail" placeholder="이메일을 입력하세요">
                </div>
                <div class="mb-3">
                  <label class="form-label fw-bold">비밀번호</label>
                  <input type="password" class="form-control" id="loginPw" placeholder="비밀번호를 입력하세요">
                </div>
                <div class="alert alert-danger d-none mb-3" id="loginError"></div>
                <button class="btn btn-primary w-100 fw-bold" id="loginSubmitBtn">로그인</button>
              </div>
              <div class="tab-pane fade" id="signupPane">
                <div class="mb-3">
                  <label class="form-label fw-bold">이름</label>
                  <input type="text" class="form-control" id="signupName" placeholder="이름을 입력하세요">
                </div>
                <div class="mb-3">
                  <label class="form-label fw-bold">이메일</label>
                  <input type="email" class="form-control" id="signupEmail" placeholder="이메일을 입력하세요">
                </div>
                <div class="mb-3">
                  <label class="form-label fw-bold">비밀번호</label>
                  <input type="password" class="form-control" id="signupPw" placeholder="대·소문자·숫자·특수문자 포함 8자 이상">
                </div>
                <div class="mb-3">
                  <label class="form-label fw-bold">비밀번호 확인</label>
                  <input type="password" class="form-control" id="signupPwConfirm">
                </div>
                <div class="alert alert-danger d-none mb-3" id="signupError"></div>
                <button class="btn btn-success w-100 fw-bold" id="signupSubmitBtn">회원가입</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>`;
}

// ─────────────────────────────────────────────────────────────
// 토스트 알림 컨테이너 HTML + showToast() (모든 페이지 공통)
// ─────────────────────────────────────────────────────────────
function renderToastContainer() {
    return `
    <div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index:1090;">
      <div id="liveToast" class="toast align-items-center border-0" role="alert">
        <div class="d-flex">
          <div class="toast-body" id="toastBody"></div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
      </div>
    </div>`;
}

// 공통 토스트 표시 함수 (기존 각 페이지의 showToast를 대체)
//   type: "success" | "danger" | "warning" | "primary" ...
function showToast(message, type = "primary") {
    const toastEl = document.getElementById("liveToast");
    const bodyEl  = document.getElementById("toastBody");
    if (!toastEl || !bodyEl) return;
    toastEl.className = `toast align-items-center text-bg-${type} border-0`;
    bodyEl.textContent = message;
    bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 3000 }).show();
}


// ─────────────────────────────────────────────────────────────
// 로그인 / 회원가입 처리 (모든 페이지 공통)
// ─────────────────────────────────────────────────────────────
async function handleLogin() {
    const email    = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPw").value;
    const errEl    = document.getElementById("loginError");

    if (!email || !password) {
        errEl.textContent = "이메일과 비밀번호를 입력해주세요.";
        errEl.classList.remove("d-none");
        return;
    }
    errEl.classList.add("d-none");

    try {
        const data = await apiPost("/users/login", { email, password });
        saveToken(data.access_token);
        localStorage.setItem("user_name", email.split("@")[0]);
        bootstrap.Modal.getInstance(document.getElementById("authModal"))?.hide();
        refreshNavbar();   // 관리자면 관리자 메뉴가 즉시 나타남
        showToast("로그인 성공! 환영합니다 😊", "success");
        // 로그인 후 추가 동작이 필요한 페이지는 window의 onAfterLogin 콜백을 등록
        if (typeof window.onAfterLogin === "function") window.onAfterLogin();
    } catch (error) {
        errEl.textContent = error.message || "로그인에 실패했습니다.";
        errEl.classList.remove("d-none");
    }
}

async function handleSignup() {
    const name      = document.getElementById("signupName").value.trim();
    const email     = document.getElementById("signupEmail").value.trim();
    const password  = document.getElementById("signupPw").value;
    const pwConfirm = document.getElementById("signupPwConfirm").value;
    const errEl     = document.getElementById("signupError");

    if (!name || !email || !password) {
        errEl.textContent = "모든 항목을 입력해주세요.";
        errEl.classList.remove("d-none");
        return;
    }
    if (password !== pwConfirm) {
        errEl.textContent = "비밀번호가 일치하지 않습니다.";
        errEl.classList.remove("d-none");
        return;
    }
    errEl.classList.add("d-none");

    try {
        await apiPost("/users/signup", { email, password, name });
        bootstrap.Modal.getInstance(document.getElementById("authModal"))?.hide();
        showToast("회원가입 완료! 로그인해주세요 ✅", "success");
        document.getElementById("loginEmail").value = email;
    } catch (error) {
        errEl.textContent = error.message || "회원가입에 실패했습니다.";
        errEl.classList.remove("d-none");
    }
}

// 로그인 모달을 여는 헬퍼(비로그인 상태에서 예약 시도 등에 사용)
function openAuthModal() {
    const el = document.getElementById("authModal");
    if (el) bootstrap.Modal.getOrCreateInstance(el).show();
}


// ─────────────────────────────────────────────────────────────
// navbar 로그인 상태 반영 (기존 각 페이지의 updateNavbar 통합)
// ─────────────────────────────────────────────────────────────
function updateNavbar() {
    const loginBtn  = document.getElementById("loginBtn");
    const logoutBtn = document.getElementById("logoutBtn");
    const nameDisp  = document.getElementById("userNameDisplay");
    // navbar가 아직 안 그려졌으면 중단(방어 코드)
    if (!loginBtn || !logoutBtn || !nameDisp) return;

    if (isLoggedIn()) {
        // 로그인 상태: 로그인 버튼 숨기고, 로그아웃 버튼 + 이름 표시
        loginBtn.classList.add("d-none");
        logoutBtn.classList.remove("d-none");
        nameDisp.classList.remove("d-none");
        nameDisp.textContent = `👤 ${getUserName()}님`;
    } else {
        // 비로그인 상태: 로그인 버튼만 표시
        loginBtn.classList.remove("d-none");
        logoutBtn.classList.add("d-none");
        nameDisp.classList.add("d-none");
    }
}


// ─────────────────────────────────────────────────────────────
// refreshNavbar() — navbar를 '메뉴까지' 통째로 다시 그린다
// ─────────────────────────────────────────────────────────────
// 📌 로그인/로그아웃 '직후'에 호출한다.
//   updateNavbar()는 로그인/로그아웃 '버튼'만 바꿀 뿐, 메뉴 목록은 안 바꾼다.
//   관리자 메뉴는 renderNavbar() 안의 isAdmin() 필터로 결정되므로,
//   로그인 후 관리자 메뉴를 즉시 보이게 하려면 renderNavbar()를 다시 실행해야 한다.
//   (이게 없으면 로그인 후 다른 페이지로 이동해야 관리자 메뉴가 나타난다)
function refreshNavbar() {
    const navSlot = document.getElementById("navbar-placeholder");
    if (!navSlot) return;

    navSlot.innerHTML = renderNavbar();   // 메뉴(관리자 링크 포함)를 새 로그인 상태로 다시 그림
    updateNavbar();                       // 로그인/로그아웃 버튼 상태 반영

    // ⚠️ innerHTML을 새로 넣으면 기존 이벤트 연결이 사라지므로 다시 연결한다
    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) logoutBtn.addEventListener("click", handleLogout);
}


// ─────────────────────────────────────────────────────────────
// 로그아웃 처리 (모든 페이지 공통)
// ─────────────────────────────────────────────────────────────
function handleLogout() {
    removeToken();                       // JWT 삭제 (api.js)
    localStorage.removeItem("user_name");
    // 로그아웃 후 메인 페이지로 이동 (관리자 페이지에 남지 않도록)
    window.location.href = "/static/index.html";
}


// ─────────────────────────────────────────────────────────────
// 페이지 로드 시: navbar/footer 삽입 → 상태 반영 → 이벤트 연결
// ─────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // 1) footer 자리표시자 채우기
    const footSlot = document.getElementById("footer-placeholder");
    if (footSlot) footSlot.innerHTML = renderFooter();

    // 2) 공통 로그인 모달 + 토스트를 body 끝에 자동 삽입
    //    (각 HTML에 모달/토스트를 중복해서 넣지 않아도 됨)
    if (!document.getElementById("authModal")) {
        document.body.insertAdjacentHTML("beforeend", renderAuthModal());
    }
    if (!document.getElementById("liveToast")) {
        document.body.insertAdjacentHTML("beforeend", renderToastContainer());
    }

    // 3) navbar 그리기 + 로그인 상태 반영 + 로그아웃 버튼 연결
    refreshNavbar();

    // 4) 로그인/회원가입 버튼 이벤트 연결
    document.getElementById("loginSubmitBtn")?.addEventListener("click", handleLogin);
    document.getElementById("signupSubmitBtn")?.addEventListener("click", handleSignup);
    document.getElementById("loginPw")?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleLogin();
    });
});
