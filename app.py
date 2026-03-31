import streamlit as st
import json
import os
import time
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go

# [리포트 엔진 연결]
import engine_analysis
import engine_matching
import engine_loan
import engine_ai_plan

# ==========================================
# 0. 핵심 설정 및 디자인 커스텀 (CSS)
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    /* 1. 일반 위젯 라벨 설정 */
    [data-testid="stWidgetLabel"] p {
        font-weight: 400 !important;
        font-size: 14px !important;
        color: #31333F !important;
        margin-bottom: 2px !important;
    }
    /* 2. 섹션 헤더 스타일 */
    h2 { font-weight: 700 !important; margin-top: 25px !important; }
    
    /* 3. 숫자 입력창 우측 버튼 제거 */
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    
    /* 4. 라디오 버튼 폭 조정 */
    div[data-testid="stHorizontalRadio"] div[role="radiogroup"] > label {
        min-width: 85px !important; 
        margin-right: 0px !important;
    }

    /* 5. 3번 섹션 - 바닥 라인 맞춤 박스 스타일 (높이 145px 고정) */
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

    /* 6. 보유인증 탭 체크박스 폰트 (16px) */
    [data-testid="stCheckbox"] label p {
        font-size: 16px !important;
        font-weight: 450 !important;
    }

    /* 7. 9번 섹션 강조 라벨 */
    .blue-bold-label-16 {
        color: #1E88E5 !important; font-size: 16px !important; font-weight: 700 !important;
        display: inline-block; margin-bottom: 12px !important;
    }
    
    /* 8. Placeholder(예시문) 색상 및 크기 조정 */
    input::placeholder, textarea::placeholder {
        color: #aaa !important;
        font-size: 0.85em !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 헬퍼 함수 ---
def safe_int(value):
    try:
        if value is None or value == "": return 0
        return int(float(str(value).replace(',', '').strip()))
    except: return 0

# 신용 등급 판정 로직
def get_kcb_grade(score):
    s = safe_int(score)
    if s >= 942: return "1등급", "#43A047"
    elif s >= 891: return "2등급", "#43A047"
    elif s >= 832: return "3등급", "#66BB6A"
    elif s >= 768: return "4등급", "#FFA726"
    elif s >= 698: return "5등급", "#FB8C00"
    elif s >= 630: return "6등급", "#EF6C00"
    elif s >= 530: return "7등급", "#E64A19"
    elif s >= 454: return "8등급", "#D84315"
    elif s >= 335: return "9등급", "#BF360C"
    else: return "10등급", "#E53935"

def get_nice_grade(score):
    s = safe_int(score)
    if s >= 900: return "1등급", "#1E88E5"
    elif s >= 870: return "2등급", "#1E88E5"
    elif s >= 840: return "3등급", "#42A5F5"
    elif s >= 805: return "4등급", "#FFA726"
    elif s >= 750: return "5등급", "#FB8C00"
    elif s >= 665: return "6등급", "#EF6C00"
    elif s >= 600: return "7등급", "#E64A19"
    elif s >= 515: return "8등급", "#D84315"
    elif s >= 445: return "9등급", "#BF360C"
    else: return "10등급", "#E53935"

# ==========================================
# 1. 상태 관리 및 사이드바
# ==========================================
DB_FILE = "company_db.json"
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(data): json.dump(data, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "api_key" not in st.session_state: st.session_state["api_key"] = ""

st.sidebar.header("⚙️ AI 엔진 설정")
api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password", placeholder="API Key를 입력하세요")
if st.sidebar.button("💾 API KEY 저장", use_container_width=True):
    st.session_state["api_key"] = api_key_input; st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📂 업체 관리")
db = load_db()
selected_company = st.sidebar.selectbox("불러올 업체 선택", ["선택 안 함"] + list(db.keys()))
if st.sidebar.button("📂 불러오기", use_container_width=True):
    if selected_company != "선택 안 함":
        for k, v in db[selected_company].items(): st.session_state[k] = v
        st.rerun()

if st.sidebar.button("💾 정보 저장", use_container_width=True):
    name = st.session_state.get("in_company_name", "").strip()
    if name:
        current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        db[name] = current_data; save_db(db); st.sidebar.success("저장 완료!")

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")
if st.sidebar.button("📊 AI 기업분석리포트", use_container_width=True): st.session_state["view_mode"] = "REPORT"; st.rerun()
if st.sidebar.button("💡 AI 정책자금 매칭", use_container_width=True): st.session_state["view_mode"] = "MATCHING"; st.rerun()
if st.sidebar.button("📝 기관별 융자/사업계획서", use_container_width=True): st.session_state["view_mode"] = "LOAN_PLAN"; st.rerun()
if st.sidebar.button("📑 AI 사업계획서", use_container_width=True): st.session_state["view_mode"] = "AI_PLAN"; st.rerun()

# ==========================================
# 2. 메인 대시보드
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 ---
    st.header("1. 기업현황")
    c1r1 = st.columns([2, 1, 1.5, 1.5])
    with c1r1[0]: st.text_input("기업명", key="in_company_name", placeholder="업체명을 입력하세요")
    with c1r1[1]: st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1r1[2]: st.text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    with c1r1[3]: st.text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")
    
    c1r2 = st.columns([1, 2.5, 1.5])
    with c1r2[0]: st.text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD")
    with c1r2[1]: st.text_input("사업장 주소", key="in_biz_addr", placeholder="사업장 소재지를 입력하세요")
    with c1r2[2]: st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
    
    c1r3 = st.columns([1, 1, 1, 1])
    with c1r3[0]: st.text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-0000-0000")
    with c1r3[1]: st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c1r3[2]: st.number_input("보증금 (만원)", key="in_lease_deposit", step=1, placeholder=GUIDE_STR)
    with c1r3[3]: st.number_input("월임대료 (만원)", key="in_lease_rent", step=1, placeholder=GUIDE_STR)
    
    c1r4 = st.columns([1, 1, 2])
    with c1r4[0]: st.text_input("이메일 주소", key="in_email_addr", placeholder="example@email.com")
    with c1r4[1]: st.radio("추가 사업장 여부", ["없음", "있음"], horizontal=True, key="in_has_extra_biz")
    with c1r4[2]: st.text_input("추가사업장 정보입력", key="in_extra_biz_info", placeholder="사업장명/사업자등록번호 기재")
    st.markdown("---")

    # --- 2. 대표자 정보 ---
    st.header("2. 대표자 정보")
    c2r1 = st.columns([1, 1, 1, 1])
    with c2r1[0]: st.text_input("대표자명", key="in_rep_name", placeholder="성명을 입력하세요")
    with c2r1[1]: st.text_input("생년월일", key="in_rep_dob", placeholder="YYYY.MM.DD")
    with c2r1[2]: st.text_input("연락처", key="in_rep_phone", placeholder="010-0000-0000")
    with c2r1[3]: st.selectbox("통신사", ["선택", "SKT", "KT", "LGU+", "알뜰폰"], key="in_rep_carrier")
    
    c2r2 = st.columns([2, 1, 1]) 
    with c2r2[0]: st.text_input("거주지 주소", key="in_home_addr", placeholder="현재 거주지를 입력하세요")
    with c2r2[1]: st.radio("거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status")
    with c2r2[2]: st.multiselect("부동산 보유현황", ["아파트", "빌라", "토지", "공장", "임야"], key="in_real_estate")
    
    c2r3 = st.columns([0.8, 0.8, 1.2, 1.2]) 
    with c2r3[0]: st.selectbox("최종학력", ["선택", "중졸", "고졸", "대졸", "석사", "박사"], key="in_edu_level")
    with c2r3[1]: st.text_input("전공", key="in_rep_major", placeholder="전공명 입력")
    with c2r3[2]: st.text_input("경력사항 1", key="in_rep_career_1", placeholder="주요 경력 기재")
    with c2r3[3]: st.text_input("경력사항 2", key="in_rep_career_2", placeholder="기타 경력 기재")
    st.markdown("---")

    # --- 3. 대표자 신용정보 (정렬 및 결과박스 유지) ---
    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.5, 1.3, 1.8])
    
    with c3_col1:
        l_r1_c1, l_r1_c2 = st.columns(2)
        with l_r1_c1: delinquency = st.radio("금융연체여부", ["없음", "있음"], horizontal=True, key="in_fin_delinquency")
        with l_r1_c2: tax_delin = st.radio("세금체납여부", ["없음", "있음"], horizontal=True, key="in_tax_delinquency")
        
        st.markdown("<div style='margin-top:25px;'></div>", unsafe_allow_html=True)
        
        l_r2_c1, l_r2_c2 = st.columns(2)
        with l_r2_c1: s_kcb = st.number_input("KCB 점수", value=st.session_state.get("in_kcb_score", 0), key="in_kcb_score", step=1, placeholder="0~1000")
        with l_r2_c2: s_nice = st.number_input("NICE 점수", value=st.session_state.get("in_nice_score", 0), key="in_nice_score", step=1, placeholder="0~1000")

    with c3_col2:
        vk, vn = safe_int(s_kcb), safe_int(s_nice)
        has_issue = (delinquency == "있음" or tax_delin == "있음")
        if has_issue: status, color, text = "🔴 진행 불가", "#FFEBEE", "연체 기록 확인 필수"
        elif (vk > 0 and vk < 630) or (vn > 0 and vn < 665): status, color, text = "🟡 진행 주의", "#FFF3E0", "신용 보완 권장"
        elif vk == 0: status, color, text = "⚪ 정보 대기", "#F8F9FA", "점수를 입력하세요"
        else: status, color, text = "🟢 진행 원활", "#E8F5E9", "양호한 신용 상태"
        
        st.markdown(f"""
            <div class="summary-box-compact">
                <p style='font-weight:700; color:#555; font-size:0.95em; margin-bottom:5px;'>신용상태요약</p>
                <p style='font-size:1.45em; font-weight:800; color:#333; margin-bottom:5px;'>{status}</p>
                <p style='font-size:0.85em; color:#666;'>{text}</p>
            </div>
        """, unsafe_allow_html=True)

    with c3_col3:
        res_c1, res_c2 = st.columns(2)
        kg, kc = get_kcb_grade(vk); ng, nc = get_nice_grade(vn)
        with res_c1:
            st.markdown(f"""
                <div class="score-result-box">
                    <p class="result-title">KCB 결과</p>
                    <p style='font-size:1.8em; font-weight:800; color:{kc}; margin:5px 0;'>{vk}점</p>
                    <p style='font-weight:700; color:#333; font-size:1.15em;'>{kg}</p>
                </div>
            """, unsafe_allow_html=True)
        with res_c2:
            st.markdown(f"""
                <div class="score-result-box">
                    <p class="result-title">NICE 결과</p>
                    <p style='font-size:1.8em; font-weight:800; color:{nc}; margin:5px 0;'>{vn}점</p>
                    <p style='font-weight:700; color:#333; font-size:1.15em;'>{ng}</p>
                </div>
            """, unsafe_allow_html=True)
    st.markdown("---")

    # --- 4. 매출현황 (수출 복구 및 예시문 추가) ---
    st.header("4. 매출현황")
    exp_c1, exp_c2 = st.columns([1, 1])
    with exp_c1: has_exp = st.radio("수출매출 여부", ["없음", "있음"], horizontal=True, key="in_export_revenue")
    with exp_c2: plan_exp = st.radio("수출예정 여부", ["없음", "있음"], horizontal=True, key="in_planned_export")
    
    mc = st.columns(4)
    m_keys = [("금년 매출", "in_sales_cur"), ("25년 매출", "in_sales_25"), ("24년 매출", "in_sales_24"), ("23년 매출", "in_sales_23")]
    for i, (t, k) in enumerate(m_keys):
        mc[i].number_input(f"{t} (만원)", value=st.session_state.get(k, 0), key=k, step=1, placeholder=GUIDE_STR)
    
    if has_exp == "있음":
        st.markdown("<p style='font-size:14px; font-weight:600; margin-top:10px;'>[수출매출 상세역사]</p>", unsafe_allow_html=True)
        ec = st.columns(4)
        e_keys = [("금년 수출액", "in_exp_cur"), ("25년 수출액", "in_exp_25"), ("24년 수출액", "in_exp_24"), ("23년 수출액", "in_exp_23")]
        for i, (t, k) in enumerate(e_keys):
            ec[i].number_input(f"{t} (만원)", value=st.session_state.get(k, 0), key=k, step=1, placeholder=GUIDE_STR)
    st.markdown("---")

    # --- 5. 부채현황 ---
    st.header("5. 부채현황")
    debt_items = [("중진공", "in_debt_kosme"), ("소진공", "in_debt_semas"), ("신보", "in_debt_kodit"), ("기보", "in_debt_kibo"), ("재단", "in_debt_foundation"), ("회사담보", "in_debt_corp_coll"), ("대표신용", "in_debt_rep_cred"), ("대표담보", "in_debt_rep_coll")]
    for r in range(0, 8, 4):
        cols = st.columns(4)
        for i in range(4): cols[i].number_input(f"{debt_items[r+i][0]} (만원)", key=debt_items[r+i][1], step=1, placeholder=GUIDE_STR)
    st.markdown("---")

    # --- 6. 보유 인증 ---
    st.header("6. 보유 인증")
    cert_list = ["중소기업확인서(소상공인확인서)", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4):
            if i+j < len(cert_list): cols[j].checkbox(cert_list[i+j], key=f"in_cert_{i+j}")
    st.markdown("---")

    # --- 7. 특허 및 정부지원 ---
    st.header("7. 특허 및 정부지원")
    c7 = st.columns(2)
    with c7[0]:
        st.radio("특허 보유 여부", ["없음", "있음"], horizontal=True, key="in_has_patent")
        st.number_input("보유 건수", key="in_pat_cnt", step=1, placeholder="0"); st.text_area("특허 상세 내용", key="in_pat_desc", placeholder="보유하신 특허의 명칭 및 주요 내용을 입력하세요")
    with c7[1]:
        st.radio("정부지원 수혜이력", ["없음", "있음"], horizontal=True, key="in_has_gov")
        st.number_input("수혜 건수", key="in_gov_cnt", step=1, placeholder="0"); st.text_area("수혜 사업명 상세", key="in_gov_desc", placeholder="과거에 선정되었던 정부지원 사업명을 입력하세요")
    st.markdown("---")

    # --- 8. 비즈니스 상세 정보 ---
    st.header("8. 비즈니스 상세 정보")
    r8_1 = st.columns(2); r8_1[0].text_area("핵심 아이템", key="in_item_desc", height=100, placeholder="제품이나 서비스의 핵심 기능을 설명하세요"); r8_1[1].text_area("판매 루트(유통망)", key="in_sales_route", height=100, placeholder="주요 거래처나 판매 채널을 입력하세요")
    r8_2 = st.columns(2); r8_2[0].text_area("경쟁력 및 차별성", key="in_item_diff", height=100, placeholder="타사 대비 강점을 입력하세요"); r8_2[1].text_area("시장 현황", key="in_market_status", height=100, placeholder="현재 업계 분위기나 시장 규모를 입력하세요")
    r8_3 = st.columns(2); r8_3[0].text_area("공정도", key="in_process_desc", height=100, placeholder="제품 생산이나 서비스 제공 과정을 요약하세요"); r8_3[1].text_area("타겟 고객", key="in_target_cust", height=100, placeholder="주요 구매층을 입력하세요")
    r8_4 = st.columns(2); r8_4[0].text_area("수익 모델", key="in_revenue_model", height=100, placeholder="매출이 발생하는 구조를 입력하세요"); r8_4[1].text_area("앞으로의 계획", key="in_future_plan", height=100, placeholder="향후 1~3년 내의 비즈니스 목표를 입력하세요")
    st.markdown("---")

    # --- 9. 자금 계획 ---
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-bold-label-16">이번 조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", key="in_req_funds", label_visibility="collapsed", step=1, placeholder=GUIDE_STR)
    with c9[1]:
        st.markdown('<p style="font-size:14px;">상세 자금 집행 계획</p>', unsafe_allow_html=True)
        st.text_area("자금집행", key="in_fund_plan", placeholder="예: 연구인력 채용(40%), 시제품 제작(30%), 마케팅 집행(30%) 등", label_visibility="collapsed")

# ==========================================
# 3. 리포트 출력
# ==========================================
else:
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    mode = st.session_state["view_mode"]; v_titles = {"REPORT":"분석리포트", "MATCHING":"정책자금매칭", "LOAN_PLAN":"융자계획서", "AI_PLAN":"사업계획서"}
    st.subheader(f"📊 {current_data.get('in_company_name', '미입력')} - {v_titles.get(mode)}")
    if not st.session_state.get("api_key"): st.error("사이드바에서 API Key를 먼저 저장해 주세요.")
    else:
        with st.status("🚀 AI 분석 진행 중..."):
            try:
                if mode == "REPORT": res = engine_analysis.run_report(st.session_state["api_key"], current_data)
                elif mode == "MATCHING": res = engine_matching.run_report(st.session_state["api_key"], current_data)
                elif mode == "LOAN_PLAN": res = engine_loan.run_report(st.session_state["api_key"], current_data)
                elif mode == "AI_PLAN": res = engine_ai_plan.run_report(st.session_state["api_key"], current_data)
                st.markdown(res)
            except Exception as e: st.error(f"오류: {e}")
