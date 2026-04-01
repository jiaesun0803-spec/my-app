import streamlit as st
import json
import os
import time
import streamlit.components.v1 as components
import google.generativeai as genai

# ==========================================
# 0. 시스템 설정 및 데이터 초기화 (데이터 유실 원천 차단)
# ==========================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"
GUIDE_STR = "1억=10000으로 입력"

# 모든 입력 필드 정의 (3/27 자료 기반 전체 복구)
INPUT_FIELDS = [
    "in_company_name", "in_biz_type", "in_raw_biz_no", "in_raw_corp_no",
    "in_start_date", "in_biz_tel", "in_email_addr", "in_industry",
    "in_lease_status", "in_biz_addr", "in_lease_deposit", "in_lease_rent",
    "in_has_extra_biz", "in_extra_biz_info", 
    # 2번 대표자 정보 복구
    "in_rep_name", "in_rep_dob", "in_rep_phone", "in_rep_carrier", 
    "in_home_addr", "in_home_status", "in_real_estate", 
    "in_edu_level", "in_rep_major", "in_rep_career_1", "in_rep_career_2",
    # 3번 신용 및 4번 매출
    "in_fin_delinquency", "in_tax_delinquency", "in_kcb_score", "in_nice_score",
    "in_export_revenue", "in_planned_export",
    "in_sales_cur", "in_sales_25", "in_sales_24", "in_sales_23",
    "in_exp_cur", "in_exp_25", "in_exp_24", "in_exp_23",
    # 5~7번 부채/인증/특허
    "in_debt_kosme", "in_debt_semas", "in_debt_kodit", "in_debt_kibo", 
    "in_debt_foundation", "in_debt_corp_coll", "in_debt_rep_cred", "in_debt_rep_coll",
    "in_has_patent", "in_pat_cnt", "in_pat_desc", "in_has_gov", "in_gov_cnt", "in_gov_desc",
    # 8번 비즈니스 상세 (8종 전체 복구)
    "in_item_desc", "in_sales_route", "in_item_diff", "in_market_status",
    "in_process_desc", "in_target_cust", "in_revenue_model", "in_future_plan",
    # 9번 자금
    "in_req_funds", "in_fund_plan"
]
CERT_KEYS = [f"in_cert_{i}" for i in range(8)]

# 숫자형 필드 식별
numeric_keywords = ["cnt", "score", "deposit", "rent", "sales", "exp", "funds", "debt"]

# 세션 상태 초기화 (오류 방지 및 데이터 고정)
for field in INPUT_FIELDS + CERT_KEYS:
    if field not in st.session_state:
        if any(kw in field for kw in numeric_keywords): st.session_state[field] = None
        elif field.startswith("in_cert_"): st.session_state[field] = False
        else: st.session_state[field] = ""

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 1. 디자인 커스텀 (CSS - 파란색 선 제거 및 가독성)
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown(f"""
<style>
    /* 헤더 파란색 선 제거 및 크기 조정 */
    h2 {{ font-weight: 700 !important; margin-top: 30px !important; color: #111 !important; border-left: none !important; }}
    [data-testid="stWidgetLabel"] p {{ font-weight: 400 !important; font-size: 14px !important; color: #31333F !important; }}
    input::placeholder {{ font-size: 0.85em !important; color: #aaa !important; }}
    
    /* 6번 인증서 체크박스 폰트 키우기 */
    [data-testid="stCheckbox"] label p {{ font-size: 18px !important; font-weight: 500 !important; }}
    
    /* 3번 신용정보 결과 박스 복구 */
    .summary-box-compact {{ background-color: #E8F5E9; padding: 15px; border-radius: 10px; border: 1px solid #ddd; text-align: center; height: 145px; display: flex; flex-direction: column; justify-content: center; }}
    .score-result-box {{ background-color: #F1F8E9; padding: 15px; border-radius: 10px; border: 1px solid #C8E6C9; text-align: center; height: 145px; display: flex; flex-direction: column; justify-content: center; }}
    .result-title {{ font-size: 17px !important; font-weight: 700 !important; color: #2E7D32; margin-bottom: 5px !important; }}
    .blue-bold-label-16 {{ color: #1E88E5 !important; font-size: 16px !important; font-weight: 700 !important; }}
</style>
""", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "settings" not in st.session_state: st.session_state["settings"] = load_json(SETTINGS_FILE, {"api_key": ""})
if "company_list" not in st.session_state: st.session_state["company_list"] = load_json(DATA_FILE, {})
if "edit_api_key" not in st.session_state: st.session_state["edit_api_key"] = False

# 등급 계산 함수
def get_grade(score, type="KCB"):
    s = (score or 0)
    if type == "KCB":
        if s >= 942: return "1등급", "#43A047"
        elif s >= 832: return "3등급", "#66BB6A"
        return "6등급이하", "#EF6C00"
    else:
        if s >= 900: return "1등급", "#1E88E5"
        elif s >= 840: return "3등급", "#42A5F5"
        return "6등급이하", "#EF6C00"

# ==========================================
# 2. 사이드바 (업체 관리 및 리포트 탭)
# ==========================================
st.sidebar.header("⚙️ AI 엔진 설정")
saved_key = st.session_state["settings"].get("api_key", "")
if saved_key and not st.session_state["edit_api_key"]:
    st.sidebar.success("✅ API Key 저장됨")
    if st.sidebar.button("🔄 API Key 변경"): st.session_state["edit_api_key"] = True; st.rerun()
else:
    new_key = st.sidebar.text_input("Gemini API Key", value=saved_key, type="password")
    if st.sidebar.button("💾 영구 저장"):
        save_json(SETTINGS_FILE, {"api_key": new_key}); st.session_state["settings"]["api_key"] = new_key
        st.session_state["edit_api_key"] = False; st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")
t_s, t_l = st.sidebar.tabs(["💾 저장", "📂 불러오기"])
with t_s:
    if st.button("현재 정보 파일 저장", use_container_width=True):
        name = st.session_state.in_company_name.strip()
        if name:
            st.session_state["company_list"][name] = {k: st.session_state[k] for k in INPUT_FIELDS + CERT_KEYS}
            save_json(DATA_FILE, st.session_state["company_list"]); st.success(f"'{name}' 저장 완료!")
        else: st.error("기업명을 입력하세요.")
with t_l:
    if st.session_state["company_list"]:
        target = st.selectbox("업체 선택", list(st.session_state["company_list"].keys()))
        if st.button("데이터 불러오기", use_container_width=True):
            for k, v in st.session_state["company_list"][target].items(): st.session_state[k] = v
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")
report_types = {"REPORT":"📊 AI 기업분석리포트", "MATCHING":"💡 AI 정책자금 매칭", "LOAN_PLAN":"📝 융자/사업계획서", "AI_PLAN":"📑 AI 사업계획서"}
for m, l in report_types.items():
    if st.sidebar.button(l, key=f"side_{m}", use_container_width=True):
        st.session_state["view_mode"] = m; st.rerun()

# ==========================================
# 3. 메인 대시보드
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
for i, (m, l) in enumerate(report_types.items()):
    if t_cols[i].button(l, key=f"top_{m}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = m; st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (요청하신 최종 4층 구조) ---
    st.header("1. 기업현황")
    c1 = st.columns([2, 1, 1.5, 1.5])
    c1[0].text_input("기업명", key="in_company_name")
    c1[1].radio("사업자유형", ["개인", "법인"], key="in_biz_type", horizontal=True)
    c1[2].text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    c1[3].text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")
    
    c2 = st.columns([1, 1, 1, 1])
    c2[0].text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD")
    c2[1].text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-00-0000")
    c2[2].text_input("이메일 주소", key="in_email_addr", placeholder="example@email.com")
    c2[3].selectbox("현사업장 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
    
    c3 = st.columns([1.2, 3, 0.9, 0.9])
    c3[0].radio("사업장 임대여부", ["자가", "임대"], key="in_lease_status", horizontal=True)
    c3[1].text_input("사업장 주소", key="in_biz_addr", placeholder="소재지를 입력하세요")
    c3[2].number_input("보증금 (만원)", key="in_lease_deposit", placeholder=GUIDE_STR, value=st.session_state.in_lease_deposit)
    c3[3].number_input("월임대료 (만원)", key="in_lease_rent", placeholder=GUIDE_STR, value=st.session_state.in_lease_rent)
    
    c4 = st.columns([1.2, 3, 1.8])
    c4[0].radio("추가 사업장 여부", ["없음", "있음"], key="in_has_extra_biz", horizontal=True)
    c4[1].text_input("추가사업장 정보입력", key="in_extra_biz_info", placeholder="사업장명/사업자등록번호")
    c4[2].empty()

    # --- 2. 대표자 정보 (완벽 복구) ---
    st.markdown("---")
    st.header("2. 대표자 정보")
    r2c1 = st.columns([1, 1, 1, 1])
    r2c1[0].text_input("대표자명", key="in_rep_name")
    r2c1[1].text_input("생년월일", key="in_rep_dob", placeholder="YYYY.MM.DD")
    r2c1[2].text_input("연락처", key="in_rep_phone", placeholder="010-0000-0000")
    r2c1[3].selectbox("통신사", ["선택", "SKT", "KT", "LGU+", "알뜰폰"], key="in_rep_carrier")
    
    r2c2 = st.columns([2, 1, 1])
    r2c2[0].text_input("거주지 주소", key="in_home_addr")
    r2c2[1].radio("거주지 상태", ["자가", "임대"], key="in_home_status", horizontal=True)
    r2c2[2].multiselect("부동산 보유", ["아파트", "빌라", "토지", "공장"], key="in_real_estate")
    
    r2c3 = st.columns([1, 1, 2, 2])
    r2c3[0].selectbox("학력", ["선택", "고졸", "대졸", "석사", "박사"], key="in_edu_level")
    r2c3[1].text_input("전공", key="in_rep_major")
    r2c3[2].text_input("경력 1", key="in_rep_career_1")
    r2c3[3].text_input("경력 2", key="in_rep_career_2")

    # --- 3. 대표자 신용정보 (디자인 및 결과박스 복구) ---
    st.markdown("---")
    st.header("3. 대표자 신용정보")
    cc1, cc2, cc3 = st.columns([1.5, 1.3, 1.8])
    with cc1:
        cr1 = st.columns(2)
        cr1[0].radio("금융연체", ["없음", "있음"], key="in_fin_delinquency", horizontal=True)
        cr1[1].radio("세금체납", ["없음", "있음"], key="in_tax_delinquency", horizontal=True)
        cr2 = st.columns(2)
        sk = cr2[0].number_input("KCB 점수", key="in_kcb_score", value=st.session_state.in_kcb_score)
        sn = cr2[1].number_input("NICE 점수", key="in_nice_score", value=st.session_state.in_nice_score)
    with cc2:
        vk = (sk or 0)
        status = "🟢 진행 원활" if vk > 700 else "🟡 진행 주의"
        st.markdown(f'<div class="summary-box-compact"><p style="font-weight:700;">신용요약</p><h3>{status}</h3><p>종합 분석 결과</p></div>', unsafe_allow_html=True)
    with cc3:
        kg, kc = get_grade(sk, "KCB"); ng, nc = get_grade(sn, "NICE")
        rc1, rc2 = st.columns(2)
        rc1.markdown(f'<div class="score-result-box"><p class="result-title">KCB 결과</p><h2 style="color:{kc}; margin:0;">{sk or 0}점</h2><p>{kg}</p></div>', unsafe_allow_html=True)
        rc2.markdown(f'<div class="score-result-box"><p class="result-title">NICE 결과</p><h2 style="color:{nc}; margin:0;">{sn or 0}점</h2><p>{ng}</p></div>', unsafe_allow_html=True)

    # --- 4. 매출 및 수출현황 ---
    st.markdown("---")
    st.header("4. 매출 및 수출현황")
    ec = st.columns(2)
    with ec[0]: has_exp = st.radio("수출매출 여부", ["없음", "있음"], key="in_export_revenue", horizontal=True)
    with ec[1]: plan_exp = st.radio("수출예정 여부", ["없음", "있음"], key="in_planned_export", horizontal=True)
    m_cols = st.columns(4)
    m_cols[0].number_input("금년 매출", key="in_sales_cur", placeholder=GUIDE_STR, value=st.session_state.in_sales_cur)
    m_cols[1].number_input("25년 매출", key="in_sales_25", placeholder=GUIDE_STR, value=st.session_state.in_sales_25)
    m_cols[2].number_input("24년 매출", key="in_sales_24", placeholder=GUIDE_STR, value=st.session_state.in_sales_24)
    m_cols[3].number_input("23년 매출", key="in_sales_23", placeholder=GUIDE_STR, value=st.session_state.in_sales_23)
    if has_exp == "있음":
        e_cols = st.columns(4)
        e_cols[0].number_input("금년 수출", key="in_exp_cur", placeholder=GUIDE_STR, value=st.session_state.in_exp_cur)
        e_cols[1].number_input("25년 수출", key="in_exp_25", placeholder=GUIDE_STR, value=st.session_state.in_exp_25)
        e_cols[2].number_input("24년 수출", key="in_exp_24", placeholder=GUIDE_STR, value=st.session_state.in_exp_24)
        e_cols[3].number_input("23년 수출", key="in_exp_23", placeholder=GUIDE_STR, value=st.session_state.in_exp_23)

    # --- 5. 부채현황 ---
    st.markdown("---")
    st.header("5. 부채현황 (만원)")
    d_keys = [("중진공", "in_debt_kosme"), ("소진공", "in_debt_semas"), ("신보", "in_debt_kodit"), ("기보", "in_debt_kibo"), 
              ("재단", "in_debt_foundation"), ("회사담보", "in_debt_corp_coll"), ("대표신용", "in_debt_rep_cred"), ("대표담보", "in_debt_rep_coll")]
    for r in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4): cols[j].number_input(d_keys[r+j][0], key=d_keys[r+j][1], placeholder=GUIDE_STR, value=st.session_state[d_keys[r+j][1]])

    # --- 6. 보유 인증 ---
    st.markdown("---")
    st.header("6. 보유 인증")
    c_list = ["중소기업확인서(소상공인확인서)", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4): cols[j].checkbox(c_list[i+j], key=f"in_cert_{i+j}")

    # --- 8. 비즈니스 상세 정보 (8종 완벽 복구) ---
    st.markdown("---")
    st.header("8. 비즈니스 상세 정보")
    b_rows = [("핵심 아이템", "in_item_desc", "판매 루트", "in_sales_route"),
              ("경쟁력/차별성", "in_item_diff", "시장 현황", "in_market_status"),
              ("생산 공정도", "in_process_desc", "타겟 고객", "in_target_cust"),
              ("수익 모델", "in_revenue_model", "미래 계획", "in_future_plan")]
    for labels in b_rows:
        cols = st.columns(2)
        cols[0].text_area(labels[0], key=labels[1], height=100)
        cols[1].text_area(labels[2], key=labels[3], height=100)

    # --- 9. 자금 계획 ---
    st.markdown("---")
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    c9[0].number_input("조달 필요 금액 (만원)", key="in_req_funds", placeholder=GUIDE_STR, value=st.session_state.in_req_funds)
    c9[1].text_area("상세 자금 집행 계획", key="in_fund_plan")

# ==========================================
# 4. 리포트 출력 화면 (데이터 인식 오류 완벽 수정)
# ==========================================
else:
    col_back, col_style = st.columns([6, 2])
    if col_back.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    r_style = col_style.selectbox("리포트 스타일 선택", ["문서형", "랜딩페이지형"])

    # [핵심 수동 동기화] 세션 상태에서 직접 데이터 추출
    biz_name = st.session_state.get("in_company_name", "").strip()
    api_key = st.session_state["settings"].get("api_key", "")
    
    if not api_key: st.error("사이드바에서 API Key를 먼저 저장해 주세요.")
    elif not biz_name: 
        st.warning("⚠️ 분석할 기업 정보가 없습니다. 입력 화면에서 '기업명'을 먼저 작성해 주세요.")
        if st.button("기업명 입력하러 가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    else:
        with st.status(f"🚀 {biz_name} 리포트 생성 중..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash-latest')
                
                # 리포트용 데이터 정리
                current_data = {k: st.session_state[k] for k in INPUT_FIELDS + CERT_KEYS}
                summary = "\n".join([f"{k}: {v}" for k, v in current_data.items() if v])
                
                style_inst = "관공서/은행 제출용 전문 표 형식 리포트" if r_style == "문서형" else "프리미엄 랜딩페이지 리포트"
                prompt = f"다음 기업정보를 바탕으로 {style_inst} HTML 리포트를 작성하세요:\n{summary}"
                
                response = model.generate_content(prompt)
                res_html = response.text.replace('```html', '').replace('```', '').strip()
                components.html(res_html, height=1200, scrolling=True)
            except Exception as e:
                st.error(f"리포트 생성 실패: {str(e)}")
