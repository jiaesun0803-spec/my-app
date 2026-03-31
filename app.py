import streamlit as st
import json
import os
import time
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 0. 핵심 설정 및 디자인 커스텀 (CSS)
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    /* 1. 모든 위젯 라벨 설정: 일반 굵기(400), 폰트 크기 14px */
    [data-testid="stWidgetLabel"] p {
        font-weight: 400 !important;
        font-size: 14px !important;
        color: #31333F !important;
        margin-bottom: 5px !important;
    }
    /* 2. 섹션 헤더는 볼드 유지 */
    h2 { font-weight: 700 !important; }
    
    /* 3. 입력창 내부 Placeholder(흐릿한 글씨) 크기 조절: 0.8em */
    input::placeholder {
        font-size: 0.8em !important;
        color: #888 !important;
    }
    
    /* 4. 숫자 입력창 우측 증감 버튼 숨기기 */
    input::-webkit-outer-spin-button,
    input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    
    /* 5. 9번 섹션 파란색 라벨 전용 */
    .blue-label {
        color: #1E88E5 !important;
        font-size: 14px !important;
        font-weight: 400 !important;
    }
</style>
""", unsafe_allow_html=True)

def safe_int(value):
    """숫자 입력이 None이거나 비어있을 때 0으로 처리하는 안전 함수"""
    try:
        if value is None or value == "": return 0
        clean_val = str(value).replace(',', '').strip()
        return int(float(clean_val))
    except: return 0

def format_kr_currency(value):
    val = safe_int(value)
    if val == 0: return "0원"
    uk, man = val // 10000, val % 10000
    if uk > 0 and man > 0: return f"{uk}억 {man:,}만원"
    elif uk > 0: return f"{uk}억원"
    else: return f"{man:,}만원"

def clean_html(text):
    if not text: return ""
    cleaned = text.replace("```html", "").replace("```", "").replace("```json", "").strip()
    return cleaned

def get_best_model_name():
    return 'gemini-1.5-flash'

# --- 신용 등급 판정 로직 (N등급 표기) ---
def get_kcb_info(score):
    s = safe_int(score)
    if s >= 942: return "1등급", "#43A047"
    if s >= 891: return "2등급", "#43A047"
    if s >= 832: return "3등급", "#43A047"
    if s >= 768: return "4등급", "#FB8C00"
    if s >= 698: return "5등급", "#FB8C00"
    if s >= 630: return "6등급", "#FB8C00"
    if s >= 530: return "7등급", "#E53935"
    if s >= 454: return "8등급", "#E53935"
    if s >= 335: return "9등급", "#E53935"
    return "10등급", "#E53935"

def get_nice_info(score):
    s = safe_int(score)
    if s >= 900: return "1등급", "#1E88E5"
    if s >= 870: return "2등급", "#1E88E5"
    if s >= 840: return "3등급", "#43A047"
    if s >= 805: return "4등급", "#43A047"
    if s >= 750: return "5등급", "#FB8C00"
    if s >= 665: return "6등급", "#FB8C00"
    if s >= 600: return "7등급", "#E53935"
    if s >= 515: return "8등급", "#E53935"
    if s >= 445: return "9등급", "#E53935"
    return "10등급", "#E53935"

def create_gauge(score, title, color):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = score if score else 0,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 14}},
        gauge = {
            'axis': {'range': [None, 1000]}, 'bar': {'color': color},
            'bgcolor': "white", 'borderwidth': 1,
            'steps': [{'range': [0, 600], 'color': '#FFEBEE'}, {'range': [600, 850], 'color': '#FFF3E0'}, {'range': [850, 1000], 'color': '#E8F5E9'}],
        }
    ))
    fig.update_layout(height=165, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
    return fig

# ==========================================
# 1. 파일 및 데이터 관리
# ==========================================
DB_FILE = "company_db.json"
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(data): json.dump(data, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

# ---------------- 사이드바 ----------------
st.sidebar.header("⚙️ AI 엔진 설정")
if "api_key_saved" not in st.session_state: st.session_state["api_key_saved"] = False

if not st.session_state["api_key_saved"]:
    api_key_input = st.sidebar.text_input("Gemini API Key", type="password")
    if st.sidebar.button("💾 API KEY 저장"):
        if api_key_input:
            st.session_state["api_key"] = api_key_input
            st.session_state["api_key_saved"] = True
            st.rerun()
else:
    st.sidebar.success("✅ AI 엔진 연결됨")
    if st.sidebar.button("🔄 API KEY 변경"):
        st.session_state["api_key_saved"] = False
        st.rerun()

if st.session_state.get("api_key"): 
    genai.configure(api_key=st.session_state["api_key"])

st.sidebar.markdown("---")
st.sidebar.header("📂 업체 관리")
db = load_db()

if st.sidebar.button("💾 현재 업체 정보 저장", use_container_width=True):
    cn = st.session_state.get("in_company_name", "").strip()
    if cn:
        db[cn] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        save_db(db)
        st.sidebar.success(f"'{cn}' 저장 완료!")

selected_company = st.sidebar.selectbox("불러올 업체 선택", ["선택 안 함"] + list(db.keys()))
if st.sidebar.button("📂 불러오기") and selected_company != "선택 안 함":
    for k, v in db[selected_company].items(): st.session_state[k] = v
    st.session_state["view_mode"] = "INPUT"; st.rerun()

# [복구] 초기화 탭
st.sidebar.markdown("---")
if st.sidebar.button("🧹 전체 데이터 초기화", use_container_width=True):
    for key in list(st.session_state.keys()):
        if key.startswith("in_"): del st.session_state[key]
    st.rerun()

# ==========================================
# 2. 메인 화면
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
with t_cols[0]: 
    if st.button("📊 AI기업분석리포트", use_container_width=True, type="primary"): st.session_state["view_mode"] = "REPORT"; st.rerun()
with t_cols[1]: 
    if st.button("💡 AI 정책자금 매칭", use_container_width=True, type="primary"): st.session_state["view_mode"] = "MATCHING"; st.rerun()
with t_cols[2]: 
    if st.button("📝 AI 사업계획서", use_container_width=True, type="primary"): st.session_state["view_mode"] = "PLAN"; st.rerun()
with t_cols[3]: 
    if st.button("📑 데이터 리셋", use_container_width=True): 
        for key in list(st.session_state.keys()): 
            if key.startswith("in_"): del st.session_state[key]
        st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 ---
    st.header("1. 기업현황")
    c1r1 = st.columns([2, 1, 1.5, 1.5])
    with c1r1[0]: st.text_input("기업명", key="in_company_name")
    with c1r1[1]: st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1r1[2]: st.text_input("사업자번호", placeholder="000-00-00000", key="in_raw_biz_no")
    with c1r1[3]: st.text_input("법인등록번호", placeholder="000000-0000000", key="in_raw_corp_no")

    c1r2 = st.columns([1, 2, 1])
    with c1r2[0]: st.text_input("사업개시일", placeholder="YYYY.MM.DD", key="in_start_date")
    with c1r2[1]: st.text_input("사업장 주소", key="in_biz_addr")
    with c1r2[2]: st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    c1r3 = st.columns([1, 1, 1, 1])
    with c1r3[0]: st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c1r3[1]: st.text_input("전화번호", placeholder="010-0000-0000", key="in_biz_tel")
    with c1r3[2]: st.number_input("보증금 (만원)", value=st.session_state.get("in_lease_deposit", None), key="in_lease_deposit", placeholder=GUIDE_STR, step=1, format="%d")
    with c1r3[3]: st.number_input("월임대료 (만원)", value=st.session_state.get("in_lease_rent", None), key="in_lease_rent", placeholder=GUIDE_STR, step=1, format="%d")

    # --- 2. 대표자 정보 (복구) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    c2r1 = st.columns(4)
    with c2r1[0]: st.text_input("대표자명", key="in_rep_name")
    with c2r1[1]: st.text_input("생년월일", placeholder="YYYY.MM.DD", key="in_rep_dob")
    with c2r1[2]: st.text_input("연락처", placeholder="010-0000-0000", key="in_rep_phone")
    with c2r1[3]: st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")
    
    c2r2 = st.columns([1.5, 1, 1.5])
    with c2r2[0]: st.text_input("거주지 주소", key="in_home_addr")
    with c2r2[1]: st.selectbox("최종학력", ["선택", "중학교 졸업", "고등학교 졸업", "대학교 졸업", "석사 수료", "박사 수료"], key="in_edu_school")
    with c2r2[2]: st.text_input("전공", key="in_edu_major")

    c2r3 = st.columns([1, 2, 1])
    with c2r3[0]: st.radio("거주지 임대여부", ["자가", "임대"], horizontal=True, key="in_home_status")
    with c2r3[1]: st.multiselect("부동산 보유현황", ["아파트", "빌라", "토지", "공장", "임야"], key="in_real_estate")
    with c2r3[2]: st.text_input("이메일 주소", key="in_rep_email")

    c2r4 = st.columns(3)
    with c2r4[0]: st.text_input("주요경력 1", key="in_career_1")
    with c2r4[1]: st.text_input("주요경력 2", key="in_career_2")
    with c2r4[2]: st.text_input("주요경력 3", key="in_career_3")

    # --- 3. 대표자 신용정보 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.1, 1.2, 1.8])
    with c3_col1:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t1 = st.columns(2); t1[0].markdown("금융연체 여부"); t1[1].markdown("세금체납 여부")
        r1 = st.columns(2); delinquency = r1[0].radio("f_d", ["무", "유"], horizontal=True, key="in_fin_delinquency", label_visibility="collapsed")
        tax_delin = r1[1].radio("t_d", ["무", "유"], horizontal=True, key="in_tax_delinquency", label_visibility="collapsed")
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t2 = st.columns(2); t2[0].markdown("KCB 점수"); t2[1].markdown("NICE 점수")
        r2 = st.columns(2); s_kcb = r2[0].number_input("k_i", value=st.session_state.get("in_kcb_score", None), key="in_kcb_score", label_visibility="collapsed", placeholder="점수입력", step=1, format="%d")
        s_nice = r2[1].number_input("n_i", value=st.session_state.get("in_nice_score", None), key="in_nice_score", label_visibility="collapsed", placeholder="점수입력", step=1, format="%d")
    with c3_col2:
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        if delinquency == "유" or tax_delin == "유":
            box_html = "<div style='background-color:#FFEBEE; padding:20px; border-radius:10px; height:185px;'><p style='color:#B71C1C; font-weight:700;'>⚠️ 연체/체납 확인</p><p style='font-size:0.9em;'>심사 전 반드시 해결이 필요합니다.</p></div>"
        else:
            box_html = "<div style='background-color:#E8F5E9; padding:20px; border-radius:10px; height:185px;'><p style='color:#1B5E20; font-weight:700;'>✅ 신용 양호</p><p style='font-size:0.9em;'>기초 신용 요건을 충족하고 있습니다.</p></div>"
        st.markdown(box_html, unsafe_allow_html=True)
    with c3_col3:
        v_cols = st.columns(2); k_grade, k_color = get_kcb_info(s_kcb); n_grade, n_color = get_nice_info(s_nice)
        with v_cols[0]: 
            st.plotly_chart(create_gauge(s_kcb, "KCB Score", k_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:5px; background-color:{k_color}; color:white; border-radius:5px; font-size:0.9em; margin-top:-15px;'>KCB: {k_grade}</div>", unsafe_allow_html=True)
        with v_cols[1]: 
            st.plotly_chart(create_gauge(s_nice, "NICE Score", n_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:5px; background-color:{n_color}; color:white; border-radius:5px; font-size:0.9em; margin-top:-15px;'>NICE: {n_grade}</div>", unsafe_allow_html=True)

    # --- 4. 매출현황 (태그 제거 보완) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("4. 매출현황")
    exp_r = st.columns([1, 1, 2])
    with exp_r[0]: has_export = st.radio("수출매출 여부", ["무", "유"], horizontal=True, key="in_export_revenue")
    with exp_r[1]: plan_export = st.radio("수출예정 여부", ["무", "유"], horizontal=True, key="in_planned_export")
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    m_titles = ["금년 매출합계", "25년도 매출합계", "24년도 매출합계", "23년도 매출합계"]
    m_keys = ["in_sales_cur", "in_sales_25", "in_sales_24", "in_sales_23"]
    ic = st.columns(4)
    for i, key in enumerate(m_keys): 
        with ic[i]:
            st.markdown(f"{m_titles[i]} (만원)", unsafe_allow_html=True)
            st.number_input(m_titles[i], value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, label_visibility="collapsed", step=1, format="%d")
    
    if has_export == "유":
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        e_titles = ["금년 수출매출", "25년도 수출합계", "24년도 수출합계", "23년도 수출합계"]
        e_keys = ["in_exp_cur", "in_exp_25", "in_exp_24", "in_exp_23"]
        eic = st.columns(4)
        for i, key in enumerate(e_keys): 
            with eic[i]:
                st.markdown(f"{e_titles[i]} (만원)", unsafe_allow_html=True)
                st.number_input(e_titles[i], value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, label_visibility="collapsed", step=1, format="%d")

    # --- 5. 기대출 현황 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("5. 기대출 현황")
    debt_items = [("중진공", "in_debt_kosme"), ("소진공", "in_debt_semas"), ("신보", "in_debt_kodit"), ("기보", "in_debt_kibo"), ("재단", "in_debt_foundation"), ("회사담보", "in_debt_corp_coll"), ("대표신용", "in_debt_rep_cred"), ("대표담보", "in_debt_rep_coll")]
    for row in range(0, 8, 4):
        cols = st.columns(4)
        for i in range(4):
            idx = row + i; name, key = debt_items[idx]
            with cols[i]:
                st.markdown(f"{name} (만원)", unsafe_allow_html=True)
                st.number_input(name, value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, label_visibility="collapsed", step=1, format="%d")

    # --- 6. 보유 인증 (복구) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("6. 보유 인증")
    cert_list = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4):
            if i+j < len(cert_list): 
                cols[j].checkbox(cert_list[i+j], key=f"in_cert_{i+j}", value=st.session_state.get(f"in_cert_{i+j}", False))

    # --- 7. 특허 및 정부지원 (복구) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("7. 특허 및 정부지원")
    c7 = st.columns(2)
    with c7[0]:
        st.radio("특허 보유 여부", ["무", "유"], horizontal=True, key="in_has_patent")
        st.number_input("특허 보유 건수", value=st.session_state.get("in_pat_cnt", None), key="in_pat_cnt", step=1, format="%d")
        st.text_area("특허 명칭 및 상세", key="in_pat_desc", value=st.session_state.get("in_pat_desc", ""))
    with c7[1]:
        st.radio("정부지원 수혜이력", ["무", "유"], horizontal=True, key="in_has_gov")
        st.number_input("수혜 건수", value=st.session_state.get("in_gov_cnt", None), key="in_gov_cnt", step=1, format="%d")
        st.text_area("수혜 사업명 상세", key="in_gov_desc", value=st.session_state.get("in_gov_desc", ""))

    # --- 8. 비즈니스 상세 정보 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("8. 비즈니스 상세 정보")
    
    if st.sidebar.button("🪄 AI 비즈니스 정보 초안 생성"):
        if not st.session_state.get("in_item_desc"): st.warning("핵심 아이템을 입력하세요.")
        elif not st.session_state.get("api_key"): st.error("API Key를 저장하세요.")
        else:
            with st.spinner("AI가 전략을 구상 중입니다..."):
                try:
                    model = genai.GenerativeModel(get_best_model_name())
                    fill_prompt = f"아이템: {st.session_state['in_item_desc']}에 대해 차별성, 공정도, 시장현황, 타겟고객, 수익모델, 판매루트, 앞으로의계획을 JSON 형식으로 작성하라."
                    response = model.generate_content(fill_prompt)
                    cleaned_txt = response.text.strip().replace("```json", "").replace("```", "")
                    res_json = json.loads(cleaned_txt)
                    st.session_state["in_item_diff"] = res_json.get('차별성', '')
                    st.session_state["in_market_status"] = res_json.get('시장현황', '')
                    st.session_state["in_revenue_model"] = res_json.get('수익모델', '')
                    st.session_state["in_sales_route"] = res_json.get('판매루트', '')
                    st.session_state["in_process_desc"] = res_json.get('공정도', '')
                    st.session_state["in_target_cust"] = res_json.get('타겟고객', '')
                    st.session_state["in_future_plan"] = res_json.get('앞으로의계획', '')
                    st.rerun()
                except: st.error("AI 초안 생성 실패.")

    c8_top = st.columns(2)
    with c8_top[0]: st.text_area("핵심 아이템", key="in_item_desc", height=100)
    with c8_top[1]: st.text_area("판매 루트(유통망)", key="in_sales_route", height=100)
    c8_1, c8_2 = st.columns(2)
    with c8_1:
        st.text_area("경쟁력 및 차별성", key="in_item_diff")
        st.text_area("시장 현황", key="in_market_status")
        st.text_area("수익 모델", key="in_revenue_model")
    with c8_2:
        st.text_area("제품생산/서비스 공정도", key="in_process_desc")
        st.text_area("구체적인 타겟 고객", key="in_target_cust")
        st.text_area("앞으로의 계획", key="in_future_plan")

    # --- 9. 자금 계획 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-label">이번 조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", value=st.session_state.get("in_req_funds", None), key="in_req_funds", placeholder=GUIDE_STR, step=1, format="%d", label_visibility="collapsed")
    with c9[1]:
        st.markdown('상세 자금 집행 계획', unsafe_allow_html=True)
        st.text_area("자금집행", key="in_fund_plan", placeholder="예: 연구인력 채용(40%), 시제품 제작(30%), 마케팅 집행(30%) 등", label_visibility="collapsed")

    st.success("✅ [수정 완료] 태그 오류 해결 및 6, 7번 항목이 정상 복구되었습니다.")

# ==========================================
# 3. 리포트 출력
# ==========================================
else:
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    d = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    cn = d.get('in_company_name', '미입력').strip()
    
    st.subheader(f"📊 {cn} 분석 리포트")
    with st.status("🚀 분석 진행 중..."):
        model = genai.GenerativeModel(get_best_model_name())
        res = model.generate_content(f"기업 정보: {d} 를 바탕으로 리포트를 HTML로 작성하라.").text
    st.markdown(clean_html(res), unsafe_allow_html=True)
