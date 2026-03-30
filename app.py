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
# 0. 핵심 헬퍼 함수 (에러 방지 최상단 고정)
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

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
    # AI가 마크다운(```html)을 붙여서 낼 경우를 대비한 강력한 정제 로직
    if "```html" in text:
        text = text.split("```html")[1]
    if "```" in text:
        text = text.split("```")[0]
    return text.strip()

def get_credit_grade(sc, t="NICE"):
    sc = safe_int(sc)
    if sc == 0: return "-"
    if t == "NICE": 
        if sc >= 900: return 1
        elif sc >= 870: return 2
        elif sc >= 840: return 3
        elif sc >= 805: return 4
        elif sc >= 750: return 5
        elif sc >= 665: return 6
        elif sc >= 600: return 7
        elif sc >= 515: return 8
        elif sc >= 445: return 9
        else: return 10
    else: # KCB
        if sc >= 942: return 1
        elif sc >= 891: return 2
        elif sc >= 832: return 3
        elif sc >= 768: return 4
        elif sc >= 698: return 5
        elif sc >= 630: return 6
        elif sc >= 530: return 7
        elif sc >= 454: return 8
        elif sc >= 335: return 9
        else: return 10

def get_ai_model():
    # 무한 로딩(Timeout) 원천 차단을 위해 list_models() 검색 삭제 후 다이렉트 연결
    api_key = st.session_state.get("api_key", "")
    if not api_key: return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-pro')

# --- 데이터 포맷팅 ---
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

class VarObj: pass
def get_common_vars(d):
    v = VarObj()
    g = lambda k, df="": d.get(k, df)
    v.c_name = str(g('in_company_name')).strip()
    v.rep_name, v.biz_type, v.c_ind = g('in_rep_name'), g('in_biz_type'), g('in_industry')
    v.address, v.biz_no, v.corp_no = g('in_biz_addr'), str(g('in_raw_biz_no')), str(g('in_raw_corp_no'))
    v.s_25, v.s_cur = format_kr_currency(g('in_sales_2025', 0)), format_kr_currency(g('in_sales_current', 0))
    v.sales_24, v.sales_23 = format_kr_currency(g('in_sales_2024', 0)), format_kr_currency(g('in_sales_2023', 0))
    v.req_fund, v.fund_type, v.fund_purpose = format_kr_currency(g('in_req_amount', 0)), g('in_fund_type'), g('in_fund_purpose')
    v.item, v.market, v.diff, v.route = g('in_item_desc'), g('in_market_status'), g('in_diff_point'), g('in_sales_route')
    v.lease_status, v.start_date_str = g('in_lease_status'), g('in_start_date')
    v.biz_years = max(0, 2026 - int(v.start_date_str[:4])) if len(v.start_date_str)>=4 else 0
    
    cl = [f"{c}({g(f'in_cert_date_{idx}', '일자미상')})" for idx, c in enumerate(["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]) if d.get(f'in_chk_{idx}')]
    v.cert_status = ", ".join(cl) if cl else "미보유"
    
    pl = []
    if g('in_has_patent') == '유':
        for pt in ["특허출원", "특허등록", "상표등록", "디자인등록"]:
            cnt = safe_int(g(f'in_{pt}_cnt', 0))
            for i in range(cnt):
                pt_num = g(f'in_{pt}_num_{i}', '')
                if pt_num: pl.append(f"{pt}({pt_num})")
                else: pl.append(f"{pt}")
    v.pat_str = ", ".join(pl) if pl else "특허/지재권 미보유"
    
    v.gov_str = f"지원사업 {safe_int(g('in_gov_cnt', 0))}건" if g('in_has_gov') == '유' and safe_int(g('in_gov_cnt', 0)) > 0 else "지원사업 이력 없음"
    v.tax_status, v.fin_status = g('in_tax_status', '무'), g('in_fin_status', '무')
    v.nice_score, v.emp_cnt = safe_int(g('in_nice_score', 0)), safe_int(g('in_employee_count', 0))
    kibo, kodit = safe_int(g('in_debt_kibo', 0)), safe_int(g('in_debt_kodit', 0))
    v.guarantee = "기보 이용중(신보 불가)" if kibo > 0 else ("신보 이용중(기보 불가)" if kodit > 0 else "신보/기보 자유선택 가능")
    v.tot_debt = format_kr_currency(sum([safe_int(g(k, 0)) for k in ['in_debt_kosme', 'in_debt_semas', 'in_debt_koreg', 'in_debt_kodit', 'in_debt_kibo', 'in_debt_etc', 'in_debt_credit', 'in_debt_coll']]))
    v.val_cur, v.career, v.future_plan, v.process_desc = safe_int(g('in_sales_current', 0)), g('in_career'), g('in_future_plan'), g('in_process_desc')
    return v

# ==========================================
# 1. 파일 관리 및 보안 설정
# ==========================================
CONFIG_FILE = "config.json"
DB_FILE = "company_db.json"
def load_config(): return json.load(open(CONFIG_FILE, "r", encoding="utf-8")) if os.path.exists(CONFIG_FILE) else {}
def save_config(d): json.dump(d, open(CONFIG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(d): json.dump(d, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

if "password_correct" not in st.session_state:
    st.title("🔐 AI 컨설팅 시스템")
    pw = st.text_input("접속 비밀번호를 입력하세요", type="password")
    if st.button("접속"):
        if pw == st.secrets.get("LOGIN_PASSWORD", "1234"): 
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("비밀번호가 틀렸습니다.")
    st.stop()

# ==========================================
# 2. 사이드바 구성 및 탭 제어 함수
# ==========================================
st.markdown("""<style>
div.stButton > button { min-height: 55px !important; font-size: 16.5px !important; font-weight: bold !important; }
section[data-testid="stSidebar"] div.stButton > button { min-height: 45px !important; font-size: 12.5px !important; }
.report-container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); color: #333; line-height: 1.6; font-size:15px; }
.report-container table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; border:1px solid #ddd; }
.report-container th, .report-container td { border: 1px solid #ddd; padding: 12px; }
.report-container th { background-color: #f8f9fa; font-weight: bold; text-align: center; }
.report-container h2 { color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 5px; margin-top: 30px; }
.page-break { page-break-before: always; }
</style>""", unsafe_allow_html=True)

config = load_config()
if "api_key" not in st.session_state: st.session_state["api_key"] = config.get("GEMINI_API_KEY", "")
st.sidebar.header("⚙️ AI 엔진 설정")
api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
if st.sidebar.button("💾 API KEY 저장"):
    config["GEMINI_API_KEY"] = api_key_input; save_config(config); st.session_state["api_key"] = api_key_input; st.sidebar.success("저장 완료!")

st.sidebar.markdown("---")
st.sidebar.header("📂 업체 관리")
db = load_db()
if st.sidebar.button("💾 현재 업체 정보 저장", use_container_width=True):
    cn = st.session_state.get("in_company_name", "").strip()
    if cn: 
        if st.session_state.get("view_mode", "INPUT") == "INPUT":
            save_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        else:
            save_data = st.session_state.get("permanent_data", {})
        db[cn] = save_data
        save_db(db); st.sidebar.success(f"✅ '{cn}' 저장 완료!")

selected_company = st.sidebar.selectbox("저장된 업체 목록", ["선택 안 함"] + list(db.keys()))
col_s1, col_s2 = st.sidebar.columns(2)
with col_s1:
    if st.button("📂 불러오기", use_container_width=True) and selected_company != "선택 안 함":
        loaded_data = db[selected_company]
        for k, v in loaded_data.items(): st.session_state[k] = v
        st.session_state["permanent_data"] = loaded_data
        st.session_state["view_mode"] = "INPUT"
        st.rerun()
with col_s2:
    if st.button("🔄 초기화", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("in_"): del st.session_state[k]
        st.session_state.pop("permanent_data", None)
        st.cache_data.clear()
        st.session_state["view_mode"] = "INPUT"
        st.rerun()

def change_mode(target_mode):
    if st.session_state.get("view_mode", "INPUT") == "INPUT":
        if not st.session_state.get("in_company_name", "").strip():
            st.warning("🚨 기업명을 입력해야 분석이 가능합니다.")
            return False
        st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    
    st.session_state["view_mode"] = target_mode
    if target_mode == "REPORT": st.session_state.pop("generated_report", None)
    elif target_mode == "MATCHING": st.session_state.pop("generated_matching", None)
    elif target_mode == "PLAN": 
        st.session_state.pop("kosme_result_html", None)
        st.session_state.pop("semas_result_html", None)
    return True

st.sidebar.markdown("---")
st.sidebar.header("🚀 빠른 리포트 생성")
if st.sidebar.button("📊 AI기업분석리포트", key="side_1", use_container_width=True):
    if change_mode("REPORT"): st.rerun()
if st.sidebar.button("💡 AI 정책자금 매칭리포트", key="side_2", use_container_width=True):
    if change_mode("MATCHING"): st.rerun()
if st.sidebar.button("📝 기관별 융자/사업계획서", key="side_3", use_container_width=True):
    if change_mode("PLAN"): st.rerun()

# ==========================================
# 3. 메인 상단 탭
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t1, t2, t3, t4 = st.columns(4)
with t1: 
    if st.button("📊 AI기업분석리포트", key="top_1", use_container_width=True, type="primary"): 
        if change_mode("REPORT"): st.rerun()
with t2: 
    if st.button("💡 AI 정책자금 매칭리포트", key="top_2", use_container_width=True, type="primary"): 
        if change_mode("MATCHING"): st.rerun()
with t3: 
    if st.button("📝 기관별 융자/사업계획서", key="top_3", use_container_width=True, type="primary"): 
        if change_mode("PLAN"): st.rerun()
with t4: 
    if st.button("📑 AI 사업계획서", key="top_4", use_container_width=True, type="primary"): 
        if change_mode("FULL_PLAN"): st.rerun()
st.markdown("<hr style='margin-top:0px; margin-bottom:20px;'>", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

DL_HTML_BASE = "<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{{font-family:'Malgun Gothic',sans-serif; padding:40px; line-height:1.6; color:#333; max-width:1000px; margin:0 auto; background-color:#fff;}} table{{width:100%;border-collapse:collapse;margin-bottom:20px;font-size:14px;}} th,td{{border:1px solid #ccc;padding:12px;}} th{{background-color:#f8f9fa;font-weight:bold;text-align:center;}} h2{{color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:5px;margin-top:30px;}} .page-break{{page-break-before:always;}}</style></head><body>{content}</body></html>"

# ==========================================
# 4. 리포트 렌더링 화면
# ==========================================
if st.session_state["view_mode"] != "INPUT":
    if st.button("⬅️ 입력 화면으로 돌아가기"): 
        if "permanent_data" in st.session_state:
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
        st.session_state["view_mode"] = "INPUT"
        st.rerun()
    
    v = get_common_vars(st.session_state.get("permanent_data", {}))
    model = get_ai_model()
    
    if not model: 
        st.error("⚠️ 좌측 사이드바에 API 키를 설정해주세요."); st.stop()

    if st.session_state["view_mode"] == "REPORT":
        val_cur = v.val_cur if v.val_cur > 0 else 1000
        m_vals = [int((val_cur/12) + ((val_cur/12)*0.5)*(i/11.0) + ((val_cur/12)*0.5)*0.15*np.sin((i/11.0)*np.pi*3.5)) for i in range(12)]
        fig = go.Figure(go.Scatter(x=[f"{i}월" for i in range(1, 13)], y=m_vals, mode='lines+markers+text', text=[format_kr_currency(x) for x in m_vals], textposition="top center", line=dict(color='#1a73e8', width=4, shape='spline')))
        fig.update_layout(width=800, height=400, template="plotly_white", title="📈 향후 1년 월별 예상 매출")
        plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

        if "generated_report" not in st.session_state:
            with st.status("🚀 AI기업분석리포트는 생성중입니다...") as status:
                try:
                    pr = f"""전문 경영컨설턴트입니다. 
                    반드시 순수 HTML 태그만 사용하여 출력하세요. (마크다운 ```html 금지)
                    [기업명]: {v.c_name}, [업종]: {v.c_ind}, [아이템]: {v.item}
                    '2. 시장 동향 및 아이템 분석' 파트를 당신의 방대한 지식으로 1000자 이상 아주 상세하게 작성하세요.
                    반드시 내용 중간에 [GRAPH_INSERT_POINT] 라는 텍스트를 기재하세요."""
                    
                    res_raw = model.generate_content(pr).text
                    st.session_state["generated_report"] = clean_html(res_raw)
                    status.update(label="✅ 리포트 생성 완료!", state="complete")
                except Exception as e: 
                    status.update(label=f"❌ 오류 발생: {str(e)}", state="error")
                    st.stop()
        
        res = st.session_state.get("generated_report", "")
        if "[GRAPH_INSERT_POINT]" in res:
            parts = res.split("[GRAPH_INSERT_POINT]")
            st.markdown(f"<div class='report-container'>{parts[0]}</div>", unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True)
            if len(parts) > 1: st.markdown(f"<div class='report-container'>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='report-container'>{res}</div>", unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True)

        html_export = DL_HTML_BASE.format(content=res.replace('[GRAPH_INSERT_POINT]', plotly_html))
        st.download_button("📥 리포트 다운로드", html_export, f"{v.c_name}_분석리포트.html", "text/html")

    elif st.session_state["view_mode"] == "MATCHING":
        if "generated_matching" not in st.session_state:
            with st.status("🚀 전년도 매출 기준으로 심사를 진행 중입니다...") as status:
                try:
                    pr = f"""정책자금 전문 컨설턴트입니다. HTML 박스 레이아웃을 사용하세요. (마크다운 금지)
                    [기업명]: {v.c_name}, [매출]: {v.s_25}, [기존보증]: {v.guarantee}, [부채]: {v.tot_debt}
                    위 기업의 스펙에 맞춰 1~4순위 추천 자금 매칭 및 상세 전략을 짜주세요."""
                    
                    st.session_state["generated_matching"] = clean_html(model.generate_content(pr).text)
                    status.update(label="✅ 심사 및 매칭 완료!", state="complete")
                except Exception as e: 
                    status.update(label=f"❌ 오류 발생: {str(e)}", state="error")
                    st.stop()
        
        res = st.session_state.get("generated_matching", "")
        st.markdown(f"<div class='report-container'>{res}</div>", unsafe_allow_html=True)
        
        html_export = DL_HTML_BASE.format(content=res)
        st.download_button("📥 매칭리포트 다운로드", html_export, f"{v.c_name}_매칭리포트.html", "text/html")

    elif st.session_state["view_mode"] == "PLAN":
        st.subheader("📝 기관별 융자/사업계획서 자동 생성")
        tabs = st.tabs(["1. 중소벤처기업진흥공단", "2. 소상공인시장진흥공단"])
        
        with tabs[0]:
            st.markdown("#### 🏢 중소벤처기업진흥공단 (중진공)")
            col_dd1, col_dd2 = st.columns(2)
            with col_dd1: mf = st.selectbox("💡 1. 대분류 자금종류 (중진공)", ["혁신창업화자금", "신시장진출지원자금", "신성장기반자금", "재도약지원자금", "긴급경영안전자금"])
            with col_dd2: 
                if mf == "혁신창업화자금": sf_list = ["청년전용창업자금", "개발기술사업화자금"]
                elif mf == "신시장진출지원자금": sf_list = ["내수기업 수출기업화자금", "수출기업 글로벌화 자금", "수출지원자금"]
                elif mf == "신성장기반자금": sf_list = ["혁신성장지원자금", "스케일업금융자금", "탄소중립전환자금"]
                else: sf_list = [f"{mf} 세부자금"]
                sf = st.selectbox("💡 2. 세부 자금종류 (중진공)", sf_list)
            
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                if st.button("🚀 중진공 융자신청서(공통) 생성", use_container_width=True):
                    with st.status("🚀 융자신청서 렌더링 중...") as status:
                        try:
                            pr = f"컨설턴트. 마크다운 금지. HTML 표. [기업]{v.c_name}/매출:{v.s_cur}/자금:{v.req_fund}/아이템:{v.item}. <h2 style='text-align:center;'>중소기업 정책자금 융자신청서</h2><table style='width:100%; border:1px solid #333;'><tr><th>신청자금</th><td>▣ {sf}</td><th>금액</th><td>{v.req_fund}</td></tr></table> 공정도와 시장상황 상세히."
                            st.session_state["kosme_result_type"] = "loan"
                            st.session_state["kosme_result_html"] = clean_html(model.generate_content(pr).text)
                            status.update(label="✅ 공통 융자신청서 작성 완료!", state="complete")
                        except Exception as e: 
                            status.update(label=f"❌ 오류: {str(e)}", state="error")
            with c_p2:
                if st.button(f"🚀 중진공 {sf} 별첨계획서 생성", use_container_width=True):
                    with st.status("🚀 사업계획서 렌더링 중...") as status:
                        try:
                            pr = f"심사역. 마크다운 금지. HTML. [기업]{v.c_name}/아이템:{v.item}/매출:{v.s_cur}. <h2 style='text-align:center;'>{sf} 사업계획서</h2><h2>1. 사업개요</h2><p>(상세)</p><h2>2. 시장성</h2><p>(상세)</p><h2>3. 추진계획</h2><p>(상세)</p>"
                            st.session_state["kosme_result_type"] = "plan"
                            st.session_state["kosme_result_html"] = clean_html(model.generate_content(pr).text)
                            status.update(label="✅ 별첨 사업계획서 작성 완료!", state="complete")
                        except Exception as e:
                            status.update(label=f"❌ 오류: {str(e)}", state="error")

            if "kosme_result_html" in st.session_state:
                st.divider()
                st.markdown(f"<div class='report-container'>{st.session_state['kosme_result_html']}</div>", unsafe_allow_html=True)
                html_export = DL_HTML_BASE.format(content=st.session_state['kosme_result_html'])
                st.download_button("📥 중진공 서식 다운로드", html_export, f"{v.c_name}_중진공.html", "text/html")

        with tabs[1]:
            st.markdown("#### 🏪 소상공인시장진흥공단 (소진공)")
            semas_fund = st.selectbox("💡 소진공 자금종류 (대분류만 유지)", ["혁신성장촉진자금", "민간투자연계형매칭융자", "상생성장지원자금", "일시적경영애로자금", "신용취약소상공인자금", "재도전특별자금"])
            if st.button(f"🚀 소진공 {semas_fund} 융자/사업계획서(통합) 생성", use_container_width=True):
                with st.status("🚀 소진공 서식 렌더링 중...") as status:
                    try:
                        pr = f"심사역. 마크다운 금지. HTML 표. [기업]{v.c_name}/아이템:{v.item}/매출:{v.s_cur}/자금:{v.req_fund}. <h2 style='text-align:center;'>기업현황 및 사업계획서 ({semas_fund})</h2><table style='width:100%; border:1px solid #ccc;'><tr><th>업체명</th><td>{v.c_name}</td><th>대표</th><td>{v.rep_name}</td></tr></table><h3>사업계획</h3><table style='width:100%; border:1px solid #ccc;'><tr><th>내용/목적</th><td>(상세)</td></tr><tr><th>경쟁력</th><td>(상세)</td></tr></table><h3>자금집행계획</h3><table style='width:100%; border:1px solid #ccc;'><tr><th>총소요</th><td>{v.req_fund}</td></tr></table>"
                        st.session_state["semas_result_html"] = clean_html(model.generate_content(pr).text)
                        status.update(label="✅ 통합 서식 작성 완료!", state="complete")
                    except Exception as e:
                        status.update(label=f"❌ 오류: {str(e)}", state="error")
            
            if "semas_result_html" in st.session_state:
                st.divider()
                st.markdown(f"<div class='report-container'>{st.session_state['semas_result_html']}</div>", unsafe_allow_html=True)
                html_export = DL_HTML_BASE.format(content=st.session_state['semas_result_html'])
                st.download_button("📥 소진공 서식 다운로드", html_export, f"{v.c_name}_소진공.html", "text/html")

    elif st.session_state["view_mode"] == "FULL_PLAN":
        st.title("📑 AI 사업계획서")
        st.info("💡 투자 유치 및 기관 제출을 위한 정식 사업계획서 자동 생성 메뉴입니다. (곧 업데이트 예정)")

# ==========================================
# 5. 메인 폼 (대시보드 입력칸)
# ==========================================
else:
    st.markdown("<p style='color:#1a73e8; font-weight:bold;'>※ 아래 정보를 입력해 주세요.</p>", unsafe_allow_html=True)
    st.header("1. 기업현황")
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        biz_col1, biz_col2 = st.columns([1, 1.2])
        with biz_col1: biz_type = st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
        with biz_col2:
            if biz_type == "법인": st.text_input("법인등록번호", placeholder="숫자만", key="in_raw_corp_no", on_change=cb_format_corp_no)
    with r1c2: st.text_input("기업명", key="in_company_name")
    with r1c3: st.text_input("사업자번호", placeholder="숫자만", key="in_raw_biz_no", on_change=cb_format_biz_no)

    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1: st.text_input("사업개시일", placeholder="YYYYMMDD", key="in_start_date", on_change=cb_format_date, args=("in_start_date",))
    with r2c2: st.text_input("사업장 주소", key="in_biz_addr")
    with r2c3: st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    r3c1, r3c2, r3c3 = st.columns(3)
    with r3c1:
        st.text_input("전화번호", placeholder="숫자만", key="in_biz_tel", on_change=cb_format_phone, args=("in_biz_tel",))
        st.number_input("상시근로자수(명)", value=0, format="%d", key="in_employee_count")
    with r3c2:
        ls = st.radio("임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
        if ls == "임대":
            ilc1, ilc2 = st.columns(2)
            with ilc1: st.number_input("보증금(만)", value=0, key="in_lease_deposit")
            with ilc2: st.number_input("월세(만)", value=0, key="in_lease_rent")
    with r3c3:
        if st.radio("추가사업장", ["무", "유"], horizontal=True, key="in_has_additional_biz") == "유":
            st.text_input("추가 정보", key="in_additional_biz_addr")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    dob = str(st.session_state.get("in_rep_dob", "") or "").replace(".", "")
    is_youth = len(dob)==8 and (2026 - int(dob[:4]) <= 39)
    d_lbl = "생년월일" + (" 🌟 청년" if is_youth else "")
    r4c1, r4c2, r4c3, r4c4 = st.columns(4)
    with r4c1: st.text_input("대표자명", key="in_rep_name")
    with r4c2: st.text_input(d_lbl, placeholder="YYYYMMDD", key="in_rep_dob", on_change=cb_format_date, args=("in_rep_dob",))
    with r4c3: st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")
    with r4c4: st.text_input("휴대폰", placeholder="숫자만", key="in_rep_phone", on_change=cb_format_phone, args=("in_rep_phone",))

    r5c1, r5c2, r5c3 = st.columns([2, 1, 1])
    with r5c1: st.text_input("거주지 주소", key="in_home_addr")
    with r5c2: st.selectbox("최종학력", ["중졸", "고졸", "전문대졸", "대졸", "석사", "박사"], key="in_edu_school")
    with r5c3: st.text_input("전공", key="in_edu_major")

    r6c1, r6c2, r6c3 = st.columns([1, 1, 2])
    with r6c1: st.radio("거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status")
    with r6c2:
        st.text_input("이메일 주소", key="in_rep_email")
        st.multiselect("부동산 현황", ["아파트", "빌라", "단독주택", "토지", "상가", "공장", "기타"], key="in_real_estate")
    with r6c3: st.text_area("경력(최근기준)", key="in_career", height=135)

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 신용 및 연체 정보")
    cr1, cr2 = st.columns([1.2, 1])
    with cr1:
        stc1, stc2 = st.columns(2)
        with stc1: st.radio("세금체납", ["무", "유"], horizontal=True, key="in_tax_status")
        with stc2: st.radio("금융연체", ["무", "유"], horizontal=True, key="in_fin_status")
        sc1, sc2 = st.columns(2)
        with sc1: kcb = st.number_input("KCB 점수", value=0, key="in_kcb_score")
        with sc2: nice = st.number_input("NICE 점수", value=0, key="in_nice_score")
    with cr2:
        kg, ng = get_credit_grade(kcb, 'KCB'), get_credit_grade(nice, 'NICE')
        st.markdown(f"<div style='padding:25px; background:#e8f0fe; border-radius:15px; text-align:center; border:2px solid #a4c2f4; margin-top:10px;'><h3>🏆 신용등급 판정 결과</h3><p style='font-size:30px; font-weight:900;'>KCB: {kg}등급 | NICE: {ng}등급</p></div>", unsafe_allow_html=True)

    st.header("4. 매출현황")
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.number_input("금년 매출(만)", value=0, key="in_sales_current")
    with m2: st.number_input("25년 매출(만)", value=0, key="in_sales_2025")
    with m3: st.number_input("24년 매출(만)", value=0, key="in_sales_2024")
    with m4: st.number_input("23년 매출(만)", value=0, key="in_sales_2023")

    st.header("5. 부채현황")
    d1, d2, d3, d4 = st.columns(4)
    with d1: st.number_input("중진공(만)", value=0, key="in_debt_kosme")
    with d2: st.number_input("소진공(만)", value=0, key="in_debt_semas")
    with d3: st.number_input("신보(만)", value=0, key="in_debt_kodit")
    with d4: st.number_input("기보(만)", value=0, key="in_debt_kibo")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("6. 필요자금")
    p1, p2, p3 = st.columns([1, 1, 2])
    with p1: st.selectbox("자금구분", ["운전자금", "시설자금"], key="in_fund_type")
    with p2: st.number_input("금액(만원)", value=0, key="in_req_amount")
    with p3: st.text_input("용도", key="in_fund_purpose")

    st.header("7. 인증현황")
    certs = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4):
            idx = i + j
            with cols[j]:
                if st.checkbox(certs[idx], key=f"in_chk_{idx}"):
                    st.text_input(f"↪ {certs[idx]} 일자", key=f"in_cert_date_{idx}", on_change=cb_format_date, args=(f"in_cert_date_{idx}",))

    st.header("8. 특허 및 지식재산권")
    pc1, pc2 = st.columns(2)
    with pc1:
        if st.radio("특허보유", ["무", "유"], horizontal=True, key="in_has_patent") == "유":
            for pt in ["특허출원", "특허등록", "상표등록", "디자인등록"]:
                cnt = st.number_input(f"➤ {pt} 건수", min_value=0, step=1, format="%d", key=f"in_{pt}_cnt")
                for i in range(int(cnt)): st.text_input(f"↪ {pt}번호 {i+1}", key=f"in_{pt}_num_{i}")
    with pc2:
        if st.radio("지원사업이력", ["무", "유"], horizontal=True, key="in_has_gov") == "유":
            cnt = st.number_input("➤ 지원사업 건수", min_value=0, step=1, format="%d", key="in_gov_cnt")
            for i in range(int(cnt)): st.text_input(f"↪ 사업명 {i+1}", key=f"in_gov_name_{i}")

    st.header("9. 비즈니스 상세 정보")
    st.text_area("아이템", key="in_item_desc", placeholder="핵심 제품/서비스 설명")
    st.text_input("제품생산공정도", key="in_process_desc", placeholder="예: 원물 입고 -> 세척 -> 포장")
    st.text_area("판매루트", key="in_sales_route")
    st.text_area("시장현황", key="in_market_status")
    st.text_area("차별화", key="in_diff_point")
    st.text_area("앞으로의 계획", key="in_future_plan")
    
    st.success("✅ 세팅 완료! 상단 버튼을 클릭해 리포트를 생성하세요.")
