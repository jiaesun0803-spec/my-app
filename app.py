import streamlit as st
import streamlit.components.v1 as components
import json
import os
import time
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 0. 필수 유틸리티 함수 (최상단 배치)
# ==========================================
def safe_int(value):
    try: return int(float(str(value or "").replace(',', '').strip() or 0))
    except: return 0

def format_kr_currency(value):
    val = safe_int(value)
    if val == 0: return "0원"
    uk, man = val // 10000, val % 10000
    if uk > 0 and man > 0: return f"{uk}억 {man:,}만원"
    elif uk > 0: return f"{uk}억원"
    else: return f"{man:,}만원"

def clean_html(text): 
    return "\n".join([l.lstrip() for l in text.replace("```html", "").replace("```", "").strip().split("\n")])

def get_best_model_name():
    try:
        av = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for pref in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']:
            if pref in av: return pref
        return 'gemini-pro'
    except: return 'gemini-pro'

def get_credit_grade(sc, t="NICE"):
    sc = safe_int(sc)
    if sc == 0: return "-"
    if t == "NICE": return 1 if sc>=900 else 2 if sc>=870 else 3 if sc>=840 else 4 if sc>=805 else 5 if sc>=750 else 6 if sc>=665 else 7 if sc>=600 else 8 if sc>=515 else 9 if sc>=445 else 10
    else: return 1 if sc>=942 else 2 if sc>=891 else 3 if sc>=832 else 4 if sc>=768 else 5 if sc>=698 else 6 if sc>=630 else 7 if sc>=530 else 8 if sc>=454 else 9 if sc>=335 else 10

# --- 핵심 데이터 바인딩 클래스 ---
class VarObj: pass
def get_common_vars(d):
    v = VarObj()
    g = lambda k, df="미입력": d.get(k, df)
    v.c_name, v.rep_name, v.biz_type, v.c_ind = g('in_company_name').strip(), g('in_rep_name'), g('in_biz_type'), g('in_industry')
    v.address, v.biz_no, v.corp_no = g('in_biz_addr'), str(g('in_raw_biz_no')), str(g('in_raw_corp_no', ''))
    v.s_25, v.s_cur = format_kr_currency(g('in_sales_2025', 0)), format_kr_currency(g('in_sales_current', 0))
    v.sales_24, v.sales_23 = format_kr_currency(g('in_sales_2024', 0)), format_kr_currency(g('in_sales_2023', 0))
    v.req_fund, v.fund_type, v.fund_purpose = format_kr_currency(g('in_req_amount', 0)), g('in_fund_type', '운전자금'), g('in_fund_purpose')
    v.item, v.market, v.diff, v.route = g('in_item_desc'), g('in_market_status'), g('in_diff_point'), g('in_sales_route', '')
    v.lease_status, v.start_date_str = g('in_lease_status', '자가'), g('in_start_date', '').strip()
    v.biz_years = max(0, 2026 - int(v.start_date_str[:4])) if v.start_date_str and len(v.start_date_str)>=4 else 0
    cl = [f"{c}({g(f'in_cert_date_{i}', '일자미상')})" for i, c in enumerate(["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]) if d.get(f"in_chk_{i}")]
    v.cert_status = ", ".join(cl) if cl else "미보유"
    pl = [f"{pt} {safe_int(g(f'in_{pt}_cnt', 0))}건" for pt in ["특허출원", "특허등록", "상표등록", "디자인등록"] if g('in_has_patent') == '유' and safe_int(g(f"in_{pt}_cnt", 0)) > 0]
    v.pat_str = " ".join(pl) if pl else "특허/지재권 미보유"
    v.gov_str = f"지원사업 {safe_int(g('in_gov_cnt', 0))}건" if g('in_has_gov') == '유' and safe_int(g('in_gov_cnt', 0)) > 0 else "지원사업 이력 없음"
    v.tax_status, v.fin_status = g('in_tax_status', '무'), g('in_fin_status', '무')
    v.nice_score, v.emp_cnt = safe_int(g('in_nice_score', 0)), safe_int(g('in_employee_count', 0))
    kibo, kodit = safe_int(g('in_debt_kibo', 0)), safe_int(g('in_debt_kodit', 0))
    v.guarantee = "기보 이용중(신보 불가)" if kibo > 0 else ("신보 이용중(기보 불가)" if kodit > 0 else "신보/기보 자유선택 가능")
    v.tot_debt = format_kr_currency(sum([safe_int(g(k, 0)) for k in ['in_debt_kosme', 'in_debt_semas', 'in_debt_koreg', 'in_debt_kodit', 'in_debt_kibo', 'in_debt_etc', 'in_debt_credit', 'in_debt_coll']]))
    v.add_biz_status, v.add_biz_addr = g('in_has_additional_biz', '무'), g('in_additional_biz_addr', '').strip()
    v.val_cur, v.career, v.edu_school, v.edu_major = safe_int(g('in_sales_current', 0)), g('in_career'), g('in_edu_school', ''), g('in_edu_major', '')
    v.re_list = ", ".join(g('in_real_estate', []))
    v.email = g('in_rep_email')
    return v

# ==========================================
# 1. 보안 및 설정 로직
# ==========================================
CONFIG_FILE = "config.json"
DB_FILE = "company_db.json"

def load_config(): return json.load(open(CONFIG_FILE, "r", encoding="utf-8")) if os.path.exists(CONFIG_FILE) else {}
def save_config(d): json.dump(d, open(CONFIG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(d): json.dump(d, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 AI 컨설팅 시스템")
        pw = st.text_input("접속 비밀번호를 입력하세요", type="password")
        if st.button("접속"):
            if pw == st.secrets.get("LOGIN_PASSWORD", "1234"):
                st.session_state["password_correct"] = True
                return True
            else: st.error("비밀번호가 틀렸습니다.")
        return False
    return True

# --- 앱 실행 제어 ---
if not check_password(): st.stop()

# ==========================================
# 2. 메인 앱 화면 (로그인 후 실행)
# ==========================================

# 포맷팅 콜백 함수
def cb_format_biz_no(): st.session_state["in_raw_biz_no"] = fmt_biz(st.session_state.get("in_raw_biz_no"))
def cb_format_corp_no(): st.session_state["in_raw_corp_no"] = fmt_corp(st.session_state.get("in_raw_corp_no"))
def cb_format_date(key): st.session_state[key] = fmt_date(st.session_state.get(key))
def cb_format_phone(key): st.session_state[key] = fmt_phone(st.session_state.get(key))

def fmt_biz(val):
    v = str(val or "").replace("-", "").replace(".", "").strip()
    return f"{v[:3]}-{v[3:5]}-{v[5:]}" if len(v) == 10 else val
def fmt_corp(val):
    v = str(val or "").replace("-", "").replace(".", "").strip()
    return f"{v[:6]}-{v[6:]}" if len(v) == 13 else val
def fmt_date(val):
    v = str(val or "").replace("-", "").replace(".", "").strip()
    return f"{v[:4]}.{v[4:6]}.{v[6:]}" if len(v) == 8 else val
def fmt_phone(val):
    v = str(val or "").replace("-", "").replace(".", "").strip()
    if len(v) == 9: return f"{v[:2]}-{v[2:5]}-{v[5:]}"
    elif len(v) == 10: return f"{v[:2]}-{v[2:6]}-{v[6:]}" if v.startswith("02") else f"{v[:3]}-{v[3:6]}-{v[6:]}"
    elif len(v) == 11: return f"{v[:3]}-{v[3:7]}-{v[7:]}"
    return val

# 필수 입력 검사
def is_valid_mandatory():
    req_texts = ["in_company_name", "in_raw_biz_no", "in_biz_type", "in_start_date", "in_industry", "in_biz_addr", "in_rep_name", "in_rep_dob", "in_rep_phone", "in_home_addr", "in_home_status", "in_item_desc", "in_sales_route", "in_future_plan", "in_fund_purpose"]
    for k in req_texts:
        if not str(st.session_state.get(k, "") or "").strip(): return False
    return True

# --- 사이드바 ---
st.sidebar.header("⚙️ AI 엔진 설정")
config = load_config()
if "api_key" not in st.session_state: st.session_state["api_key"] = config.get("GEMINI_API_KEY", "")
api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
if st.sidebar.button("💾 API KEY 저장"):
    config["GEMINI_API_KEY"] = api_key_input; save_config(config); st.session_state["api_key"] = api_key_input; st.sidebar.success("✅ 저장됨!")
if st.session_state["api_key"]: genai.configure(api_key=st.session_state["api_key"])

st.sidebar.markdown("---")
st.sidebar.header("📂 업체 관리")
db = load_db()
if st.sidebar.button("💾 현재 정보 저장", use_container_width=True):
    cn = st.session_state.get("in_company_name", "").strip()
    if cn: db[cn] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}; save_db(db); st.sidebar.success("✅ 저장 완료!")

selected_company = st.sidebar.selectbox("저장된 업체 목록", ["선택 안 함"] + list(db.keys()))
col_s1, col_s2 = st.sidebar.columns(2)
with col_s1:
    if st.button("📂 불러오기", use_container_width=True) and selected_company != "선택 안 함":
        for k, v in db[selected_company].items(): st.session_state[k] = v
        st.rerun()
with col_s2:
    if st.button("🔄 초기화", use_container_width=True):
        for k in [k for k in st.session_state.keys() if k.startswith("in_")]: del st.session_state[k]
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🚀 빠른 리포트 생성")
def set_mode(m):
    if not is_valid_mandatory(): st.sidebar.error("🚨 필수 항목(*)을 모두 입력해주세요.")
    else:
        st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = m
        if m=="REPORT": st.session_state.pop("generated_report", None)
        elif m=="MATCHING": st.session_state.pop("generated_matching", None)
        st.rerun()

if st.sidebar.button("📊 기업분석리포트", key="side_1", use_container_width=True): set_mode("REPORT")
if st.sidebar.button("💡 정책자금 매칭리포트", key="side_2", use_container_width=True): set_mode("MATCHING")
if st.sidebar.button("📝 사업계획서 생성", key="side_3", use_container_width=True): set_mode("PLAN")

# --- 글로벌 상단 탭 ---
st.title("📊 AI 컨설팅 대시보드")
t1, t2, t3, t4 = st.columns(4)
with t1:
    if st.button("📊 기업분석리포트", key="top_1", use_container_width=True, type="primary"): set_mode("REPORT")
with t2:
    if st.button("💡 매칭리포트", key="top_2", use_container_width=True, type="primary"): set_mode("MATCHING")
with t3:
    if st.button("📝 사업계획서 생성", key="top_3", use_container_width=True, type="primary"): set_mode("PLAN")
with t4:
    if st.button("📑 마스터 사업계획서", key="top_4", use_container_width=True, type="primary"): set_mode("FULL_PLAN")
st.markdown("<hr>", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

# --- 리포트용 CSS ---
PDF_CSS = """
<style>
    body { font-family: 'Malgun Gothic', sans-serif; background: #525659; padding: 40px 0; }
    .doc { max-width: 900px; margin: 0 auto; background: #fff; padding: 60px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); border-radius: 8px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; border: 1.5px solid #333; }
    td, th { border: 1px solid #333; padding: 12px; font-size: 14px; }
    th { background: #f2f2f2; font-weight: bold; }
    .page-break { page-break-before: always; }
    @media print { body{ background:#fff; padding:0; } .doc{ box-shadow:none; padding:0; max-width:100%; } }
</style>
"""

# ==========================================
# 모드별 렌더링
# ==========================================
if st.session_state["view_mode"] == "REPORT":
    if st.button("⬅️ 대시보드 복귀"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    v = get_common_vars(st.session_state["permanent_data"])
    
    if "generated_report" not in st.session_state:
        with st.status("🚀 리포트 생성 중..."):
            try:
                # 그래프 생성
                m_vals = [int((v.val_cur/12) + ((v.val_cur/12)*0.5)*(i/11.0) + ((v.val_cur/12)*0.5)*0.15*np.sin((i/11.0)*np.pi*3.5)) for i in range(12)]
                fig = go.Figure(go.Scatter(x=[f"{i}월" for i in range(1, 13)], y=m_vals, mode='lines+markers+text', text=[format_kr_currency(x) for x in m_vals], textposition="top center", line=dict(color='#ab47bc', width=4, shape='spline')))
                fig.update_layout(width=760, height=400, template="plotly_white")
                plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

                pr = f"전문 컨설턴트. 파스텔톤 HTML 표. [기업]{v.c_name}/업종:{v.c_ind}/아이템:{v.item}. 시장 동향 포함 1000자 이상 방대하게. [GRAPH_INSERT_POINT] 포함 필수."
                res = genai.GenerativeModel(get_best_model_name()).generate_content(pr).text
                st.session_state["generated_report"] = clean_html(res).replace('[GRAPH_INSERT_POINT]', f"<div style='text-align:center;'>{plotly_html}</div>")
                st.balloons()
            except Exception as e: st.error(str(e)); st.stop()
    
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{PDF_CSS}</head><body><div class='doc'>{st.session_state.get('generated_report')}</div></body></html>"
    components.html(full_html, height=1000, scrolling=True)
    st.download_button("📥 다운로드", full_html, f"{v.c_name}_분석.html", "text/html")

elif st.session_state["view_mode"] == "MATCHING":
    if st.button("⬅️ 대시보드 복귀"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    v = get_common_vars(st.session_state["permanent_data"])
    if v.tax_status == '유' or v.fin_status == '유': st.error("🚨 체납/연체 시 자금 매칭 불가")
    else:
        if "generated_matching" not in st.session_state:
            with st.status("🚀 심사 중..."):
                pr = f"컨설턴트. HTML 박스 레이아웃. [기업]{v.c_name}/매출:{v.s_25}/보증:{v.guarantee}."
                st.session_state["generated_matching"] = genai.GenerativeModel(get_best_model_name()).generate_content(pr).text
                st.balloons()
        full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{PDF_CSS}</head><body><div class='doc'>{clean_html(st.session_state.get('generated_matching'))}</div></body></html>"
        components.html(full_html, height=1000, scrolling=True)

# --- 입력 화면 (기존 UI 완벽 복구) ---
else:
    st.markdown("<p style='color:#c62828; font-weight:bold;'>※ 필수정보를 입력해야 리포트가 생성됩니다.</p>", unsafe_allow_html=True)
    
    st.header("1. 기업현황")
    c1, c2, c3 = st.columns(3)
    with c1:
        bc1, bc2 = st.columns([1, 1])
        with bc1: biz_type = st.radio("* 사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
        with bc2:
            if biz_type == "법인": st.text_input("* 법인등록번호", placeholder="숫자만", key="in_raw_corp_no", on_change=cb_format_corp_no)
    with c2: st.text_input("* 기업명", key="in_company_name")
    with c3: st.text_input("* 사업자번호", placeholder="숫자만", key="in_raw_biz_no", on_change=cb_format_biz_no)

    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1: st.text_input("* 사업개시일", placeholder="YYYYMMDD", key="in_start_date", on_change=cb_format_date, args=("in_start_date",))
    with r2c2: st.text_input("* 사업장 주소", key="in_biz_addr")
    with r2c3: st.selectbox("* 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    r3c1, r3c2, r3c3 = st.columns(3)
    with r3c1:
        st.text_input("전화번호", placeholder="숫자만", key="in_biz_tel", on_change=cb_format_phone, args=("in_biz_tel",))
        st.number_input("상시근로자수(명)", value=0, step=1, format="%d", key="in_employee_count")
    with r3c2:
        ls = st.radio("임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
        if ls == "임대":
            ilc1, ilc2 = st.columns(2)
            with ilc1: st.number_input("보증금(만)", value=0, step=1, format="%d", key="in_lease_deposit")
            with ilc2: st.number_input("월세(만)", value=0, step=1, format="%d", key="in_lease_rent")
    with r3c3:
        if st.radio("추가사업장현황", ["무", "유"], horizontal=True, key="in_has_additional_biz") == "유":
            st.text_input("추가 정보", key="in_additional_biz_addr")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    r4c1, r4c2, r4c3, r4c4 = st.columns(4)
    with r4c1: st.text_input("* 대표자명", key="in_rep_name")
    with r4c2: st.text_input("* 생년월일", placeholder="YYYYMMDD", key="in_rep_dob", on_change=cb_format_date, args=("in_rep_dob",))
    with r4c3: st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")
    with r4c4: st.text_input("* 연락처 (휴대폰)", placeholder="숫자만", key="in_rep_phone", on_change=cb_format_phone, args=("in_rep_phone",))

    r5c1, r5c2, r5c3 = st.columns([2, 1, 1])
    with r5c1: st.text_input("* 거주지 주소", key="in_home_addr")
    with r5c2: st.selectbox("최종학력", ["중졸", "고졸", "전문대졸", "대졸", "석사", "박사"], key="in_edu_school")
    with r5c3: st.text_input("전공", key="in_edu_major")

    r6c1, r6c2, r6c3 = st.columns([1, 1, 2])
    with r6c1: st.radio("* 거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status")
    with r6c2:
        st.text_input("이메일 주소", key="in_rep_email")
        st.multiselect("부동산 현황", ["아파트", "빌라", "토지", "임야", "공장", "기타"], key="in_real_estate")
    with r6c3: st.text_area("* 경력(최근기준)", key="in_career", height=135)

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 신용 및 연체 정보")
    cr1, cr2 = st.columns(2)
    with cr1:
        st.radio("* 세금체납", ["무", "유"], horizontal=True, key="in_tax_status")
        st.radio("* 금융연체", ["무", "유"], horizontal=True, key="in_fin_status")
        kcb = st.number_input("* KCB 점수", value=0, step=1, format="%d", key="in_kcb_score")
        nice = st.number_input("* NICE 점수", value=0, step=1, format="%d", key="in_nice_score")
    with cr2:
        kg, ng = get_credit_grade(kcb, 'KCB'), get_credit_grade(nice, 'NICE')
        st.markdown(f"<div style='padding:20px; background:#e8f0fe; border-radius:12px; text-align:center; margin-top:28px;'>🏆 KCB: <span style='color:red;'>{kg}등급</span> | NICE: <span style='color:red;'>{ng}등급</span></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("4. 매출현황")
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.number_input("* 금년 매출(만)", value=0, step=1, format="%d", key="in_sales_current")
    with m2: st.number_input("* 25년 매출(만)", value=0, step=1, format="%d", key="in_sales_2025")
    with m3: st.number_input("* 24년 매출(만)", value=0, step=1, format="%d", key="in_sales_2024")
    with m4: st.number_input("* 23년 매출(만)", value=0, step=1, format="%d", key="in_sales_2023")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("5. 부채현황")
    d1, d2, d3, d4 = st.columns(4)
    with d1: st.number_input("* 중진공(만)", value=0, key="in_debt_kosme")
    with d2: st.number_input("* 소진공(만)", value=0, key="in_debt_semas")
    with d3: st.number_input("* 신보재단(만)", value=0, key="in_debt_koreg")
    with d4: st.number_input("* 신용보증기금(만)", value=0, key="in_debt_kodit")
    d5, d6, d7, d8 = st.columns(4)
    with d5: st.number_input("* 기술보증기금(만)", value=0, key="in_debt_kibo")
    with d6: st.number_input("* 기타(만)", value=0, key="in_debt_etc")
    with d7: st.number_input("* 신용(만)", value=0, key="in_debt_credit")
    with d8: st.number_input("* 담보(만)", value=0, key="in_debt_coll")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("8. 비즈니스 정보")
    st.text_area("* [아이템]", key="in_item_desc")
    st.text_area("* [판매루트]", key="in_sales_route")
    st.text_area("* [앞으로의 계획]", key="in_future_plan")
    
    st.success("✅ 세팅 완료! 상단 버튼을 클릭해 리포트를 생성하세요.")

