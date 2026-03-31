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
    [data-testid="stWidgetLabel"] p {
        font-weight: 400 !important;
        font-size: 14px !important;
        color: #31333F !important;
        margin-bottom: 2px !important;
    }
    h2 { font-weight: 700 !important; }
    input::placeholder { font-size: 0.8em !important; color: #888 !important; }
    
    .blue-label {
        color: #1E88E5 !important;
        font-size: 14px !important;
        font-weight: 400 !important;
        margin-bottom: 5px !important;
        display: inline-block;
    }
    /* 숫자 입력창 우측 버튼 숨기기 */
    input::-webkit-outer-spin-button,
    input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
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

# AI 모델명 수정 (Error 방지)
def get_best_model_name():
    return 'gemini-1.5-flash'

# --- 상세 신용 코멘트 생성 로직 ---
def get_detailed_credit_comment(kcb, nice, fin_delin, tax_delin):
    k = safe_int(kcb); n = safe_int(nice)
    if fin_delin == "유" or tax_delin == "유":
        return "⚠️ **심각한 결격사유 확인**: 현재 연체 또는 체납 정보가 확인됩니다. 이 경우 정책자금 신청 시 즉시 부결 대상이 될 수 있습니다. 자금 신청 전 반드시 해당 내역을 정리하고 해제 사실이 전산상 반영된 후 진행하시기 바랍니다."
    
    if k >= 850 and n >= 850:
        return "✅ **최우수 신용 상태**: 1금융권 대출 및 대규모 정책자금 조달에 매우 유리한 상태입니다. 기술보증기금이나 신용보증기금의 우대 금리 적용이 가능하며, 추가적인 담보 없이 대표자 신용만으로도 한도 증액이 가능합니다."
    elif k >= 700 and n >= 700:
        return "ℹ️ **보통 신용 상태**: 일반적인 정책자금 지원에는 문제가 없으나, 금리가 다소 높게 책정될 수 있습니다. NICE 점수가 KCB보다 낮을 경우 카드론이나 현금서비스 사용을 줄여 점수를 10~20점만 더 올리면 금리 인하 효과를 기대할 수 있습니다."
    else:
        return "💡 **신용 보완 필요**: 신용 점수가 다소 낮아 정책기관 심사 시 '사업성' 항목에서 훨씬 높은 점수를 받아야 합니다. 대표자 본인 명의의 자산 증빙이나 관련 업력 경력을 강력히 어필하는 전략이 필요합니다."

def get_kcb_info(score):
    s = safe_int(score)
    if s >= 942: return "1등급", "#43A047"
    if s >= 832: return "3등급", "#43A047"
    if s >= 630: return "6등급", "#FB8C00"
    return "저신용", "#E53935"

def get_nice_info(score):
    s = safe_int(score)
    if s >= 900: return "1등급", "#1E88E5"
    if s >= 840: return "3등급", "#43A047"
    if s >= 665: return "6등급", "#FB8C00"
    return "저신용", "#E53935"

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
# 1. 사이드바 및 모드 관리
# ==========================================
DB_FILE = "company_db.json"
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(data): json.dump(data, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

st.sidebar.header("⚙️ AI 엔진 설정")
if "api_key" not in st.session_state: st.session_state["api_key"] = ""
api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
if st.sidebar.button("💾 API KEY 저장"):
    st.session_state["api_key"] = api_key_input; st.sidebar.success("저장 완료!")
if st.session_state["api_key"]: genai.configure(api_key=st.session_state["api_key"])

st.sidebar.markdown("---")
st.sidebar.header("📂 업체 관리")
db = load_db()
selected_company = st.sidebar.selectbox("불러올 업체 선택", ["선택 안 함"] + list(db.keys()))
if st.sidebar.button("📂 불러오기") and selected_company != "선택 안 함":
    for k, v in db[selected_company].items(): st.session_state[k] = v
    st.session_state["view_mode"] = "INPUT"; st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🚀 빠른 리포트 생성")
if st.sidebar.button("📊 AI 기업분석리포트"): st.session_state["view_mode"] = "REPORT"; st.rerun()
if st.sidebar.button("💡 정책자금 매칭리포트"): st.session_state["view_mode"] = "MATCHING"; st.rerun()
if st.sidebar.button("📝 AI 사업계획서 생성"): st.session_state["view_mode"] = "PLAN"; st.rerun()

# ==========================================
# 2. 메인 화면
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
with t_cols[0]: 
    if st.button("📊 AI기업분석리포트", use_container_width=True, type="primary"): st.session_state["view_mode"] = "REPORT"; st.rerun()
with t_cols[1]: 
    if st.button("💡 정책자금 매칭", use_container_width=True, type="primary"): st.session_state["view_mode"] = "MATCHING"; st.rerun()
with t_cols[2]: 
    if st.button("📝 AI 사업계획서", use_container_width=True, type="primary"): st.session_state["view_mode"] = "PLAN"; st.rerun()
with t_cols[3]: 
    if st.button("💾 정보 저장", use_container_width=True):
        cn = st.session_state.get("in_company_name", "").strip()
        if cn: db[cn] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}; save_db(db); st.success("저장 완료!")

st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"
LABEL_HTML = f"<span style='font-weight:normal;'>(만원)</span>"

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
    with c1r3[2]: st.number_input(f"보증금 {LABEL_HTML}", value=st.session_state.get("in_lease_deposit", None), key="in_lease_deposit", placeholder=GUIDE_STR, step=1, format="%d")
    with c1r3[3]: st.number_input(f"월임대료 {LABEL_HTML}", value=st.session_state.get("in_lease_rent", None), key="in_lease_rent", placeholder=GUIDE_STR, step=1, format="%d")

    # --- 2. 대표자 정보 (복구 완료) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    c2r1 = st.columns(4)
    with c2r1[0]: st.text_input("대표자명", key="in_rep_name")
    with c2r1[1]: st.text_input("생년월일", placeholder="YYYY.MM.DD", key="in_rep_dob")
    with c2r1[2]: st.text_input("연락처", placeholder="010-0000-0000", key="in_rep_phone")
    with c2r1[3]: st.selectbox("최종학력", ["선택", "중학교 졸업", "고등학교 졸업", "대학교 졸업", "석사 수료", "박사 수료"], key="in_edu_school")

    c2r2 = st.columns([1, 1, 2])
    with c2r2[0]: st.radio("거주지 임대여부", ["자가", "임대"], horizontal=True, key="in_home_status")
    with c2r2[1]: st.multiselect("부동산 보유현황", ["아파트", "빌라", "토지", "공장", "임야"], key="in_real_estate")
    with c2r2[2]: st.text_input("거주지 주소", key="in_home_addr")

    # --- 3. 대표자 신용정보 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.1, 1.2, 1.8])
    with c3_col1:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t1 = st.columns(2); t1[0].markdown("금융연체 여부"); t1[1].markdown("세금체납 여부")
        r1 = st.columns(2); fin_del = r1[0].radio("f_d", ["무", "유"], horizontal=True, key="in_fin_delinquency", label_visibility="collapsed")
        tax_del = r1[1].radio("t_d", ["무", "유"], horizontal=True, key="in_tax_delinquency", label_visibility="collapsed")
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t2 = st.columns(2); t2[0].markdown("KCB 점수"); t2[1].markdown("NICE 점수")
        r2 = st.columns(2); s_kcb = r2[0].number_input("k_i", value=st.session_state.get("in_kcb_score", None), key="in_kcb_score", label_visibility="collapsed", placeholder="점수", step=1, format="%d")
        s_nice = r2[1].number_input("n_i", value=st.session_state.get("in_nice_score", None), key="in_nice_score", label_visibility="collapsed", placeholder="점수", step=1, format="%d")
    with c3_col2:
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        comment = get_detailed_credit_comment(s_kcb, s_nice, fin_del, tax_del)
        box_color = "#FFEBEE" if "⚠️" in comment else "#E8F5E9"
        st.markdown(f"""<div style='background-color: {box_color}; padding: 15px; border-radius: 10px; height: 185px; overflow-y: auto; font-size:0.95em; line-height:1.6;'>{comment}</div>""", unsafe_allow_html=True)
    with c3_col3:
        v_cols = st.columns(2); k_grade, k_color = get_kcb_info(s_kcb); n_grade, n_color = get_nice_info(s_nice)
        with v_cols[0]: st.plotly_chart(create_gauge(s_kcb, "KCB", k_color), use_container_width=True, config={'displayModeBar': False})
        with v_cols[1]: st.plotly_chart(create_gauge(s_nice, "NICE", n_color), use_container_width=True, config={'displayModeBar': False})

    # --- 4. 매출현황 (수출매출 상세 복구) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("4. 매출현황")
    exp_r = st.columns([1, 1, 2])
    with exp_r[0]: has_export = st.radio("수출매출 여부", ["무", "유"], horizontal=True, key="in_export_revenue")
    with exp_r[1]: plan_export = st.radio("수출예정 여부", ["무", "유"], horizontal=True, key="in_planned_export")
    
    m_titles = ["금년 매출합계", "25년도 매출합계", "24년도 매출합계", "23년도 매출합계"]
    m_keys = ["in_sales_cur", "in_sales_25", "in_sales_24", "in_sales_23"]
    mc = st.columns(4)
    for i, key in enumerate(m_keys): 
        mc[i].number_input(f"{m_titles[i]} {LABEL_HTML}", value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, step=1, format="%d")

    if has_export == "유":
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        e_titles = ["금년 수출실적", "25년도 수출", "24년도 수출", "23년도 수출"]
        e_keys = ["in_exp_cur", "in_exp_25", "in_exp_24", "in_exp_23"]
        ec = st.columns(4)
        for i, key in enumerate(e_keys):
            ec[i].number_input(f"{e_titles[i]} {LABEL_HTML}", value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, step=1, format="%d")

    # --- 5. 기대출 현황 (복구 완료) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("5. 기대출 현황")
    debt_items = [
        ("중진공", "in_debt_kosme"), ("소진공", "in_debt_semas"), ("신보", "in_debt_kodit"), ("기보", "in_debt_kibo"),
        ("재단", "in_debt_foundation"), ("회사담보", "in_debt_corp_coll"), ("대표신용", "in_debt_rep_cred"), ("대표담보", "in_debt_rep_coll")
    ]
    for row in range(0, 8, 4):
        cols = st.columns(4)
        for i in range(4):
            idx = row + i
            name, key = debt_items[idx]
            cols[i].number_input(f"{name} {LABEL_HTML}", value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, step=1, format="%d")

    # --- 6, 7. 인증 및 특허 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("6. 보유 인증 및 7. 특허")
    c67 = st.columns([2, 1])
    with c67[0]:
        cert_list = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤벤처인증", "뿌리기업", "ISO인증", "HACCP"]
        for i in range(0, 8, 4):
            cc = st.columns(4)
            for j in range(4): cc[j].checkbox(cert_list[i+j], key=f"in_cert_{i+j}")
    with c67[1]:
        st.radio("특허 보유", ["무", "유"], horizontal=True, key="in_has_patent")
        st.number_input("특허 건수", key="in_pat_cnt", step=1, format="%d")

    # --- 8. 비즈니스 정보 (AI 엔진 수정 완료) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("8. 비즈니스 상세 정보")
    
    if st.button("🪄 AI로 비즈니스 정보 초안 생성", type="secondary"):
        if not st.session_state.get("in_item_desc"): st.warning("먼저 '핵심 아이템' 내용을 입력해주세요.")
        elif not st.session_state.get("api_key"): st.error("API Key를 저장해주세요.")
        else:
            with st.spinner("AI가 전략적 초안을 작성 중입니다..."):
                try:
                    model = genai.GenerativeModel(get_best_model_name())
                    fill_prompt = f"아이템: {st.session_state['in_item_desc']}에 대한 사업계획서 6개 항목(차별성, 공정도, 시장현황, 타겟고객, 수익모델, 계획)을 JSON형식으로 작성하라."
                    response = model.generate_content(fill_prompt)
                    # 텍스트에서 JSON 부분만 추출하는 안전 로직
                    cleaned_txt = response.text.strip().replace("```json", "").replace("```", "")
                    res_json = json.loads(cleaned_txt)
                    st.session_state["in_item_diff"] = res_json.get('차별성', '')
                    st.session_state["in_process_desc"] = res_json.get('공정도', '')
                    st.session_state["in_market_status"] = res_json.get('시장현황', '')
                    st.session_state["in_target_cust"] = res_json.get('타겟고객', '')
                    st.session_state["in_revenue_model"] = res_json.get('수익모델', '')
                    st.session_state["in_future_plan"] = res_json.get('계획', '')
                    st.rerun()
                except Exception as e: st.error(f"AI 오류: {e}")

    st.text_area("핵심 아이템", key="in_item_desc", placeholder="제품/서비스의 정체성을 입력하세요.")
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
        st.text_area("상세 자금 집행 계획", key="in_fund_plan", placeholder="예: 연구인력 채용(40%), 마케팅 집행(30%) 등")

    st.success("✅ [수정 완료] 모든 항목 복구 및 AI 엔진 정상화가 완료되었습니다.")

# ==========================================
# 3. 리포트 출력 로직
# ==========================================
else:
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    d = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    
    if st.session_state["view_mode"] == "REPORT":
        st.subheader("📊 AI 기업 통합 분석 리포트")
        with st.status("🚀 분석 진행 중..."):
            model = genai.GenerativeModel(get_best_model_name())
            res = model.generate_content(f"다음 정보를 바탕으로 기업분석 보고서를 HTML로 작성하라: {d}").text
        st.markdown(clean_html(res), unsafe_allow_html=True)
    
    elif st.session_state["view_mode"] == "PLAN":
        st.subheader("📝 정책자금 맞춤 사업계획서")
        with st.status("🚀 계획서 초안 생성 중..."):
            model = genai.GenerativeModel(get_best_model_name())
            res = model.generate_content(f"다음 정보를 바탕으로 정책자금 통과용 사업계획서를 HTML로 작성하라: {d}").text
        st.markdown(clean_html(res), unsafe_allow_html=True)
