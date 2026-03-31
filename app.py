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
    /* 1. 일반 위젯 라벨 설정 (표준 14px) */
    [data-testid="stWidgetLabel"] p {
        font-weight: 400 !important;
        font-size: 14px !important;
        color: #31333F !important;
        margin-bottom: 5px !important;
    }
    /* 2. 섹션 헤더 스타일 */
    h2 { font-weight: 700 !important; margin-top: 25px !important; }
    
    /* 3. 입력창 내부 Placeholder(흐릿한 글씨) 크기 조절 */
    input::placeholder {
        font-size: 0.8em !important;
        color: #888 !important;
    }
    
    /* 4. 숫자 입력창 우측 증감 버튼 제거 */
    input::-webkit-outer-spin-button,
    input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    
    /* 5. 6번 보유인증 폰트 설정 (15px) */
    [data-testid="stCheckbox"] label p {
        font-size: 15px !important;
        font-weight: 450 !important;
    }

    /* 6. 9번 섹션 강조 라벨: 16px + 볼드 + 파란색 */
    .blue-bold-label-16 {
        color: #1E88E5 !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        display: inline-block;
        margin-bottom: 12px !important;
    }
    
    /* 7. 상세 자금 집행 계획 라벨 높이 조정용 */
    .std-label-14 {
        font-size: 14px !important;
        font-weight: 400 !important;
        display: inline-block;
        margin-bottom: 12px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 헬퍼 함수 ---
def safe_int(value):
    try:
        if value is None or value == "": return 0
        clean_val = str(value).replace(',', '').strip()
        return int(float(clean_val))
    except: return 0

def clean_html(text):
    if not text: return ""
    cleaned = text.replace("```html", "").replace("```", "").replace("```json", "").strip()
    return cleaned

def get_best_model_name():
    return 'gemini-1.5-flash'

# --- 신용 등급 판정 로직 ---
def get_kcb_info(score):
    s = safe_int(score)
    if s >= 942: return "1등급", "#43A047"
    elif s >= 891: return "2등급", "#43A047"
    elif s >= 832: return "3등급", "#43A047"
    elif s >= 768: return "4등급", "#FB8C00"
    elif s >= 698: return "5등급", "#FB8C00"
    elif s >= 630: return "6등급", "#FB8C00"
    elif s >= 530: return "7등급", "#E53935"
    elif s >= 454: return "8등급", "#E53935"
    elif s >= 335: return "9등급", "#E53935"
    else: return "10등급", "#E53935"

def get_nice_info(score):
    s = safe_int(score)
    if s >= 900: return "1등급", "#1E88E5"
    elif s >= 870: return "2등급", "#1E88E5"
    elif s >= 840: return "3등급", "#43A047"
    elif s >= 805: return "4등급", "#43A047"
    elif s >= 750: return "5등급", "#FB8C00"
    elif s >= 665: return "6등급", "#FB8C00"
    elif s >= 600: return "7등급", "#E53935"
    elif s >= 515: return "8등급", "#E53935"
    elif s >= 445: return "9등급", "#E53935"
    else: return "10등급", "#E53935"

def create_gauge(score, title, color):
    val = safe_int(score)
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = val,
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
# 1. 초기화 및 세션 관리
# ==========================================
DB_FILE = "company_db.json"
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(data): json.dump(data, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

# ---------------- 사이드바 ----------------
st.sidebar.header("⚙️ AI 엔진 설정")

if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")

if st.sidebar.button("💾 API KEY 저장"):
    st.session_state["api_key"] = api_key_input
    st.sidebar.success("✅ 키가 저장되었습니다.")
    time.sleep(0.5)
    st.rerun()

if st.session_state["api_key"]:
    genai.configure(api_key=st.session_state["api_key"])
else:
    st.sidebar.warning("🔑 API Key를 입력해주세요.")

st.sidebar.markdown("---")
st.sidebar.header("📂 업체 관리")
db = load_db()
selected_company = st.sidebar.selectbox("불러올 업체 선택", ["선택 안 함"] + list(db.keys()))

sb_col1, sb_col2 = st.sidebar.columns(2)
with sb_col1:
    if st.button("📂 불러오기", use_container_width=True):
        if selected_company != "선택 안 함":
            for k, v in db[selected_company].items(): st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"; st.rerun()
with sb_col2:
    if st.button("💾 정보 저장", use_container_width=True):
        cn = st.session_state.get("in_company_name", "").strip()
        if cn:
            db[cn] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            save_db(db); st.sidebar.success("저장 완료!")

# [해결] 초기화 시 에러 방지 로직 포함
if st.sidebar.button("🧹 전체 데이터 초기화", use_container_width=True):
    for key in list(st.session_state.keys()):
        if key.startswith("in_") or key == "view_mode":
            del st.session_state[key]
    st.session_state["view_mode"] = "INPUT"
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")
if st.sidebar.button("📊 AI 기업분석리포트"): st.session_state["view_mode"] = "REPORT"; st.rerun()
if st.sidebar.button("💡 AI 정책자금 매칭"): st.session_state["view_mode"] = "MATCHING"; st.rerun()
if st.sidebar.button("📝 AI 사업계획서"): st.session_state["view_mode"] = "PLAN"; st.rerun()

# ==========================================
# 2. 메인 대시보드
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
with t_cols[0]: 
    if st.button("📊 AI기업분석리포트", use_container_width=True, type="primary", key="main_btn_1"): st.session_state["view_mode"] = "REPORT"; st.rerun()
with t_cols[1]: 
    if st.button("💡 AI 정책자금 매칭", use_container_width=True, type="primary", key="main_btn_2"): st.session_state["view_mode"] = "MATCHING"; st.rerun()
with t_cols[2]: 
    if st.button("📝 AI 사업계획서", use_container_width=True, type="primary", key="main_btn_3"): st.session_state["view_mode"] = "PLAN"; st.rerun()
with t_cols[3]: 
    if st.button("📑 화면 리프레시", use_container_width=True, key="main_btn_4"): st.rerun()
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
    with c1r3[0]: st.text_input("사업장 전화번호", placeholder="000-00-00000", key="in_biz_tel")
    with c1r3[1]: st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c1r3[2]: st.number_input("보증금 (만원)", value=st.session_state.get("in_lease_deposit", None), key="in_lease_deposit", placeholder=GUIDE_STR, step=1, format="%d")
    with c1r3[3]: st.number_input("월임대료 (만원)", value=st.session_state.get("in_lease_rent", None), key="in_lease_rent", placeholder=GUIDE_STR, step=1, format="%d")
    st.markdown("---")

    # --- 2. 대표자 정보 ---
    st.header("2. 대표자 정보")
    c2r1 = st.columns(4)
    with c2r1[0]: st.text_input("대표자명", key="in_rep_name")
    with c2r1[1]: st.text_input("생년월일", placeholder="YYYY.MM.DD", key="in_rep_dob")
    with c2r1[2]: st.text_input("연락처", placeholder="010-0000-0000", key="in_rep_phone")
    with c2r1[3]: st.selectbox("최종학력", ["선택", "중학교 졸업", "고등학교 졸업", "대학교 졸업", "석사 수료", "박사 수료"], key="in_edu_school")
    c2r2 = st.columns([1.5, 1, 1.5])
    with c2r2[0]: st.text_input("거주지 주소", key="in_home_addr")
    with c2r2[1]: st.radio("거주지 임대여부", ["자가", "임대"], horizontal=True, key="in_home_status")
    with c2r2[2]: st.multiselect("부동산 보유현황", ["아파트", "빌라", "토지", "공장", "임야"], key="in_real_estate")
    st.markdown("---")

    # --- 3. 대표자 신용정보 (TypeError 방지 완료) ---
    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.1, 1.2, 1.8])
    with c3_col1:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t1 = st.columns(2); t1[0].markdown("금융연체 여부"); t1[1].markdown("세금체납 여부")
        r1 = st.columns(2); delinquency = r1[0].radio("f_d", ["무", "유"], horizontal=True, key="in_fin_delinquency", label_visibility="collapsed")
        tax_delin = r1[1].radio("t_d", ["무", "유"], horizontal=True, key="in_tax_delinquency", label_visibility="collapsed")
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t2 = st.columns(2); t2[0].markdown("KCB 점수"); t2[1].markdown("NICE 점수")
        r2 = st.columns(2)
        s_kcb = r2[0].number_input("k_i", value=st.session_state.get("in_kcb_score", None), key="in_kcb_score", label_visibility="collapsed", placeholder="점수", step=1, format="%d")
        s_nice = r2[1].number_input("n_i", value=st.session_state.get("in_nice_score", None), key="in_nice_score", label_visibility="collapsed", placeholder="점수", step=1, format="%d")
    with c3_col2:
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        
        # [수정] TypeError 방지용 안전한 값 변환
        val_kcb = safe_int(s_kcb)
        val_nice = safe_int(s_nice)
        
        has_issue = (delinquency == "유" or tax_delin == "유")
        # 비어있는 값이 아닌 실제 입력값이 기준치 미만인 경우만 체크
        low_score = (val_kcb > 0 and val_kcb < 630) or (val_nice > 0 and val_nice < 665)
        
        if has_issue:
            status_text = "🔴 진행 불가 (위험)"
            comment_text = "연체 또는 체납 정보가 확인됩니다. 해당 사항 해결 전까지는 대부분의 정책자금 신청이 제한될 수 있습니다."
            bg_color = "#FFEBEE"
        elif low_score:
            status_text = "🟡 진행 검토 필요 (주의)"
            comment_text = "신용 점수가 다소 낮습니다. 보증서 발급 시 추가 담보 요구나 한도 제한이 있을 수 있으니 정밀 검토가 필요합니다."
            bg_color = "#FFF3E0"
        elif val_kcb == 0 and val_nice == 0:
            status_text = "⚪ 정보 입력 대기"
            comment_text = "신용 정보를 입력하시면 즉시 금융 상태를 진단해 드립니다."
            bg_color = "#F8F9FA"
        else:
            status_text = "🟢 진행 원활 (양호)"
            comment_text = "금융 이력 및 신용 점수가 양호합니다. 매출액 및 고용 현황에 따라 원활한 자금 조달이 가능할 것으로 보입니다."
            bg_color = "#E8F5E9"

        st.markdown(f"""
            <div style='background-color:{bg_color}; padding:20px; border-radius:10px; height:185px;'>
                <p style='font-weight:700; margin-bottom:10px;'>금융 상태 요약</p>
                <p style='font-size:1.1em; font-weight:700; color:#333;'>{status_text}</p>
                <p style='font-size:0.9em; line-height:1.4;'>{comment_text}</p>
            </div>
        """, unsafe_allow_html=True)

    with c3_col3:
        # 게이지 역시 safe_int 처리된 값 사용
        v_cols = st.columns(2); k_grade, k_color = get_kcb_info(val_kcb); n_grade, n_color = get_nice_info(val_nice)
        with v_cols[0]: 
            st.plotly_chart(create_gauge(val_kcb, "KCB Score", k_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:5px; background-color:{k_color}; color:white; border-radius:5px; font-size:0.9em; margin-top:-15px;'>KCB: {k_grade}</div>", unsafe_allow_html=True)
        with v_cols[1]: 
            st.plotly_chart(create_gauge(val_nice, "NICE Score", n_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:5px; background-color:{n_color}; color:white; border-radius:5px; font-size:0.9em; margin-top:-15px;'>NICE: {n_grade}</div>", unsafe_allow_html=True)
    st.markdown("---")

    # --- 4. 매출현황 ---
    st.header("4. 매출현황")
    exp_r = st.columns([1, 1, 2])
    with exp_r[0]: has_export = st.radio("수출매출 여부", ["무", "유"], horizontal=True, key="in_export_revenue")
    with exp_r[1]: plan_export = st.radio("수출예정 여부", ["무", "유"], horizontal=True, key="in_planned_export")
    
    mc = st.columns(4)
    m_titles = [("금년 매출 (만원)", "in_sales_cur"), ("25년 매출 (만원)", "in_sales_25"), ("24년 매출 (만원)", "in_sales_24"), ("23년 매출 (만원)", "in_sales_23")]
    for i, (title, key) in enumerate(m_titles):
        mc[i].number_input(title, value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, step=1, format="%d")
    
    if has_export == "유":
        st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
        ec = st.columns(4)
        e_titles = [("금년 수출 (만원)", "in_exp_cur"), ("25년 수출 (만원)", "in_exp_25"), ("24년 수출 (만원)", "in_exp_24"), ("23년 수출 (만원)", "in_exp_23")]
        for i, (title, key) in enumerate(e_titles):
            ec[i].number_input(title, value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, step=1, format="%d")
    st.markdown("---")

    # --- 5. 기대출 현황 ---
    st.header("5. 기대출 현황")
    debt_items = [("중진공 (만원)", "in_debt_kosme"), ("소진공 (만원)", "in_debt_semas"), ("신보 (만원)", "in_debt_kodit"), ("기보 (만원)", "in_debt_kibo"), ("재단 (만원)", "in_debt_foundation"), ("회사담보 (만원)", "in_debt_corp_coll"), ("대표신용 (만원)", "in_debt_rep_cred"), ("대표담보 (만원)", "in_debt_rep_coll")]
    for row in range(0, 8, 4):
        cols = st.columns(4)
        for i in range(4):
            idx = row + i; title, key = debt_items[idx]
            cols[i].number_input(title, value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, step=1, format="%d")
    st.markdown("---")

    # --- 6. 보유 인증 ---
    st.header("6. 보유 인증")
    cert_list = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4):
            if i+j < len(cert_list): cols[j].checkbox(cert_list[i+j], key=f"in_cert_{i+j}")
    st.markdown("---")

    # --- 7. 특허 및 정부지원 ---
    st.header("7. 특허 및 정부지원")
    c7 = st.columns(2)
    with c7[0]:
        st.radio("특허 보유 여부", ["무", "유"], horizontal=True, key="in_has_patent")
        st.number_input("보유 건수", value=st.session_state.get("in_pat_cnt", None), key="in_pat_cnt", step=1, format="%d")
        st.text_area("특허 상세 내용", key="in_pat_desc")
    with c7[1]:
        st.radio("정부지원 수혜이력", ["무", "유"], horizontal=True, key="in_has_gov")
        st.number_input("수혜 건수", value=st.session_state.get("in_gov_cnt", None), key="in_gov_cnt", step=1, format="%d")
        st.text_area("수혜 사업명 상세", key="in_gov_desc")
    st.markdown("---")

    # --- 8. 비즈니스 상세 정보 ---
    st.header("8. 비즈니스 상세 정보")
    row1 = st.columns(2)
    with row1[0]: st.text_area("핵심 아이템", key="in_item_desc", height=100)
    with row1[1]: st.text_area("판매 루트(유통망)", key="in_sales_route", height=100)
    row2 = st.columns(2)
    with row2[0]: st.text_area("경쟁력 및 차별성", key="in_item_diff")
    with row2[1]: st.text_area("시장 현황", key="in_market_status")
    row3 = st.columns(2)
    with row3[0]: st.text_area("제품생산/서비스 공정도", key="in_process_desc")
    with row3[1]: st.text_area("구체적인 타겟 고객", key="in_target_cust")
    row4 = st.columns(2)
    with row4[0]: st.text_area("수익 모델", key="in_revenue_model")
    with row4[1]: st.text_area("앞으로의 계획", key="in_future_plan")
    st.markdown("---")

    # --- 9. 자금 계획 (수평 상단 정렬 및 16px) ---
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-bold-label-16">이번 조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", value=st.session_state.get("in_req_funds", None), key="in_req_funds", placeholder=GUIDE_STR, step=1, format="%d", label_visibility="collapsed")
    with c9[1]:
        st.markdown('<p class="std-label-14">상세 자금 집행 계획</p>', unsafe_allow_html=True)
        st.text_area("자금집행", key="in_fund_plan", placeholder="예: 연구인력 채용(40%), 시제품 제작(30%), 마케팅 집행(30%) 등", label_visibility="collapsed")

# ==========================================
# 3. 리포트 출력
# ==========================================
else:
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    d = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    cn = d.get('in_company_name', '미입력').strip()
    st.subheader(f"📊 {cn} 분석 리포트")
    with st.status("🚀 분석 진행 중..."):
        if not st.session_state.get("api_key"): st.error("사이드바에서 API Key를 먼저 저장하세요.")
        else:
            try:
                model = genai.GenerativeModel(get_best_model_name())
                res = model.generate_content(f"기업 정보: {d} 를 바탕으로 전문적인 리포트를 작성하라.").text
                st.markdown(clean_html(res), unsafe_allow_html=True)
            except Exception as e:
                st.error(f"리포트 생성 중 오류가 발생했습니다: {e}")
