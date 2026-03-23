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
# 0. 기본 설정 및 보안
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 AI 컨설팅 시스템")
        correct_pw = st.secrets.get("LOGIN_PASSWORD", "1234")
        pw = st.text_input("접속 비밀번호를 입력하세요", type="password")
        if st.button("접속"):
            if pw == correct_pw:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
        return False
    return True

# --- 금액 변환 및 안전 로직 ---
def safe_int(value):
    try:
        clean_val = str(value).replace(',', '').strip()
        if not clean_val: return 0
        return int(float(clean_val))
    except:
        return 0

def format_kr_currency(value):
    try:
        val = safe_int(value)
        if val == 0: return "0원"
        uk = val // 10000
        man = val % 10000
        if uk > 0 and man > 0:
            return f"{uk}억 {man:,}만원"
        elif uk > 0:
            return f"{uk}억원"
        else:
            return f"{man:,}만원"
    except:
        return str(value)

# 사업자번호 및 법인등록번호 자동 포맷팅 함수
def format_biz_no(raw_no):
    no = str(raw_no).replace("-", "").strip()
    if len(no) == 10:
        return f"{no[:3]}-{no[3:5]}-{no[5:]}"
    return raw_no

def format_corp_no(raw_no):
    no = str(raw_no).replace("-", "").strip()
    if len(no) == 13:
        return f"{no[:6]}-{no[6:]}"
    return raw_no

if check_password():
    # --- 파일 관리 (업체 DB) ---
    DB_FILE = "company_db.json"
    
    def load_db():
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: return {}
        return {}
        
    def save_db(db_data):
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db_data, f, ensure_ascii=False, indent=4)

    def get_credit_grade(score, type="NICE"):
        score = safe_int(score)
        if type == "NICE":
            if score >= 900: return 1
            elif score >= 870: return 2
            elif score >= 840: return 3
            elif score >= 805: return 4
            elif score >= 750: return 5
            elif score >= 665: return 6
            elif score >= 600: return 7
            elif score >= 515: return 8
            elif score >= 445: return 9
            else: return 10
        else: # KCB
            if score >= 942: return 1
            elif score >= 891: return 2
            elif score >= 832: return 3
            elif score >= 768: return 4
            elif score >= 698: return 5
            elif score >= 630: return 6
            elif score >= 530: return 7
            elif score >= 454: return 8
            elif score >= 335: return 9
            else: return 10

    # ==========================================
    # 1. 사이드바 (API 설정, 업체관리)
    # ==========================================
    st.sidebar.header("⚙️ AI 엔진 설정")
    if "api_key" not in st.session_state: 
        st.session_state["api_key"] = st.secrets.get("GEMINI_API_KEY", "")
        
    api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
    if st.sidebar.button("💾 API KEY 저장"):
        st.session_state["api_key"] = api_key_input
        st.sidebar.success("✅ 이번 접속 동안 API 키가 유지됩니다.")
        time.sleep(1)
        st.rerun()

    if st.session_state["api_key"]:
        genai.configure(api_key=st.session_state["api_key"])

    st.sidebar.markdown("---")
    st.sidebar.header("📂 업체 관리")
    db = load_db()
    if st.sidebar.button("💾 현재 정보 저장", use_container_width=True):
        c_name = st.session_state.get("in_company_name", "").strip()
        if c_name:
            current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            db[c_name] = current_data
            save_db(db)
            st.sidebar.success(f"✅ '{c_name}' 저장 완료!")

    selected_company = st.sidebar.selectbox("저장된 업체 목록", ["선택 안 함"] + list(db.keys()))
    col_s1, col_s2 = st.sidebar.columns(2)
    with col_s1:
        if st.button("📂 불러오기", use_container_width=True):
            if selected_company != "선택 안 함":
                for k, v in db[selected_company].items(): st.session_state[k] = v
                st.rerun()
    with col_s2:
        if st.button("🔄 초기화", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("in_"): del st.session_state[k]
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🚀 빠른 리포트 생성")
    if st.sidebar.button("📊 1. 기업분석리포트 생성", use_container_width=True):
        st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = "REPORT"
        st.rerun()
    if st.sidebar.button("💡 2. 정책자금 매칭 리포트", use_container_width=True):
        st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = "MATCHING"
        st.rerun()
    if st.sidebar.button("📝 3. 사업계획서 생성", use_container_width=True):
        st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = "PLAN"
        st.rerun()

    # ==========================================
    # 2. 화면 모드 제어 (리포트 vs 대시보드)
    # ==========================================
    if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
    if "permanent_data" not in st.session_state: st.session_state["permanent_data"] = {}

    # ---------------------------------------------------------
    # [모드 A: 1. 기업분석리포트]
    # ---------------------------------------------------------
    if st.session_state["view_mode"] == "REPORT":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력').strip()
        
        st.title("📋 시각화 기반 AI 기업분석 리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")
        
        if not st.session_state["api_key"]:
            st.error("⚠️ 좌측 사이드바에 API 키를 입력하거나, 서버 설정에 키를 등록해주세요.")
        else:
            try:
                with st.status("🚀 잼(Jam)이 가로형 레이아웃으로 완벽한 리포트를 생성 중입니다...", expanded=True) as status:
                    try:
                        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    except Exception as e:
                        raise Exception(f"API 키 권한 오류입니다. (상세: {e})")

                    if 'models/gemini-1.5-flash' in available_models: target_model = 'gemini-1.5-flash'
                    elif 'models/gemini-1.5-pro' in available_models: target_model = 'gemini-1.5-pro'
                    elif 'models/gemini-pro' in available_models: target_model = 'gemini-pro'
                    elif len(available_models) > 0: target_model = available_models[0].replace('models/', '')
                    else: raise Exception("사용 가능한 생성형 모델이 없습니다.")

                    model = genai.GenerativeModel(target_model)
                    
                    c_ind = d.get('in_industry', '미입력')
                    rep_name = d.get('in_rep_name', '미입력')
                    biz_no = format_biz_no(d.get('in_raw_biz_no', '미입력'))
                    corp_no = format_corp_no(d.get('in_raw_corp_no', ''))
                    corp_text = f" (법인: {corp_no})" if corp_no else ""
                    address = d.get('in_biz_addr', '미입력')
                    
                    add_biz_status = d.get('in_has_additional_biz', '무')
                    add_biz_addr = d.get('in_additional_biz_addr', '').strip()
                    if add_biz_status == '유' and add_biz_addr:
                        address += f" <br>(추가사업장: {add_biz_addr})"
                    
                    lease_status = d.get('in_lease_status', '자가')
                    lease_text = "[임대]" if lease_status == '임대' else "[자가]"
                    
                    s_cur = format_kr_currency(d.get('in_sales_current', 0))
                    s_25 = format_kr_currency(d.get('in_sales_2025', 0))
                    s_24 = format_kr_currency(d.get('in_sales_2024', 0))
                    s_23 = format_kr_currency(d.get('in_sales_2023', 0))
                    
                    fund_type = d.get('in_fund_type', '운전자금')
                    req_fund = format_kr_currency(d.get('in_req_amount', 0))
                    
                    item = d.get('in_item_desc', '미입력')
                    market = d.get('in_market_status', '미입력')
                    diff = d.get('in_diff_point', '미입력')
                    
                    val_cur = safe_int(d.get('in_sales_current', 0))
                    if val_cur <= 0: val_cur = 1000
                    start_val = val_cur / 12
                    end_val = start_val * 1.5
                    
                    monthly_vals = []
                    for i in range(12):
                        progress = i / 11.0
                        linear_part = start_val + (end_val - start_val) * progress
                        wave_part = (end_val - start_val) * 0.15 * np.sin(progress * np.pi * 3.5)
                        monthly_vals.append(int(linear_part + wave_part))
                        
                    monthly_labels = [f"{i}월" for i in range(1, 13)]

                    # 화면용 Plotly 그래프 생성
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=monthly_labels, y=monthly_vals, mode='lines+markers+text',
                        text=[format_kr_currency(v) for v in monthly_vals], textposition="top center",
                        textfont=dict(size=11), line=dict(color='#1E88E5', width=4, shape='spline'),
                        marker=dict(size=10, color='#FF5252', line=dict(width=2, color='white'))
                    ))
                    fig.update_layout(
                        title="📈 향후 1년간 월별 예상 매출 상승 곡선", xaxis_title="진행 월", yaxis_title="예상 매출액",
                        xaxis=dict(tickangle=0, showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
                        template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                    )
                    
                    # 다운로드 HTML용 순수 CSS 막대그래프 생성
                    max_val = max(monthly_vals) if max(monthly_vals) > 0 else 1
                    chart_html = f'''
                    <div style="background-color:#f8f9fa; padding:20px; border-radius:15px; border:1px solid #e0e0e0; margin:20px 0; page-break-inside: avoid;">
                        <div style="text-align:center; font-weight:bold; color:#174EA6; margin-bottom:15px; font-size:18px;">📈 향후 1년간 월별 예상 매출 상승 곡선</div>
                        <table style="width:100%; height:180px; border-bottom:2px solid #ccc; border-collapse:collapse; table-layout:fixed;">
                            <tr>
                    '''
                    for val in monthly_vals:
                        height_px = int((val / max_val) * 140) + 5
                        val_str = format_kr_currency(val).replace('만원', '만')
                        chart_html += f'''
                                <td style="vertical-align:bottom; padding:0 5px; border:none;">
                                    <div style="font-size:11px; color:#555; margin-bottom:5px; text-align:center; white-space:nowrap; letter-spacing:-0.5px;">{val_str}</div>
                                    <div style="width:80%; height:{height_px}px; background-color:#1E88E5; border-radius:4px 4px 0 0; margin:0 auto; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"></div>
                                </td>
                        '''
                    chart_html += '''
                            </tr>
                        </table>
                        <table style="width:100%; border-collapse:collapse; table-layout:fixed; margin-top:5px;">
                            <tr>
                    '''
                    for label in monthly_labels:
                        chart_html += f'''
                                <td style="text-align:center; font-size:13px; font-weight:bold; color:#333; padding:5px 0; border:none;">{label}</td>
                        '''
                    chart_html += '''
                            </tr>
                        </table>
                    </div>
                    '''

                    prompt = f"""
                    당신은 20년 경력의 중소기업 경영컨설턴트입니다. 
                    아래 양식과 서식 규칙을 **반드시 100% 똑같이** 지켜서 출력하세요.

                    [작성 규칙 - 절대 엄수!!!]
                    1. 마크다운 사용 금지: 제목이나 강조에 마크다운 기호(##, **, - 등)를 절대 사용하지 마세요. 반드시 제공된 <h2 class="section-title">, <b>, <div>, <table> 등의 HTML 태그만 사용해야 합니다.
                    2. 어투: 모든 문장 끝은 '~있음', '~가능', '~함', '~필요함' 등 명사형(음/슴체)으로 마무리하세요.
                    3. 내용 풍성하게: 외부 지식을 총동원하여 각 항목을 3~4문장 이상으로 매우 상세하게 채우세요. 단, 문장 끝마다 반드시 줄바꿈 &lt;br&gt; 태그를 넣으세요.

                    [기업 정보]
                    - 기업명: {c_name} / 대표자: {rep_name} / 업종: {c_ind}
                    - 아이템: {item} / 시장현황: {market} / 차별화: {diff}
                    - 신청자금: {req_fund} ({fund_type})

                    [출력 양식]
                    <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업현황분석</h2>
                    <table style="width:100%; border-collapse: collapse; font-size: 1.1em;
