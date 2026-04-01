import streamlit as st
import json
import os

# =========================================================
# 0. 파일 경로 / 기본값
# =========================================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"

DEFAULT_SETTINGS = {
    "provider": "gemini",
    "api_key": "",
    "model": "gemini-1.5-flash-latest"
}

DEFAULT_INPUTS = {
    "in_company_name": "",
    "in_biz_type": "개인",
    "in_raw_biz_no": "",
    "in_raw_corp_no": "",
    "in_start_date": "",
    "in_biz_tel": "",
    "in_email_addr": "",
    "in_industry": "제조업",
    "in_lease_status": "자가",
    "in_biz_addr": "",
    "in_lease_deposit": None,
    "in_lease_rent": None,
    "in_has_extra_biz": "없음",
    "in_extra_biz_info": "",

    "in_rep_name": "",
    "in_rep_dob": "",
    "in_rep_phone": "",
    "in_rep_carrier": "선택",
    "in_home_addr": "",
    "in_home_status": "자가",
    "in_real_estate": [],
    "in_edu_level": "선택",
    "in_rep_major": "",
    "in_rep_career_1": "",
    "in_rep_career_2": "",

    "in_fin_delinquency": "없음",
    "in_tax_delinquency": "없음",
    "in_kcb_score": None,
    "in_nice_score": None,

    "in_export_revenue": "없음",
    "in_planned_export": "없음",
    "in_sales_cur": None,
    "in_sales_25": None,
    "in_sales_24": None,
    "in_sales_23": None,
    "in_exp_cur": None,
    "in_exp_25": None,
    "in_exp_24": None,
    "in_exp_23": None,

    "in_debt_kosme": None,
    "in_debt_semas": None,
    "in_debt_kodit": None,
    "in_debt_kibo": None,
    "in_debt_foundation": None,
    "in_debt_corp_coll": None,
    "in_debt_rep_cred": None,
    "in_debt_rep_coll": None,

    "in_cert_0": False,
    "in_cert_1": False,
    "in_cert_2": False,
    "in_cert_3": False,
    "in_cert_4": False,
    "in_cert_5": False,
    "in_cert_6": False,
    "in_cert_7": False,

    "in_has_patent": "없음",
    "in_pat_cnt": None,
    "in_pat_desc": "",
    "in_has_gov": "없음",
    "in_gov_cnt": None,
    "in_gov_desc": "",

    "in_item_desc": "",
    "in_sales_route": "",
    "in_item_diff": "",
    "in_market_status": "",
    "in_process_desc": "",
    "in_target_cust": "",
    "in_revenue_model": "",
    "in_future_plan": "",

    "in_req_funds": None,
    "in_fund_plan": ""
}

CERT_LIST = [
    "중소기업확인서(소상공인확인서)",
    "창업확인서",
    "여성기업확인서",
    "이노비즈",
    "벤처인증",
    "뿌리기업확인서",
    "ISO인증",
    "HACCP인증"
]

MODEL_OPTIONS = {
    "gemini": [
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro-latest"
    ],
    "openai": [
        "gpt-4.1-mini",
        "gpt-4.1",
        "gpt-4o-mini"
    ]
}

REPORT_MODES = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]
REPORT_LABELS = [
    "📊 기업진단 리포트",
    "💡 정책자금 매칭 + 보증가능성 리포트",
    "📝 기관별 융자/사업계획서",
    "📑 AI 사업계획서"
]

# =========================================================
# 1. 파일 로드 / 저장
# =========================================================
def load_settings():
    data = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    data = raw
        except Exception:
            data = {}
    merged = DEFAULT_SETTINGS.copy()
    merged.update(data)
    return merged


def save_settings(provider, api_key, model):
    payload = {
        "provider": provider,
        "api_key": api_key,
        "model": model
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)


def load_companies():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    return raw
        except Exception:
            return {}
    return {}


def save_companies(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================
# 2. 세션 초기화
# =========================================================
def init_session():
    if "settings" not in st.session_state:
        st.session_state["settings"] = load_settings()
    else:
        merged = DEFAULT_SETTINGS.copy()
        merged.update(st.session_state["settings"])
        st.session_state["settings"] = merged

    if "company_list" not in st.session_state:
        st.session_state["company_list"] = load_companies()

    if "view_mode" not in st.session_state:
        st.session_state["view_mode"] = "INPUT"

    if "active_company" not in st.session_state:
        st.session_state["active_company"] = ""

    if "selected_company_name" not in st.session_state:
        st.session_state["selected_company_name"] = ""

    for k, v in DEFAULT_INPUTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get_current_company_data():
    return {k: st.session_state.get(k, DEFAULT_INPUTS[k]) for k in DEFAULT_INPUTS.keys()}


def apply_company_data(company_name, loaded_data):
    merged = DEFAULT_INPUTS.copy()
    if isinstance(loaded_data, dict):
        merged.update(loaded_data)

    if not merged.get("in_company_name"):
        merged["in_company_name"] = company_name

    for k, v in merged.items():
        st.session_state[k] = v

    st.session_state["active_company"] = company_name
    st.session_state["selected_company_name"] = company_name


def reset_input_form():
    for k, v in DEFAULT_INPUTS.items():
        st.session_state[k] = v

# =========================================================
# 3. 공통 함수
# =========================================================
def safe_int(value):
    try:
        if value is None or value == "":
            return 0
        return int(float(str(value).replace(",", "").strip()))
    except Exception:
        return 0


def get_kcb_grade(score):
    s = safe_int(score)
    if s >= 942:
        return "1등급", "#43A047"
    elif s >= 832:
        return "3등급", "#66BB6A"
    elif s >= 630:
        return "6등급", "#EF6C00"
    else:
        return f"{s}점(등급외)", "#E53935"


def get_nice_grade(score):
    s = safe_int(score)
    if s >= 900:
        return "1등급", "#1E88E5"
    elif s >= 840:
        return "3등급", "#42A5F5"
    elif s >= 665:
        return "6등급", "#EF6C00"
    else:
        return f"{s}점(등급외)", "#E53935"


def selected_certs(data):
    items = []
    for i, name in enumerate(CERT_LIST):
        if data.get(f"in_cert_{i}", False):
            items.append(name)
    return items


def calc_total_debt(data):
    debt_keys = [
        "in_debt_kosme", "in_debt_semas", "in_debt_kodit", "in_debt_kibo",
        "in_debt_foundation", "in_debt_corp_coll", "in_debt_rep_cred", "in_debt_rep_coll"
    ]
    return sum(safe_int(data.get(k)) for k in debt_keys)


def calc_recent_sales(data):
    for key in ["in_sales_cur", "in_sales_25", "in_sales_24", "in_sales_23"]:
        v = safe_int(data.get(key))
        if v > 0:
            return v
    return 0


def calc_simple_policy_score(data):
    score = 0

    kcb = safe_int(data.get("in_kcb_score"))
    nice = safe_int(data.get("in_nice_score"))
    avg = 0
    if kcb > 0 and nice > 0:
        avg = (kcb + nice) / 2
    else:
        avg = max(kcb, nice)

    if data.get("in_fin_delinquency") == "있음" or data.get("in_tax_delinquency") == "있음":
        score += 0
    else:
        if avg >= 900:
            score += 20
        elif avg >= 800:
            score += 15
        elif avg >= 700:
            score += 10
        elif avg > 0:
            score += 5
        else:
            score += 5

    sales = calc_recent_sales(data)
    if sales >= 100000:
        score += 15
    elif sales >= 50000:
        score += 12
    elif sales >= 10000:
        score += 9
    elif sales > 0:
        score += 5
    else:
        score += 2

    debt = calc_total_debt(data)
    ratio = 999 if sales == 0 and debt > 0 else 0 if sales == 0 else (debt / sales) * 100

    if ratio <= 30:
        score += 15
    elif ratio <= 70:
        score += 12
    elif ratio <= 120:
        score += 8
    else:
        score += 4

    cert_count = len(selected_certs(data))
    if cert_count >= 4:
        score += 10
    elif cert_count >= 2:
        score += 7
    elif cert_count == 1:
        score += 4
    else:
        score += 1

    pat_cnt = safe_int(data.get("in_pat_cnt"))
    if data.get("in_has_patent") == "있음":
        if pat_cnt >= 3:
            score += 10
        elif pat_cnt >= 1:
            score += 7
        else:
            score += 5
    else:
        score += 1

    if data.get("in_export_revenue") == "있음":
        score += 15
    elif data.get("in_planned_export") == "있음":
        score += 7
    else:
        score += 2

    if score >= 75:
        grade = "가능"
    elif score >= 58:
        grade = "유망"
    elif score >= 40:
        grade = "보완필요"
    else:
        grade = "어려움"

    return score, grade


def calc_simple_guarantee(data):
    score = 50

    kcb = safe_int(data.get("in_kcb_score"))
    nice = safe_int(data.get("in_nice_score"))
    avg = max(kcb, nice) if (kcb == 0 or nice == 0) else (kcb + nice) / 2

    if avg >= 900:
        score += 18
    elif avg >= 850:
        score += 14
    elif avg >= 780:
        score += 10
    elif avg >= 700:
        score += 6
    elif avg >= 630:
        score += 2
    else:
        score -= 8

    if data.get("in_fin_delinquency") == "있음":
        score -= 25
    if data.get("in_tax_delinquency") == "있음":
        score -= 20

    sales = calc_recent_sales(data)
    if sales >= 100000:
        score += 10
    elif sales >= 30000:
        score += 7
    elif sales >= 10000:
        score += 4
    elif sales > 0:
        score += 2
    else:
        score -= 5

    score = max(5, min(95, int(round(score))))

    if score >= 80:
        label = "승인 가능성 높음"
    elif score >= 65:
        label = "조건부 유망"
    elif score >= 50:
        label = "보완 후 검토"
    else:
        label = "승인 가능성 낮음"

    return score, label

# =========================================================
# 4. 페이지 / 스타일
# =========================================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    [data-testid="stWidgetLabel"] p { font-weight: 400 !important; font-size: 14px !important; color: #31333F !important; margin-bottom: 2px !important; }
    h2 { font-weight: 700 !important; margin-top: 25px !important; }
    input::placeholder, textarea::placeholder { font-size: 0.85em !important; color: #888 !important; }

    [data-testid="stCheckbox"] label p { font-size: 18px !important; font-weight: 500 !important; color: #333 !important; }

    .summary-box-compact {
        background-color: #E8F5E9;
        padding: 12px;
        border-radius: 10px;
        height: 145px;
        border: 1px solid #ddd;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin-top: 25px;
    }
    .score-result-box {
        background-color: #F1F8E9;
        padding: 12px;
        border-radius: 10px;
        height: 145px;
        border: 1px solid #C8E6C9;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin-top: 25px;
    }
    .result-title {
        font-size: 18px !important;
        font-weight: 700 !important;
        color: #2E7D32;
        margin-bottom: 5px !important;
    }
    .blue-bold-label-16 {
        color: #1E88E5 !important;
        font-size: 16px !important;
        font-weight: 700;
    }
    .placeholder-box {
        background: #fff7ed;
        border: 1px solid #fed7aa;
        color: #9a3412;
        padding: 18px;
        border-radius: 12px;
        margin-top: 12px;
    }
    .active-company-box {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e3a8a;
        padding: 14px 16px;
        border-radius: 12px;
        margin-bottom: 16px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

init_session()

# =========================================================
# 5. 사이드바 - AI 엔진 설정
# =========================================================
st.sidebar.header("⚙️ AI 엔진 설정")

current_settings = st.session_state["settings"]
provider = current_settings.get("provider", "gemini")
if provider not in MODEL_OPTIONS:
    provider = "gemini"

provider = st.sidebar.selectbox(
    "Provider",
    options=list(MODEL_OPTIONS.keys()),
    index=list(MODEL_OPTIONS.keys()).index(provider)
)

saved_model = current_settings.get("model", MODEL_OPTIONS[provider][0])
if saved_model not in MODEL_OPTIONS[provider]:
    saved_model = MODEL_OPTIONS[provider][0]

model = st.sidebar.selectbox(
    "Model",
    options=MODEL_OPTIONS[provider],
    index=MODEL_OPTIONS[provider].index(saved_model)
)

api_key = st.sidebar.text_input(
    "API Key",
    value=current_settings.get("api_key", ""),
    type="password"
)

if st.sidebar.button("💾 저장", use_container_width=True):
    save_settings(provider, api_key, model)
    st.session_state["settings"] = load_settings()
    st.success("저장 완료")
    st.rerun()

# =========================================================
# 6. 사이드바 - 업체 관리
# =========================================================
st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")

tab_save, tab_load = st.sidebar.tabs(["💾 저장하기", "📂 불러오기"])

with tab_save:
    if st.button("현재 정보 저장", use_container_width=True):
        current_name = st.session_state.get("in_company_name", "").strip()
        if current_name:
            current_data = get_current_company_data()
            current_data["in_company_name"] = current_name
            st.session_state["company_list"][current_name] = current_data
            save_companies(st.session_state["company_list"])
            st.session_state["active_company"] = current_name
            st.session_state["selected_company_name"] = current_name
            st.success(f"'{current_name}' 저장 완료!")
        else:
            st.error("기업명을 입력하세요.")

with tab_load:
    company_names = list(st.session_state["company_list"].keys())
    if company_names:
        default_index = 0
        if st.session_state["selected_company_name"] in company_names:
            default_index = company_names.index(st.session_state["selected_company_name"])

        target = st.selectbox("업체 선택", options=company_names, index=default_index)

        if st.button("데이터 불러오기", use_container_width=True):
            loaded = st.session_state["company_list"][target]
            apply_company_data(target, loaded)
            st.success(f"'{target}' 불러오기 완료!")
            st.rerun()

        st.markdown("---")

        if st.button("🗑 선택 업체 삭제", use_container_width=True):
            if target in st.session_state["company_list"]:
                del st.session_state["company_list"][target]
                save_companies(st.session_state["company_list"])

                if st.session_state.get("active_company") == target:
                    st.session_state["active_company"] = ""
                    st.session_state["selected_company_name"] = ""
                    reset_input_form()
                else:
                    if st.session_state.get("selected_company_name") == target:
                        st.session_state["selected_company_name"] = ""

                st.success(f"'{target}' 삭제 완료")
                st.rerun()
    else:
        st.info("저장된 업체가 없습니다.")

# =========================================================
# 7. 사이드바 - 리포트 생성 탭
# =========================================================
st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")

for i in range(4):
    if st.sidebar.button(REPORT_LABELS[i], key=f"side_{i}", use_container_width=True):
        st.session_state["view_mode"] = REPORT_MODES[i]
        st.rerun()

# =========================================================
# 8. 메인 헤더 / 상단 버튼
# =========================================================
st.title("📊 AI 컨설팅 대시보드")

if st.session_state.get("active_company"):
    st.markdown(
        f"""
        <div class="active-company-box">
            현재 진행중 업체: {st.session_state["active_company"]}
        </div>
        """,
        unsafe_allow_html=True
    )

top_cols = st.columns(4)
for i in range(4):
    if top_cols[i].button(REPORT_LABELS[i], key=f"top_{i}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = REPORT_MODES[i]
        st.rerun()

st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"

# =========================================================
# 9. 입력 화면
# =========================================================
if st.session_state["view_mode"] == "INPUT":
    st.header("1. 기업현황")
    c1_f1 = st.columns([2, 1, 1.5, 1.5])
    with c1_f1[0]:
        st.text_input("기업명", key="in_company_name")
    with c1_f1[1]:
        st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1_f1[2]:
        st.text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    with c1_f1[3]:
        st.text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")

    c1_f2 = st.columns([1, 1, 1, 1])
    with c1_f2[0]:
        st.text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD")
    with c1_f2[1]:
        st.text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-00-0000")
    with c1_f2[2]:
        st.text_input("이메일 주소", key="in_email_addr", placeholder="example@email.com")
    with c1_f2[3]:
        st.selectbox("현사업장 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    c1_f3 = st.columns([1.2, 3, 0.9, 0.9])
    with c1_f3[0]:
        st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c1_f3[1]:
        st.text_input("사업장 주소", key="in_biz_addr", placeholder="소재지를 입력하세요")
    with c1_f3[2]:
        st.number_input("보증금 (만원)", key="in_lease_deposit", step=1, placeholder=GUIDE_STR, value=None)
    with c1_f3[3]:
        st.number_input("월임대료 (만원)", key="in_lease_rent", step=1, placeholder=GUIDE_STR, value=None)

    c1_f4 = st.columns([1.2, 3, 1.8])
    with c1_f4[0]:
        st.radio("추가 사업장 여부", ["없음", "있음"], horizontal=True, key="in_has_extra_biz")
    with c1_f4[1]:
        st.text_input("추가사업장 정보입력", key="in_extra_biz_info", placeholder="사업장명/사업자등록번호")
    with c1_f4[2]:
        st.empty()
    st.markdown("---")

    st.header("2. 대표자 정보")
    c2r1 = st.columns([1, 1, 1, 1])
    with c2r1[0]:
        st.text_input("대표자명", key="in_rep_name")
    with c2r1[1]:
        st.text_input("생년월일", key="in_rep_dob")
    with c2r1[2]:
        st.text_input("연락처", key="in_rep_phone")
    with c2r1[3]:
        st.selectbox("통신사", ["선택", "SKT", "KT", "LGU+", "알뜰폰"], key="in_rep_carrier")

    c2r2 = st.columns([2, 1, 1])
    with c2r2[0]:
        st.text_input("거주지 주소", key="in_home_addr")
    with c2r2[1]:
        st.radio("거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status")
    with c2r2[2]:
        st.multiselect("부동산 보유현황", ["아파트", "빌라", "토지", "공장", "임야"], key="in_real_estate")

    c2r3 = st.columns([0.8, 0.8, 1.2, 1.2])
    with c2r3[0]:
        st.selectbox("최종학력", ["선택", "중졸", "고졸", "대졸", "석사", "박사"], key="in_edu_level")
    with c2r3[1]:
        st.text_input("전공", key="in_rep_major")
    with c2r3[2]:
        st.text_input("경력사항 1", key="in_rep_career_1")
    with c2r3[3]:
        st.text_input("경력사항 2", key="in_rep_career_2")
    st.markdown("---")

    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.5, 1.3, 1.8])
    with c3_col1:
        l_r1 = st.columns(2)
        l_r1[0].radio("금융연체여부", ["없음", "있음"], horizontal=True, key="in_fin_delinquency")
        l_r1[1].radio("세금체납여부", ["없음", "있음"], horizontal=True, key="in_tax_delinquency")
        l_r2 = st.columns(2)
        s_kcb = l_r2[0].number_input("KCB 점수", key="in_kcb_score", step=1, value=None)
        s_nice = l_r2[1].number_input("NICE 점수", key="in_nice_score", step=1, value=None)

    with c3_col2:
        vk, vn = safe_int(s_kcb), safe_int(s_nice)
        if st.session_state.get("in_fin_delinquency") == "있음" or st.session_state.get("in_tax_delinquency") == "있음":
            status = "🔴 진행 위험"
        elif vk > 700 or vn > 700:
            status = "🟢 진행 원활"
        else:
            status = "🟡 진행 주의"

        st.markdown(
            f'<div class="summary-box-compact"><p style="font-weight:700;">신용상태요약</p><p style="font-size:1.45em; font-weight:800;">{status}</p></div>',
            unsafe_allow_html=True
        )

    with c3_col3:
        kg, kc = get_kcb_grade(vk)
        ng, nc = get_nice_grade(vn)
        res_c1, res_c2 = st.columns(2)
        with res_c1:
            st.markdown(
                f'<div class="score-result-box"><p class="result-title">KCB 결과</p><p style="font-size:1.8em; font-weight:800; color:{kc};">{vk}점</p><p>{kg}</p></div>',
                unsafe_allow_html=True
            )
        with res_c2:
            st.markdown(
                f'<div class="score-result-box"><p class="result-title">NICE 결과</p><p style="font-size:1.8em; font-weight:800; color:{nc};">{vn}점</p><p>{ng}</p></div>',
                unsafe_allow_html=True
            )
    st.markdown("---")

    st.header("4. 매출현황")
    exp_cols = st.columns(2)
    with exp_cols[0]:
        has_exp = st.radio("수출매출 여부", ["없음", "있음"], horizontal=True, key="in_export_revenue")
    with exp_cols[1]:
        st.radio("수출예정 여부", ["없음", "있음"], horizontal=True, key="in_planned_export")

    mc = st.columns(4)
    m_keys = [("금년 매출", "in_sales_cur"), ("25년 매출", "in_sales_25"), ("24년 매출", "in_sales_24"), ("23년 매출", "in_sales_23")]
    for i, (t, k) in enumerate(m_keys):
        mc[i].number_input(f"{t} (만원)", key=k, step=1, placeholder=GUIDE_STR, value=None)

    if has_exp == "있음":
        st.markdown("<p style='font-size:14px; font-weight:600;'>[수출매출 상세역사]</p>", unsafe_allow_html=True)
        ec = st.columns(4)
        e_keys = [("금년 수출액", "in_exp_cur"), ("25년 수출액", "in_exp_25"), ("24년 수출액", "in_exp_24"), ("23년 수출액", "in_exp_23")]
        for i, (t, k) in enumerate(e_keys):
            ec[i].number_input(f"{t} (만원)", key=k, step=1, placeholder=GUIDE_STR, value=None)
    st.markdown("---")

    st.header("5. 부채현황")
    debt_items = [
        ("중진공", "in_debt_kosme"), ("소진공", "in_debt_semas"), ("신보", "in_debt_kodit"), ("기보", "in_debt_kibo"),
        ("재단", "in_debt_foundation"), ("회사담보", "in_debt_corp_coll"), ("대표신용", "in_debt_rep_cred"), ("대표담보", "in_debt_rep_coll")
    ]
    for r in range(0, 8, 4):
        cols = st.columns(4)
        for i in range(4):
            cols[i].number_input(f"{debt_items[r+i][0]} (만원)", key=debt_items[r+i][1], step=1, placeholder=GUIDE_STR, value=None)
    st.markdown("---")

    st.header("6. 보유 인증")
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j < len(CERT_LIST):
                cols[j].checkbox(CERT_LIST[i+j], key=f"in_cert_{i+j}")
    st.markdown("---")

    st.header("7. 특허 및 정부지원")
    c7 = st.columns(2)
    with c7[0]:
        st.radio("특허 보유 여부", ["없음", "있음"], horizontal=True, key="in_has_patent")
        st.number_input("보유 건수", key="in_pat_cnt", step=1, value=None)
        st.text_area("특허 상세 내용", key="in_pat_desc")
    with c7[1]:
        st.radio("정부지원 수혜이력", ["없음", "있음"], horizontal=True, key="in_has_gov")
        st.number_input("수혜 건수", key="in_gov_cnt", step=1, value=None)
        st.text_area("수혜 사업명 상세", key="in_gov_desc")
    st.markdown("---")

    st.header("8. 비즈니스 상세 정보")
    r8_1 = st.columns(2)
    with r8_1[0]:
        st.text_area("핵심 아이템", key="in_item_desc", height=100, placeholder="제품/서비스 기능 상세")
    with r8_1[1]:
        st.text_area("판매 루트(유통망)", key="in_sales_route", height=100, placeholder="주요 거래처 및 채널")
    r8_2 = st.columns(2)
    with r8_2[0]:
        st.text_area("경쟁력 및 차별성", key="in_item_diff", height=100, placeholder="타사 대비 강점")
    with r8_2[1]:
        st.text_area("시장 현황", key="in_market_status", height=100, placeholder="업계 분위기")
    r8_3 = st.columns(2)
    with r8_3[0]:
        st.text_area("공정도", key="in_process_desc", height=100, placeholder="생산 과정 요약")
    with r8_3[1]:
        st.text_area("타겟 고객", key="in_target_cust", height=100, placeholder="주요 구매층")
    r8_4 = st.columns(2)
    with r8_4[0]:
        st.text_area("수익 모델", key="in_revenue_model", height=100, placeholder="매출 발생 구조")
    with r8_4[1]:
        st.text_area("앞으로의 계획", key="in_future_plan", height=100, placeholder="향후 목표")
    st.markdown("---")

    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-bold-label-16">이번 조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", key="in_req_funds", label_visibility="collapsed", step=1, placeholder=GUIDE_STR, value=None)
    with c9[1]:
        st.markdown('<p style="font-size:14px;">상세 자금 집행 계획</p>', unsafe_allow_html=True)
        st.text_area("자금집행", key="in_fund_plan", label_visibility="collapsed")

    st.markdown("---")

    current_data = get_current_company_data()
    policy_score, policy_grade = calc_simple_policy_score(current_data)
    guarantee_prob, guarantee_label = calc_simple_guarantee(current_data)

    st.subheader("실시간 자동 진단 요약")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("정책자금 점수", f"{policy_score}점")
    m2.metric("정책자금 등급", policy_grade)
    m3.metric("보증 확률", f"{guarantee_prob}%")
    m4.metric("보증 판단", guarantee_label)

# =========================================================
# 10. 리포트 화면 (현재는 준비용)
# =========================================================
else:

    if st.button("⬅️ 입력 화면으로 돌아가기"):
        st.session_state["view_mode"] = "INPUT"
        st.rerun()

    current_data = get_current_company_data()
    company_name = current_data.get("in_company_name", "").strip()

    if not company_name:
        st.warning("기업명이 입력되지 않았습니다.")
        st.stop()

    # ===============================
    # REPORT 모드: 기업진단 리포트
    # ===============================
    if st.session_state["view_mode"] == "REPORT":

        policy_score, policy_grade = calc_simple_policy_score(current_data)
        guarantee_prob, guarantee_label = calc_simple_guarantee(current_data)

        sales = calc_recent_sales(current_data)
        debt = calc_total_debt(current_data)
        certs = selected_certs(current_data)

        st.title("📊 기업진단 리포트")

        st.markdown(f"""
        ### 기업 개요
        - 기업명: **{company_name}**
        - 업종: **{current_data.get("in_industry","미입력")}**
        - 대표자: **{current_data.get("in_rep_name","미입력")}**
        """)

        st.markdown("---")

        col1, col2, col3 = st.columns(3)

        col1.metric("정책자금 점수", f"{policy_score}점")
        col2.metric("정책자금 등급", policy_grade)
        col3.metric("보증 승인 확률", f"{guarantee_prob}%")

        st.markdown("---")

        st.subheader("재무 구조 분석")

        st.write(f"- 최근 매출 추정: **{sales:,} 만원**")
        st.write(f"- 총 부채 규모: **{debt:,} 만원**")

        if sales > 0:
            ratio = round((debt / sales) * 100, 1)
            st.write(f"- 부채비율 추정: **{ratio}%**")

            if ratio <= 50:
                st.success("재무 안정성이 우수한 구조입니다.")
            elif ratio <= 120:
                st.warning("부채 관리가 일부 필요합니다.")
            else:
                st.error("부채 구조 개선 전략이 필요합니다.")
        else:
            st.info("매출 데이터가 부족합니다.")

        st.markdown("---")

        st.subheader("인증 및 기술 요소")

        if certs:
            for c in certs:
                st.write(f"✔ {c}")
        else:
            st.write("보유 인증 없음")

        if current_data.get("in_has_patent") == "있음":
            st.write("✔ 특허 보유 기업")

        if current_data.get("in_export_revenue") == "있음":
            st.write("✔ 수출 실적 보유 기업")

        st.markdown("---")

        st.subheader("보증기관 평가 해석")

        st.write(f"보증 승인 가능성 판단: **{guarantee_label}**")

        if guarantee_prob >= 80:
            st.success("보증기관 접근이 매우 유리한 상태입니다.")
        elif guarantee_prob >= 60:
            st.info("조건부 접근 가능한 수준입니다.")
        else:
            st.warning("재무 또는 신용 보완 후 접근 권장")

        st.markdown("---")

        st.subheader("종합 컨설팅 의견")

        if policy_score >= 75:
            st.success("정책자금 활용에 매우 유리한 기업입니다.")
        elif policy_score >= 58:
            st.info("일부 보완 후 정책자금 접근이 가능합니다.")
        else:
            st.warning("재무·신용 구조 보완 전략이 필요합니다.")

        st.markdown("""
        ### 추천 실행 전략
        1. 정책자금 우선 접근 기관 선정
        2. 보증기관 사전 상담 진행
        3. 인증 또는 특허 보강 전략 검토
        4. 매출 구조 개선 자료 준비
        """)

    # ===============================
    # MATCHING 모드 (다음 단계 연결 예정)
    # ===============================
    elif st.session_state["view_mode"] == "MATCHING":

        st.title("💡 정책자금 매칭 + 보증가능성 리포트")
        st.info("다음 단계에서 정책자금 자동 매칭 엔진이 연결됩니다.")

    # ===============================
    # LOAN_PLAN 모드 (기관별 사업계획서 슬롯)
    # ===============================
    elif st.session_state["view_mode"] == "LOAN_PLAN":

        st.title("📝 기관별 융자/사업계획서")
        st.info("기관별 템플릿 기반 사업계획서 엔진 연결 예정입니다.")

    # ===============================
    # AI_PLAN 모드
    # ===============================
    elif st.session_state["view_mode"] == "AI_PLAN":

        st.title("📑 AI 사업계획서")
        st.info("AI 자동 생성 사업계획서 엔진 연결 예정입니다.")
