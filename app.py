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
# 0. 기본 설정 및 UI 패치
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")
st.markdown("""
<style>
div.stButton > button { min-height: 55px !important; white-space: nowrap !important; line-height: 1.2 !important; font-size: 16.5px !important; font-weight: bold !important; letter-spacing: -0.3px !important; }
section[data-testid="stSidebar"] div.stButton > button { min-height: 45px !important; font-size: 12.5px !important; white-space: nowrap !important; letter-spacing: -0.5px !important; padding: 0px 10px !important; }
</style>
""", unsafe_allow_html=True)

# --- 콜백 함수: 자동 하이픈(-) 포맷팅 ---
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

def cb_format_biz_no(): st.session_state["in_raw_biz_no"] = fmt_biz(st.session_state.get("in_raw_biz_no"))
def cb_format_corp_no(): st.session_state["in_raw_corp_no"] = fmt_corp(st.session_state.get("in_raw_corp_no"))
def cb_format_date(key): st.session_state[key] = fmt_date(st.session_state.get(key))
def cb_format_phone(key): st.session_state[key] = fmt_phone(st.session_state.get(key))

# --- 필수 입력 검증 ---
def is_valid_mandatory():
    req_texts = ["in_company_name", "in_raw_biz_no", "in_biz_type", "in_start_date", "in_industry", "in_biz_addr", "in_rep_name", "in_rep_dob", "in_rep_phone", "in_home_addr", "in_home_status", "in_item_desc", "in_sales_route", "in_future_plan", "in_fund_purpose"]
    if st.session_state.get("in_biz_type") == "법인": req_texts.append("in_raw_corp_no")
    for k in req_texts:
        if not str(st.session_state.get(k, "") or "").strip(): return False
    req_nums = ["in_kcb_score", "in_nice_score", "in_sales_current", "in_sales_2025", "in_sales_2024", "in_sales_2023", "in_debt_kosme", "in_debt_semas", "in_debt_koreg", "in_debt_kodit", "in_debt_kibo", "in_debt_etc", "in_debt_credit", "in_debt_coll", "in_req_amount"]
    for k in req_nums:
        if st.session_state.get(k) is None: return False
    return True

# --- 설정 및 로직 ---
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
                st.rerun()
            else: st.error("비밀번호가 틀렸습니다.")
        return False
    return True

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

def get_best_model_name():
    try:
        av = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for pref in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-1.0-pro']:
            if pref in av: return pref
        return av[0].replace('models/', '') if av else 'gemini-pro'
    except: return 'gemini-pro'

def clean_html(text): return "\n".join([l.lstrip() for l in text.replace("```html", "").replace("```", "").strip().split("\n")])

def get_credit_grade(sc, t="NICE"):
    sc = safe_int(sc)
    if t == "NICE": return 1 if sc>=900 else 2 if sc>=870 else 3 if sc>=840 else 4 if sc>=805 else 5 if sc>=750 else 6 if sc>=665 else 7 if sc>=600 else 8 if sc>=515 else 9 if sc>=445 else 10
    else: return 1 if sc>=942 else 2 if sc>=891 else 3 if sc>=832 else 4 if sc>=768 else 5 if sc>=698 else 6 if sc>=630 else 7 if sc>=530 else 8 if sc>=454 else 9 if sc>=335 else 10

# --- 핵심 데이터 추출 (토큰 절약용 공통 함수) ---
class VarObj: pass
def get_common_vars(d):
    v = VarObj()
    g = lambda k, df="미입력": d.get(k, df)
    v.c_name, v.rep_name, v.biz_type, v.c_ind = g('in_company_name').strip(), g('in_rep_name'), g('in_biz_type'), g('in_industry')
    v.address, v.career, v.edu_school, v.edu_major = g('in_biz_addr'), g('in_career'), g('in_edu_school', ''), g('in_edu_major', '')
    v.home_addr, v.process_desc = g('in_home_addr'), g('in_process_desc')
    v.biz_no, v.corp_no = str(g('in_raw_biz_no')), str(g('in_raw_corp_no', ''))
    v.s_25, v.s_cur = format_kr_currency(g('in_sales_2025', 0)), format_kr_currency(g('in_sales_current', 0))
    v.sales_24, v.sales_23 = format_kr_currency(g('in_sales_2024', 0)), format_kr_currency(g('in_sales_2023', 0))
    v.req_fund, v.fund_type, v.fund_purpose = format_kr_currency(g('in_req_amount', 0)), g('in_fund_type', '운전자금'), g('in_fund_purpose')
    v.item, v.market, v.diff, v.route = g('in_item_desc'), g('in_market_status'), g('in_diff_point'), g('in_sales_route', '')
    v.lease_status, v.start_date_str = g('in_lease_status', '자가'), g('in_start_date', '').strip()
    v.biz_years = max(0, 2026 - int(v.start_date_str[:4])) if v.start_date_str and v.start_date_str != '미입력' else 0
    cl = [f"{c}({g(f'in_cert_date_{i}', '일자미상')})" for i, c in enumerate(["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]) if d.get(f"in_chk_{i}")]
    v.cert_status = ", ".join(cl) if cl else "미보유"
    pl = [f"{pt} {safe_int(g(f'in_{pt}_cnt', 0))}건" for pt in ["특허출원", "특허등록", "상표등록", "디자인등록"] if g('in_has_patent') == '유' and safe_int(g(f"in_{pt}_cnt", 0)) > 0]
    v.pat_str = " ".join(pl) if pl else "특허/지재권 미보유"
    v.gov_str = f"지원사업 {safe_int(g('in_gov_cnt', 0))}건" if g('in_has_gov') == '유' and safe_int(g('in_gov_cnt', 0)) > 0 else "지원사업 이력 없음"
    v.exp_info = f"유(24년 {format_kr_currency(g('in_exp_2024', 0))}, 금년 {format_kr_currency(g('in_exp_current', 0))})" if g('in_is_export') == '유' else "무(전액 내수)"
    v.tax_status, v.fin_status = g('in_tax_status', '무'), g('in_fin_status', '무')
    v.nice_score, v.emp_cnt = safe_int(g('in_nice_score', 0)), safe_int(g('in_employee_count', 0))
    kibo, kodit = safe_int(g('in_debt_kibo', 0)), safe_int(g('in_debt_kodit', 0))
    v.guarantee = "기보 이용중(신보 불가)" if kibo > 0 else ("신보 이용중(기보 불가)" if kodit > 0 else "신보/기보 자유선택 가능")
    v.tot_debt = format_kr_currency(sum([safe_int(g(k, 0)) for k in ['in_debt_kosme', 'in_debt_semas', 'in_debt_koreg', 'in_debt_kodit', 'in_debt_kibo', 'in_debt_etc', 'in_debt_credit', 'in_debt_coll']]))
    v.add_biz_status, v.add_biz_addr = g('in_has_additional_biz', '무'), g('in_additional_biz_addr', '').strip()
    v.val_cur = safe_int(g('in_sales_current', 0))
    return v

if check_password():
    # ==========================================
    # 1. 사이드바 (API 설정, 업체관리)
    # ==========================================
    st.sidebar.header("⚙️ AI 엔진 설정")
    config = load_config()
    if "api_key" not in st.session_state: st.session_state["api_key"] = config.get("GEMINI_API_KEY", st.secrets.get("GEMINI_API_KEY", ""))
    api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
    if st.sidebar.button("💾 API KEY 저장"):
        st.session_state["api_key"] = api_key_input
        config["GEMINI_API_KEY"] = api_key_input
        save_config(config)
        st.sidebar.success("✅ 저장 완료!")
        time.sleep(1)
        st.rerun()

    if st.session_state["api_key"]: genai.configure(api_key=st.session_state["api_key"])

    st.sidebar.markdown("---")
    st.sidebar.header("📂 업체 관리")
    db = load_db()
    if st.sidebar.button("💾 현재 정보 저장", use_container_width=True):
        c_name = st.session_state.get("in_company_name", "").strip()
        if c_name:
            db[c_name] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            save_db(db)
            st.sidebar.success(f"✅ '{c_name}' 저장 완료!")

    selected_company = st.sidebar.selectbox("저장된 업체 목록", ["선택 안 함"] + list(db.keys()))
    col_s1, col_s2 = st.sidebar.columns(2)
    with col_s1:
        if st.button("📂 불러오기", use_container_width=True) and selected_company != "선택 안 함":
            for k, v in db[selected_company].items(): st.session_state[k] = v
            cb_format_biz_no()
            cb_format_corp_no()
            cb_format_date("in_start_date")
            cb_format_date("in_rep_dob")
            cb_format_phone("in_biz_tel")
            cb_format_phone("in_rep_phone")
            for i in range(8): cb_format_date(f"in_cert_date_{i}")
            st.rerun()
    with col_s2:
        if st.button("🔄 초기화", use_container_width=True):
            for k in [k for k in st.session_state.keys() if k.startswith("in_")]:
                if any(x in k for x in ["sales", "debt", "score", "amount", "count", "cnt", "deposit", "rent"]): st.session_state[k] = None
                elif "chk" in k: st.session_state[k] = False
                elif "real_estate" in k: st.session_state[k] = []
                else: st.session_state[k] = ""
            st.rerun()

    # ==========================================
    # 상단 고정 탭 메뉴 (리포트 화면에서도 유지)
    # ==========================================
    st.title("📊 AI 컨설팅 대시보드")
    t1, t2, t3, t4 = st.columns(4)
    def set_mode(m):
        if not is_valid_mandatory(): st.error("🚨 필수 항목(*)을 모두 입력해주세요.")
        else:
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = m
            if m == "REPORT": st.session_state.pop("generated_report", None)
            elif m == "MATCHING": st.session_state.pop("generated_matching", None)
            elif m == "PLAN": st.session_state.pop("kosme_result_html", None); st.session_state.pop("semas_result_html", None)
            st.rerun()

    with t1:
        if st.button("📊 기업분석리포트", use_container_width=True, type="primary"): set_mode("REPORT")
    with t2:
        if st.button("💡 매칭리포트", use_container_width=True, type="primary"): set_mode("MATCHING")
    with t3:
        if st.button("📝 맞춤형 AI 생성", use_container_width=True, type="primary"): set_mode("PLAN")
    with t4:
        if st.button("📑 AI 사업계획서", use_container_width=True, type="primary"): set_mode("FULL_PLAN")
    
    st.markdown("<hr style='margin-top:5px; margin-bottom:20px;'>", unsafe_allow_html=True)

    if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
    if "permanent_data" not in st.session_state: st.session_state["permanent_data"] = {}

    # ==========================================
    # 모드 A: 리포트
    # ==========================================
    if st.session_state["view_mode"] == "REPORT":
        if st.button("⬅️ 대시보드 (입력화면)로 돌아가기"):
            for k, val in st.session_state["permanent_data"].items(): st.session_state[k] = val
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        v = get_common_vars(st.session_state["permanent_data"])
        st.subheader(f"📋 AI기업분석리포트 (대상기업: {v.c_name})")
        
        if not st.session_state["api_key"]: st.error("⚠️ API 키를 입력해주세요.")
        else:
            corp_text = f"<br><span style='font-size:0.9em; color:#555;'>({v.corp_no})</span>" if v.corp_no else ""
            add_biz_row = f"<tr><td style='padding:15px; background-color:#eceff1;'><b>추가사업장</b></td><td colspan='5' style='padding:15px; text-align:left;'>{v.add_biz_addr}</td></tr>" if v.add_biz_status == '유' and v.add_biz_addr else ""
            
            val_cur = v.val_cur if v.val_cur > 0 else 1000
            sv, ev = val_cur / 12, (val_cur / 12) * 1.5
            m_vals = [int(sv + (ev - sv)*(i/11.0) + (ev - sv)*0.15*np.sin((i/11.0)*np.pi*3.5)) for i in range(12)]
            fig = go.Figure(go.Scatter(x=[f"{i}월" for i in range(1, 13)], y=m_vals, mode='lines+markers+text', text=[format_kr_currency(x) for x in m_vals], textposition="top center", line=dict(color='#1E88E5', width=4, shape='spline')))
            fig.update_layout(title="📈 향후 1년 예상 매출", template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
            plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
            
            if "generated_report" not in st.session_state:
                with st.status("🚀 리포트 분석 중...", expanded=True) as status:
                    st.write("⏳ 1/3 데이터 연동... \n⏳ 2/3 로직 분석... \n⏳ 3/3 렌더링...")
                    try:
                        prompt = f"""당신은 20년차 경영컨설턴트. 마크다운 금지. 명사형 종결. HTML 사용. [기업] 기업명:{v.c_name}/업종:{v.c_ind}/아이템:{v.item}/시장:{v.market}/차별화:{v.diff}/자금:{v.req_fund}/인증:{v.cert_status}/특허:{v.pat_str}
<h2 style="color:#174EA6; border-bottom:2px solid #174EA6;">1. 기업현황분석</h2>
<table style="width:100%; border-collapse:collapse; text-align:center; border:1px solid #ccc;">
<tr><th style="background:#eceff1; border:1px solid #ccc; padding:10px;">기업명</th><td style="border:1px solid #ccc;">{v.c_name}</td><th style="background:#eceff1; border:1px solid #ccc;">사업자유형</th><td style="border:1px solid #ccc;">{v.biz_type}</td><th style="background:#eceff1; border:1px solid #ccc;">업종</th><td style="border:1px solid #ccc;">{v.c_ind}</td></tr>
<tr><th style="background:#eceff1; border:1px solid #ccc; padding:10px;">대표자</th><td style="border:1px solid #ccc;">{v.rep_name}</td><th style="background:#eceff1; border:1px solid #ccc;">사업자번호</th><td style="border:1px solid #ccc;">{v.biz_no}{corp_text}</td><th style="background:#eceff1; border:1px solid #ccc;">주소</th><td style="border:1px solid #ccc;">{v.address}</td></tr>
<tr><th style="background:#eceff1; border:1px solid #ccc; padding:10px;">인증/특허</th><td colspan="5" style="text-align:left; border:1px solid #ccc; padding:10px;">{v.cert_status} / {v.pat_str}</td></tr>
{add_biz_row}
</table>
<p>(기업 잠재력 방대한 서술)</p>
<h2 style="color:#174EA6; border-bottom:2px solid #174EA6;">2. SWOT 분석</h2>
<p>(강점, 약점, 기회, 위협을 HTML 표로 방대하게 작성)</p>
<h2 style="color:#174EA6; border-bottom:2px solid #174EA6;">3. 핵심 경쟁력 및 자금사용계획 ({v.req_fund})</h2>
<p>(경쟁사 비교표 및 자금 세부 사용계획 표 작성)</p>
[GRAPH_INSERT_POINT]
<h2 style="color:#174EA6; border-bottom:2px solid #174EA6;">4. 성장 비전 코멘트</h2>
<p>(단기/중기/장기 비전 방대한 서술)</p>"""
                        model = genai.GenerativeModel(get_best_model_name())
                        st.session_state["generated_report"] = model.generate_content(prompt).text
                        status.update(label="✅ 리포트 완료!", state="complete")
                        st.balloons()
                    except Exception as e:
                        status.update(label=f"❌ 오류: {str(e)}", state="error")
                        st.stop()

            res = clean_html(st.session_state.get("generated_report", "")).replace('[GRAPH_INSERT_POINT]', plotly_html)
            st.markdown(res, unsafe_allow_html=True)
            st.download_button("📥 다운로드", f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body style='font-family:Malgun Gothic;'>{res}</body></html>", f"{v.c_name}_분석.html", "text/html")

    # ==========================================
    # 모드 B: 매칭
    # ==========================================
    elif st.session_state["view_mode"] == "MATCHING":
        if st.button("⬅️ 대시보드 (입력화면)로 돌아가기"):
            for k, val in st.session_state["permanent_data"].items(): st.session_state[k] = val
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        v = get_common_vars(st.session_state["permanent_data"])
        st.subheader(f"🎯 AI 정책자금 최적화 매칭 (대상기업: {v.c_name})")
        
        if v.tax_status == '유' or v.fin_status == '유': st.error("🚨 세금체납 및 금융연체가 있을 시 자금 매칭이 진행되지 않습니다.")
        else:
            if "generated_matching" not in st.session_state:
                with st.status("🚀 매칭 심사 중...", expanded=True) as status:
                    st.write("⏳ 로직 적용 중...")
                    try:
                        prompt = f"""당신은 컨설턴트. 마크다운 금지. 반드시 아래 HTML 박스 레이아웃을 그대로 사용할 것. 절대 <tr><th>순위</th>... 형식의 기본 표를 만들지 마세요.
[기업]명:{v.c_name}/업종:{v.c_ind}/근로자:{v.emp_cnt}/매출:{v.s_25}/기대출:{v.tot_debt}/인증:{v.cert_status}/특허:{v.pat_str}
[룰] 보증상태({v.guarantee}) 반영 중복 금지. 

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업 스펙 진단 요약</h2>
<div style="background-color:#f8f9fa; padding:20px; border-radius:15px; border:1px solid #e0e0e0; margin-bottom:15px; line-height:1.8;">
  <b>기업명:</b> {v.c_name} | <b>업종:</b> {v.c_ind} | <b>업력:</b> 약 {v.biz_years}년 | <b>근로자:</b> {v.emp_cnt}명 <br>
  <b>인증:</b> {v.cert_status} | <b>특허:</b> {v.pat_str} | <b>정부지원:</b> {v.gov_str} <br>
  <b>전년도매출:</b> <span style="color:#1565c0; font-weight:bold;">{v.s_25}</span> | <b>총 기대출:</b> <span style="color:red;">{v.tot_debt}</span> | <b style="font-size:1.15em;">희망 필요자금: {v.req_fund}</b>
</div>
<div style="margin-bottom:20px; padding:15px; background-color:#e3f2fd; border-radius:10px;">
  <b>💡 종합 진단 코멘트:</b><br>
  (기업의 현재 재무상황, 부채비율, 인증/특허 현황을 종합적으로 분석하여 자금 조달 가능성과 핵심 포인트를 3~4문장으로 아주 상세하고 방대하게 서술하세요)
</div>

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. 우선순위 추천 정책자금 (1~2순위)</h2>
<table style="width:100%; border-collapse: collapse; margin-bottom:15px; table-layout: fixed;">
  <tr>
    <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32; vertical-align:top; width:48.5%;">
      <b style="font-size:1.2em; color:#2e7d32;">🥇 1순위: [기관명] / [세부자금]</b><br><b style="color:#333;">예상 한도: OOO</b><br><br>&bull; (추천 사유 상세 2~3줄)<br>&bull; (진행 전략 상세 2~3줄)
    </td>
    <td style="width:3%;"></td>
    <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32; vertical-align:top; width:48.5%;">
      <b style="font-size:1.2em; color:#2e7d32;">🥈 2순위: [신보/기보 택1] / [상품명]</b><br><b style="color:#333;">예상 한도: OOO</b><br><br>&bull; (추천 사유 상세 2~3줄)<br>&bull; (진행 전략 상세 2~3줄)
    </td>
  </tr>
</table>

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 후순위 추천 (플랜 B)</h2>
<table style="width:100%; border-collapse: collapse; margin-bottom:15px; table-layout: fixed;">
  <tr>
    <td style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00; vertical-align:top; width:48.5%;">
      <b style="font-size:1.2em; color:#ef6c00;">🥉 3순위: [지역신보 등] / [세부자금]</b><br><b style="color:#333;">예상 한도: OOO</b><br><br>&bull; (추천 사유 상세 2~3줄)<br>&bull; (진행 전략 상세 2~3줄)
    </td>
    <td style="width:3%;"></td>
    <td style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00; vertical-align:top; width:48.5%;">
      <b style="font-size:1.2em; color:#ef6c00;">🏅 4순위: [시중은행 등] / [세부자금]</b><br><b style="color:#333;">예상 한도: OOO</b><br><br>&bull; (추천 사유 상세 2~3줄)<br>&bull; (진행 전략 상세 2~3줄)
    </td>
  </tr>
</table>

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 심사 전 필수 체크리스트 및 보완 가이드</h2>
<div style="background-color:#ffebee; border-left:5px solid #d32f2f; padding:15px; border-radius:15px; margin-top:15px;">
  <b style="font-size:1.1em; color:#c62828;">🚨 필수 보완 조언:</b><br><br>&bull; (특허/인증 확보 및 활용 조언 2줄)<br>&bull; (재무/고용 등 약점 보완 조언 2줄)
</div>"""
                        model = genai.GenerativeModel(get_best_model_name())
                        st.session_state["generated_matching"] = model.generate_content(prompt).text
                        status.update(label="✅ 완료!", state="complete")
                        st.balloons()
                    except Exception as e:
                        status.update(label=f"❌ 오류: {str(e)}", state="error")
                        st.stop()
            res = clean_html(st.session_state.get("generated_matching", ""))
            st.markdown(res, unsafe_allow_html=True)
            st.download_button("📥 다운로드", f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body style='font-family:Malgun Gothic;'>{res}</body></html>", f"{v.c_name}_매칭.html", "text/html")

    # ==========================================
    # 모드 C: PLAN
    # ==========================================
    elif st.session_state["view_mode"] == "PLAN":
        if st.button("⬅️ 대시보드 (입력화면)로 돌아가기"):
            for k, val in st.session_state["permanent_data"].items(): st.session_state[k] = val
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
            
        v = get_common_vars(st.session_state["permanent_data"])
        st.subheader("📝 기관별 맞춤형 사업계획서")
        tabs = st.tabs(["1. 중소벤처기업진흥공단", "2. 소상공인시장진흥공단"])

        with tabs[0]:
            st.markdown("#### 🏢 중소벤처기업진흥공단 (중진공)")
            fund_cats = {"혁신창업화자금":["청년전용창업자금", "개발기술사업화자금"], "신시장진출지원자금":["내수기업 수출기업화자금", "수출지원자금"], "신성장기반자금":["혁신성장지원자금", "스케일업금융자금"]}
            c1, c2 = st.columns(2)
            with c1: mf = st.selectbox("💡 대분류", list(fund_cats.keys()))
            with c2: sf = st.selectbox("💡 세부분류", fund_cats[mf])
            
            p1, p2 = st.columns(2)
            with p1:
                st.markdown("#### 📄 공통 융자신청서")
                if st.button("🚀 중진공 융자신청서 보기", use_container_width=True):
                    with st.status("🚀 융자신청서 생성 중..."):
                        try:
                            pr = f"컨설턴트. 마크다운 금지. HTML 표.\n[기업]{v.c_name}/매출:{v.sales_24}/{v.s_cur}/자금:{v.req_fund}/아이템:{v.item}\n<h2 style='text-align:center;'>중진공 융자신청서</h2><table border='1'><tr><th>신청자금</th><td>▣ {sf}</td><th>금액</th><td>{v.req_fund}</td></tr></table><p>(공정도, 시장상황 매우 상세히 추가)</p>"
                            st.session_state["kosme_result_type"] = "loan"
                            st.session_state["kosme_result_html"] = clean_html(genai.GenerativeModel(get_best_model_name()).generate_content(pr).text)
                        except Exception as e: st.error(str(e))
            with p2:
                st.markdown(f"#### 📝 사업계획서 ({sf})")
                if st.button(f"🚀 중진공 {sf} 보기", use_container_width=True):
                    with st.status("🚀 사업계획서 생성 중..."):
                        try:
                            val_cur = v.val_cur if v.val_cur > 0 else 1000
                            sv, ev = val_cur / 12, (val_cur / 12) * 1.5
                            m_vals = [int(sv + (ev - sv)*(i/11.0) + (ev - sv)*0.15*np.sin((i/11.0)*np.pi*3.5)) for i in range(12)]
                            fig = go.Figure(go.Scatter(x=[f"{i}월" for i in range(1, 13)], y=m_vals, mode='lines+markers+text', text=[format_kr_currency(x) for x in m_vals], textposition="top center", line=dict(color='#1E88E5', width=4, shape='spline')))
                            plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

                            pr = f"심사역. 마크다운 금지. HTML.\n[기업]{v.c_name}/업력:{v.biz_years}년/아이템:{v.item}/매출:{v.s_cur}\n<h1>{sf} 사업계획서</h1><p>(서론 500자)</p><h2>1. 사업개요</h2><p>(상세)</p><h2>2. 시장성</h2><p>(상세)</p><h2>3. 추진계획</h2><p>(상세)</p>[GRAPH]"
                            res = clean_html(genai.GenerativeModel(get_best_model_name()).generate_content(pr).text).replace("[GRAPH]", plotly_html)
                            st.session_state["kosme_result_type"] = "plan"
                            st.session_state["kosme_result_html"] = res
                        except Exception as e: st.error(str(e))

            if "kosme_result_html" in st.session_state:
                st.divider()
                dt = "사업계획서" if st.session_state["kosme_result_type"] == "plan" else "융자신청서"
                st.subheader(f"📄 {dt}")
                st.markdown(st.session_state["kosme_result_html"], unsafe_allow_html=True)
                st.download_button("📥 다운로드", f"<!DOCTYPE html><html><body style='font-family:Malgun Gothic;'>{st.session_state['kosme_result_html']}</body></html>", f"{v.c_name}_{dt}.html", "text/html")

        with tabs[1]:
            st.markdown("#### 🏪 소상공인시장진흥공단 (소진공)")
            s_fund = st.selectbox("💡 소진공 자금선택", ["혁신성장촉진자금", "상생성장지원자금", "신용취약소상공인자금", "일시적경영애로자금", "재도전특별자금", "민간투자연계형매칭융자"])
            if st.button(f"🚀 소진공 {s_fund} 생성", use_container_width=True):
                with st.status("🚀 통합 서식 생성 중..."):
                    try:
                        pr = f"심사역. 마크다운 금지. HTML 표.\n[기업]{v.c_name}/아이템:{v.item}/매출:{v.s_cur}/자금:{v.req_fund}\n[규칙]개조식 단문 작성.\n<h2>기업현황 및 사업계획서 ({s_fund})</h2><table border='1' width='100%'><tr><th>업체명</th><td>{v.c_name}</td><th>대표</th><td>{v.rep_name}</td></tr><tr><th>매출</th><td colspan='3'>{v.sales_24} / {v.s_cur}</td></tr></table><h3>사업계획</h3><table border='1' width='100%'><tr><th>내용/목적</th><td>(상세)</td></tr><tr><th>경쟁력</th><td>(상세)</td></tr></table><h3>자금집행계획</h3><table border='1' width='100%'><tr><th>총소요</th><td>{v.req_fund}</td></tr></table>"
                        st.session_state["semas_result_html"] = clean_html(genai.GenerativeModel(get_best_model_name()).generate_content(pr).text)
                    except Exception as e: st.error(str(e))
            if "semas_result_html" in st.session_state:
                st.divider()
                st.markdown(st.session_state["semas_result_html"], unsafe_allow_html=True)
                st.download_button("📥 다운로드", f"<!DOCTYPE html><html><body style='font-family:Malgun Gothic;'>{st.session_state['semas_result_html']}</body></html>", f"{v.c_name}_소진공.html", "text/html")

    elif st.session_state["view_mode"] == "FULL_PLAN":
        if st.button("⬅️ 대시보드 (입력화면)로 돌아가기"):
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        st.title("📑 AI 사업계획서 자동 생성")
        st.radio("💡 용도 선택", ["기관제출용", "투자용(IR)"], horizontal=True)

    # ==========================================
    # 메인 대시보드 (입력폼)
    # ==========================================
    else:
        st.markdown("<p style='color:#c62828; font-weight:bold; font-size:1.1em;'>※ 필수정보를 입력해야 리포트가 생성됩니다.</p>", unsafe_allow_html=True)
        
        st.header("1. 기업현황")
        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c1:
            bc1, bc2 = st.columns([1, 1])
            with bc1: biz_type = st.radio("* 사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
            with bc2:
                if biz_type == "법인": st.text_input("* 법인등록번호", placeholder="숫자만", key="in_raw_corp_no", on_change=cb_format_corp_no)
        with r1c2: st.text_input("* 기업명", key="in_company_name")
        with r1c3: st.text_input("* 사업자번호", placeholder="숫자만", key="in_raw_biz_no", on_change=cb_format_biz_no)

        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1: st.text_input("* 사업개시일", placeholder="YYYYMMDD", key="in_start_date", on_change=cb_format_date, args=("in_start_date",))
        with r2c2: st.text_input("* 사업장 주소", key="in_biz_addr")
        with r2c3: st.selectbox("* 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

        r3c1, r3c2, r3c3 = st.columns(3)
        with r3c1:
            pc1, pc2 = st.columns(2)
            with pc1: st.text_input("전화번호", placeholder="숫자만", key="in_biz_tel", on_change=cb_format_phone, args=("in_biz_tel",))
            with pc2: st.number_input("상시근로자수(명)", value=None, step=1, format="%d", key="in_employee_count")
        with r3c2:
            ls = st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
            if ls == "임대":
                lc1, lc2 = st.columns(2)
                with lc1: st.number_input("보증금(만)", value=None, step=1, format="%d", placeholder="예:1억=10000", key="in_lease_deposit")
                with lc2: st.number_input("월세(만)", value=None, step=1, format="%d", placeholder="예:100만=100", key="in_lease_rent")
        with r3c3:
            ab = st.radio("추가사업장현황", ["무", "유"], horizontal=True, key="in_has_additional_biz")
            if ab == "유": st.text_input("추가 사업장 정보", key="in_additional_biz_addr")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("2. 대표자 정보")
        dob = str(st.session_state.get("in_rep_dob", "") or "").replace(".", "").strip()
        is_youth = len(dob)==8 and (2026 - int(dob[:4]) <= 39)
        d_lbl = "* 생년월일 🌟 청년사업자" if is_youth else "* 생년월일"

        r4c1, r4c2, r4c3, r4c4 = st.columns(4)
        with r4c1: st.text_input("* 대표자명", key="in_rep_name")
        with r4c2: st.text_input(d_lbl, placeholder="YYYYMMDD", key="in_rep_dob", on_change=cb_format_date, args=("in_rep_dob",))
        with r4c3: st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")
        with r4c4: st.text_input("* 연락처 (휴대폰)", placeholder="숫자만", key="in_rep_phone", on_change=cb_format_phone, args=("in_rep_phone",))

        r5c1, r5c2, r5c3 = st.columns([2, 1, 1])
        with r5c1: st.text_input("* 거주지 주소", key="in_home_addr")
        with r5c2: st.selectbox("최종학력", ["중학교 졸업", "고등학교 졸업", "2년제 대학교 졸업", "4년제 대학교 졸업", "석사 수료/졸업", "박사 수료/졸업"], key="in_edu_school")
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
            cc1, cc2 = st.columns(2)
            with cc1: st.radio("* 세금체납", ["무", "유"], horizontal=True, key="in_tax_status")
            with cc2: st.radio("* 금융연체", ["무", "유"], horizontal=True, key="in_fin_status")
            sc1, sc2 = st.columns(2)
            with sc1: kcb = st.number_input("* KCB 점수", value=None, step=1, format="%d", key="in_kcb_score")
            with sc2: nice = st.number_input("* NICE 점수", value=None, step=1, format="%d", key="in_nice_score")
        with cr2: 
            k_g, n_g = get_credit_grade(kcb, 'KCB'), get_credit_grade(nice, 'NICE')
            st.markdown(f"""
            <div style="padding:15px; background-color:#e8f0fe; border-radius:10px; border:1px solid #c2e0ff; text-align:center; margin-top:28px;">
                <h4 style="color:#1967d2; margin-top:0; margin-bottom:10px;">🏆 신용등급 판정 결과</h4>
                <p style="font-size:22px; font-weight:bold; margin-bottom:0;">KCB: <span style="color:#d32f2f;">{k_g}등급</span> &nbsp;&nbsp;|&nbsp;&nbsp; NICE: <span style="color:#d32f2f;">{n_g}등급</span></p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("4. 매출현황")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.number_input("* 금년(당월) 매출(만원)", value=None, step=1, format="%d", placeholder="예:1억=10000", key="in_sales_current")
        with m2: st.number_input("* 25년도 매출(만원)", value=None, step=1, format="%d", placeholder="예:1억=10000", key="in_sales_2025")
        with m3: st.number_input("* 24년도 매출(만원)", value=None, step=1, format="%d", placeholder="예:1억=10000", key="in_sales_2024")
        with m4: st.number_input("* 23년도 매출(만원)", value=None, step=1, format="%d", placeholder="예:1억=10000", key="in_sales_2023")
        
        if st.session_state.get("in_industry", "기타") in ["제조업", "도소매업"]:
            if st.radio("수출 유무", ["무", "유"], horizontal=True, key="in_is_export") == "유":
                e1, e2, e3 = st.columns(3)
                with e1: st.number_input("금년 수출(만원)", value=None, step=1, format="%d", key="in_exp_current")
                with e2: st.number_input("25년 수출(만원)", value=None, step=1, format="%d", key="in_exp_2025")
                with e3: st.number_input("24년 수출(만원)", value=None, step=1, format="%d", key="in_exp_2024")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("5. 부채현황")
        d1, d2, d3, d4 = st.columns(4)
        with d1: st.number_input("* 중진공(만원)", value=None, step=1, format="%d", key="in_debt_kosme")
        with d2: st.number_input("* 소진공(만원)", value=None, step=1, format="%d", key="in_debt_semas")
        with d3: st.number_input("* 신용보증재단(만원)", value=None, step=1, format="%d", key="in_debt_koreg")
        with d4: st.number_input("* 신용보증기금(만원)", value=None, step=1, format="%d", key="in_debt_kodit")
        d5, d6, d7, d8 = st.columns(4)
        with d5: st.number_input("* 기술보증기금(만원)", value=None, step=1, format="%d", key="in_debt_kibo")
        with d6: st.number_input("* 기타(만원)", value=None, step=1, format="%d", key="in_debt_etc")
        with d7: st.number_input("* 신용대출(만원)", value=None, step=1, format="%d", key="in_debt_credit")
        with d8: st.number_input("* 담보대출(만원)", value=None, step=1, format="%d", key="in_debt_coll")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("6. 필요자금")
        p1, p2, p3 = st.columns([1, 1, 2])
        with p1: st.selectbox("* 자금구분", ["운전자금", "시설자금"], key="in_fund_type")
        with p2: st.number_input("* 필요자금액(만원)", value=None, step=1, format="%d", key="in_req_amount")
        with p3: st.text_input("* 사용용도", key="in_fund_purpose")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("7. 인증 및 특허")
        certs = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
        c_cols1 = st.columns(4)
        for i in range(4):
            with c_cols1[i]:
                if st.checkbox(certs[i], key=f"in_chk_{i}"): st.text_input(f"↪ 일자", key=f"in_cert_date_{i}", on_change=cb_format_date, args=(f"in_cert_date_{i}",))
        c_cols2 = st.columns(4)
        for i in range(4, 8):
            with c_cols2[i-4]:
                if st.checkbox(certs[i], key=f"in_chk_{i}"): st.text_input(f"↪ 일자", key=f"in_cert_date_{i}", on_change=cb_format_date, args=(f"in_cert_date_{i}",))
        
        st.markdown("<br>", unsafe_allow_html=True)
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.radio("특허/지식재산권", ["무", "유"], horizontal=True, key="in_has_patent") == "유":
                for pt in ["특허출원", "특허등록", "상표등록", "디자인등록"]:
                    c = st.number_input(f"➤ {pt}건수", min_value=0, step=1, format="%d", key=f"in_{pt}_cnt")
                    for i in range(int(c)): st.text_input(f" - {pt}번호 {i+1}", key=f"in_{pt}_num_{i}")
        with pc2:
            if st.radio("지원사업", ["무", "유"], horizontal=True, key="in_has_gov") == "유":
                c = st.number_input("➤ 건수", min_value=0, step=1, format="%d", key="in_gov_cnt")
                for i in range(int(c)): st.text_input(f" - 사업명 {i+1}", key=f"in_gov_name_{i}")
            st.markdown("---")
            if st.radio("특허매입예정", ["무", "유"], horizontal=True, key="in_buy_patent") == "유":
                st.text_input("희망특허 (명칭)", key="in_buy_pat_desc")
                st.number_input("예상금액(만원)", value=None, step=1, format="%d", key="in_buy_pat_amount")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("8. 비즈니스 정보")
        st.text_area("* [아이템]", key="in_item_desc")
        st.text_input("[생산공정도]", key="in_process_desc")
        st.text_area("* [판매루트]", key="in_sales_route")
        st.text_area("* [앞으로의 계획]", key="in_future_plan")
        st.text_area("[시장현황]", key="in_market_status")
        st.text_area("[차별화]", key="in_diff_point")
        st.success("✅ 세팅 완료! 상단 버튼을 클릭해 리포트를 생성하세요.")
