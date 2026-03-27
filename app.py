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

st.markdown("""
<style>
div.stButton > button { min-height: 55px !important; white-space: nowrap !important; line-height: 1.2 !important; font-size: 16.5px !important; font-weight: bold !important; letter-spacing: -0.3px !important; }
section[data-testid="stSidebar"] div.stButton > button { min-height: 45px !important; font-size: 12.5px !important; white-space: nowrap !important; letter-spacing: -0.5px !important; padding: 0px 10px !important; }
</style>
""", unsafe_allow_html=True)

# --- 콜백 함수: 자동 하이픈(-) 포맷팅 ---
def cb_format_biz_no():
    val = str(st.session_state.get("in_raw_biz_no", "") or "").replace("-", "").replace(".", "").strip()
    if len(val) == 10: st.session_state["in_raw_biz_no"] = f"{val[:3]}-{val[3:5]}-{val[5:]}"

def cb_format_corp_no():
    val = str(st.session_state.get("in_raw_corp_no", "") or "").replace("-", "").replace(".", "").strip()
    if len(val) == 13: st.session_state["in_raw_corp_no"] = f"{val[:6]}-{val[6:]}"

def cb_format_date(key):
    val = str(st.session_state.get(key, "") or "").replace("-", "").replace(".", "").strip()
    if len(val) == 8: st.session_state[key] = f"{val[:4]}.{val[4:6]}.{val[6:]}"

def cb_format_phone(key):
    val = str(st.session_state.get(key, "") or "").replace("-", "").replace(".", "").strip()
    if len(val) == 9: st.session_state[key] = f"{val[:2]}-{val[2:5]}-{val[5:]}"
    elif len(val) == 10:
        if val.startswith("02"): st.session_state[key] = f"{val[:2]}-{val[2:6]}-{val[6:]}"
        else: st.session_state[key] = f"{val[:3]}-{val[3:6]}-{val[6:]}"
    elif len(val) == 11: st.session_state[key] = f"{val[:3]}-{val[3:7]}-{val[7:]}"

# --- 필수 입력 검증 ---
def is_valid_mandatory():
    req_texts = [
        "in_company_name", "in_raw_biz_no", "in_start_date", "in_biz_tel", "in_biz_addr",
        "in_rep_name", "in_rep_dob", "in_rep_phone", "in_rep_email", "in_home_addr",
        "in_real_estate", "in_edu_school", "in_edu_major", "in_career",
        "in_fund_purpose", "in_item_desc", "in_sales_route", "in_future_plan"
    ]
    if st.session_state.get("in_biz_type") == "법인": req_texts.append("in_raw_corp_no")
        
    for k in req_texts:
        if not str(st.session_state.get(k, "") or "").strip(): return False
            
    req_nums = [
        "in_employee_count", "in_kcb_score", "in_nice_score",
        "in_sales_current", "in_sales_2025", "in_sales_2024",
        "in_debt_kosme", "in_debt_semas", "in_debt_koreg", "in_debt_kodit",
        "in_debt_kibo", "in_debt_etc", "in_debt_credit", "in_debt_coll", "in_req_amount"
    ]
    if st.session_state.get("in_lease_status") == "임대":
        req_nums.extend(["in_lease_deposit", "in_lease_rent"])
        
    for k in req_nums:
        if st.session_state.get(k) is None: return False
    return True

# --- 설정 및 DB 로직 ---
CONFIG_FILE = "config.json"
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 AI 컨설팅 시스템")
        correct_pw = st.secrets.get("LOGIN_PASSWORD", "1234")
        pw = st.text_input("접속 비밀번호를 입력하세요", type="password")
        if st.button("접속"):
            if pw == correct_pw:
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("비밀번호가 틀렸습니다.")
        return False
    return True

def safe_int(value):
    try:
        if value is None: return 0
        clean_val = str(value).replace(',', '').strip()
        if not clean_val: return 0
        return int(float(clean_val))
    except: return 0

def format_kr_currency(value):
    try:
        val = safe_int(value)
        if val == 0: return "0원"
        uk = val // 10000
        man = val % 10000
        if uk > 0 and man > 0: return f"{uk}억 {man:,}만원"
        elif uk > 0: return f"{uk}억원"
        else: return f"{man:,}만원"
    except: return str(value)

def get_best_model_name():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if 'models/gemini-1.5-flash' in available: return 'gemini-1.5-flash'
        if 'models/gemini-1.5-pro' in available: return 'gemini-1.5-pro'
        if 'models/gemini-1.0-pro' in available: return 'gemini-1.0-pro'
        if 'models/gemini-pro' in available: return 'gemini-pro'
        if available: return available[0].replace('models/', '')
    except: pass
    return 'gemini-pro'

def clean_html_output(raw_text):
    clean_text = raw_text.replace("```html", "").replace("```", "").strip()
    return "\n".join([line.lstrip() for line in clean_text.split("\n")])

if check_password():
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
        else:
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
    config = load_config()
    if "api_key" not in st.session_state: 
        st.session_state["api_key"] = config.get("GEMINI_API_KEY", st.secrets.get("GEMINI_API_KEY", ""))
        
    api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
    if st.sidebar.button("💾 API KEY 저장"):
        st.session_state["api_key"] = api_key_input
        config["GEMINI_API_KEY"] = api_key_input
        save_config(config)
        st.sidebar.success("✅ API 키가 영구적으로 저장되었습니다.")
        time.sleep(1)
        st.rerun()

    if st.session_state["api_key"]: genai.configure(api_key=st.session_state["api_key"])

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
    
    if st.sidebar.button("📊 AI 기업분석리포트", use_container_width=True):
        if not is_valid_mandatory(): st.sidebar.error("🚨 대시보드의 필수 입력란(*필수)을 모두 채워주세요.")
        else:
            if st.session_state.get("view_mode", "INPUT") == "INPUT":
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "REPORT"
            st.session_state.pop("generated_report", None)
            st.rerun()
        
    if st.sidebar.button("💡 AI 정책자금 매칭리포트", use_container_width=True):
        if not is_valid_mandatory(): st.sidebar.error("🚨 대시보드의 필수 입력란(*필수)을 모두 채워주세요.")
        else:
            if st.session_state.get("view_mode", "INPUT") == "INPUT":
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "MATCHING"
            st.session_state.pop("generated_matching", None)
            st.rerun()
        
    if st.sidebar.button("📝 융자·사업계획서 맞춤형 AI 생성", use_container_width=True):
        if not is_valid_mandatory(): st.sidebar.error("🚨 대시보드의 필수 입력란(*필수)을 모두 채워주세요.")
        else:
            if st.session_state.get("view_mode", "INPUT") == "INPUT":
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "PLAN"
            st.session_state.pop("kosme_result_html", None)
            st.session_state.pop("semas_result_html", None)
            st.rerun()
        
    if st.sidebar.button("📑 AI 사업계획서", use_container_width=True):
        if not is_valid_mandatory(): st.sidebar.error("🚨 대시보드의 필수 입력란(*필수)을 모두 채워주세요.")
        else:
            if st.session_state.get("view_mode", "INPUT") == "INPUT":
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "FULL_PLAN"
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
            for k, v in st.session_state["permanent_data"].items(): st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력').strip()
        
        st.title("📋 AI기업분석리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")
        
        if not st.session_state["api_key"]: st.error("⚠️ 좌측 사이드바에 API 키를 입력하거나, 서버 설정에 키를 등록해주세요.")
        else:
            try:
                biz_type = d.get('in_biz_type', '개인')
                c_ind = d.get('in_industry', '미입력')
                rep_name = d.get('in_rep_name', '미입력')
                biz_no = str(d.get('in_raw_biz_no', '미입력'))
                corp_no = str(d.get('in_raw_corp_no', ''))
                corp_text = f"<br><span style='font-size:0.9em; color:#555;'>({corp_no})</span>" if corp_no else ""
                address = d.get('in_biz_addr', '미입력')
                
                add_biz_status = d.get('in_has_additional_biz', '무')
                add_biz_addr = d.get('in_additional_biz_addr', '').strip()
                add_biz_row = f"<tr><td style='padding:15px; background-color:#eceff1; font-size:0.95em; white-space:nowrap;'><b>추가사업장</b></td><td colspan='5' style='padding:15px; text-align:left;'>{add_biz_addr}</td></tr>" if add_biz_status == '유' and add_biz_addr else ""
                
                s_cur = format_kr_currency(d.get('in_sales_current', 0))
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

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=monthly_labels, y=monthly_vals, mode='lines+markers+text', text=[format_kr_currency(v) for v in monthly_vals], textposition="top center", textfont=dict(size=11), line=dict(color='#1E88E5', width=4, shape='spline'), marker=dict(size=10, color='#FF5252', line=dict(width=2, color='white'))))
                fig.update_layout(title="📈 향후 1년간 월별 예상 매출 상승 곡선", xaxis_title="진행 월", yaxis_title="예상 매출액", xaxis=dict(tickangle=0, showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e0e0'), template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
                
                certs_names = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
                certs_list = [f"{cert}({d.get(f'in_cert_date_{i}', '일자미상')})" for i, cert in enumerate(certs_names) if d.get(f"in_chk_{i}", False)]
                cert_status = ", ".join(certs_list) if certs_list else "미보유"
                
                pat_str = ""
                if d.get('in_has_patent') == '유':
                    pat_types = ["특허출원", "특허등록", "상표등록", "디자인등록"]
                    pat_parts = [f"{pt} {safe_int(d.get(f'in_{pt}_cnt', 0))}건({', '.join([d.get(f'in_{pt}_num_{i}', '') for i in range(safe_int(d.get(f'in_{pt}_cnt', 0)))])})" for pt in pat_types if safe_int(d.get(f"in_{pt}_cnt", 0)) > 0]
                    if pat_parts: pat_str += " ".join(pat_parts)
                if not pat_str: pat_str = "특허/지재권 미보유"
                
                gov_str = ""
                if d.get('in_has_gov') == '유':
                    gov_cnt = safe_int(d.get('in_gov_cnt', 0))
                    if gov_cnt > 0: gov_str = f"지원사업 {gov_cnt}건({', '.join([d.get(f'in_gov_name_{i}', '') for i in range(gov_cnt)])})"
                if not gov_str: gov_str = "지원사업 이력 없음"

                if "generated_report" not in st.session_state:
                    with st.status("🚀 리포트 분석 및 렌더링 중...", expanded=True) as status:
                        st.write("⏳ 1/3: 기업 재무 데이터 및 인증 정보 연동 중...")
                        time.sleep(1)
                        st.write("⏳ 2/3: 경영컨설턴트 모델 로직 분석 중...")
                        time.sleep(1)
                        st.write("⏳ 3/3: 리포트 서식 생성 중... (약 15~30초 소요)")
                        try:
                            model = genai.GenerativeModel(get_best_model_name())
                            prompt = f"""
                            당신은 20년 경력의 중소기업 경영컨설턴트입니다. 
                            [작성 규칙] 마크다운 금지. 명사형 종결. 외부 지식 동원 3~4문장 상세히. &bull;와 <b>로 핵심 강조. 줄바꿈 <br> 필수.
                            [기업 정보] 기업명: {c_name} / 대표자: {rep_name} / 업종: {c_ind} / 사업자유형: {biz_type} / 아이템: {item} / 시장현황: {market} / 차별화: {diff} / 신청자금: {req_fund} ({fund_type}) / 인증현황: {cert_status} / 지식재산권: {pat_str} / 정부지원사업: {gov_str}

                            [출력 양식]
                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업현황분석</h2>
                            <table style="width:100%; border-collapse: collapse; font-size: 1.05em; background-color:#f8f9fa; border-radius:15px; overflow:hidden; margin-bottom:15px; text-align:center;">
                              <tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:15px; width:12%; background-color:#eceff1;"><b>기업명</b></td><td style="padding:15px; width:21%;">{c_name}</td><td style="padding:15px; width:12%; background-color:#eceff1;"><b>사업자유형</b></td><td style="padding:15px; width:21%;">{biz_type}</td><td style="padding:15px; width:12%; background-color:#eceff1;"><b>업종</b></td><td style="padding:15px; width:22%;">{c_ind}</td></tr>
                              <tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:15px; background-color:#eceff1;"><b>대표자명</b></td><td style="padding:15px;">{rep_name}</td><td style="padding:15px; background-color:#eceff1;"><b>사업자번호</b></td><td style="padding:15px; line-height:1.4;">{biz_no}{corp_text}</td><td style="padding:15px; background-color:#eceff1;"><b>사업장주소</b></td><td style="padding:15px;">{address}</td></tr>
                              <tr><td style="padding:15px; background-color:#eceff1;"><b>인증현황</b></td><td colspan="2" style="padding:15px; text-align:left;">{cert_status}</td><td style="padding:15px; background-color:#eceff1;"><b>지식재산/지원사업</b></td><td colspan="2" style="padding:15px; text-align:left; line-height:1.5;">{pat_str}<br>{gov_str}</td></tr>
                              {add_biz_row}
                            </table>
                            <div style="margin-bottom:15px;">(해당 업종과 아이템의 잠재력, 향후 긍정적인 기대감을 외부 지식을 활용하여 3~4문장 이상 상세히 작성. 마침표 뒤 줄바꿈 &lt;br&gt;)</div>

                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. SWOT 분석</h2>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:15px; table-layout: fixed;">
                              <tr><td style="background-color:#e3f2fd; padding:20px; border-radius:15px; vertical-align:top; width:48.5%;"><b>S (강점)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(상세 분석)</div></td><td style="width:3%;"></td><td style="background-color:#ffebee; padding:20px; border-radius:15px; vertical-align:top; width:48.5%;"><b>W (약점)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(상세 분석)</div></td></tr>
                            </table>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:15px; table-layout: fixed;">
                              <tr><td style="background-color:#e8f5e9; padding:20px; border-radius:15px; vertical-align:top; width:48.5%;"><b>O (기회)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(상세 분석)</div></td><td style="width:3%;"></td><td style="background-color:#fff3e0; padding:20px; border-radius:15px; vertical-align:top; width:48.5%;"><b>T (위협)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(상세 분석)</div></td></tr>
                            </table>

                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 시장현황 및 경쟁력 비교</h2>
                            <div style="background-color:#f3e5f5; padding:20px; border-radius:15px; margin-bottom:15px;"><b>📊 시장 현황 분석</b><br><br>&bull; (해당 업종 시장 트렌드를 동원하여 상세 요약)</div>
                            <div style="margin-top:15px; padding:15px; background-color:#fff; border-radius:15px; border:1px solid #e0e0e0;">
                              <b>⚔️ 주요 경쟁사 비교 분석표</b><br>
                              <table style="width:100%; border-collapse: collapse; text-align:center; font-size:0.95em; margin-top:10px;">
                                <tr style="background-color:#eceff1;"><th style="padding:12px; border:1px solid #ccc; width:20%;">비교 항목</th><th style="padding:12px; border:1px solid #ccc; width:26%;">{c_name} (자사)</th><th style="padding:12px; border:1px solid #ccc; width:27%;">주요 경쟁사 A<br><span style="font-size:0.85em; font-weight:normal; color:#555;">(경쟁사 특징 기재)</span></th><th style="padding:12px; border:1px solid #ccc; width:27%;">주요 경쟁사 B<br><span style="font-size:0.85em; font-weight:normal; color:#555;">(경쟁사 특징 기재)</span></th></tr>
                                <tr><td style="padding:12px; border:1px solid #ccc; font-weight:bold;">핵심 타겟/<br>포지셔닝</td><td style="padding:12px; border:1px solid #ccc;">(자사 강점 요약)</td><td style="padding:12px; border:1px solid #ccc;">(경쟁사 A 특징)</td><td style="padding:12px; border:1px solid #ccc;">(경쟁사 B 특징)</td></tr>
                                <tr><td style="padding:12px; border:1px solid #ccc; font-weight:bold;">차별화 요소<br><span style="font-size:0.85em; font-weight:normal; color:#555;">(경쟁우위)</span></td><td style="padding:12px; border:1px solid #ccc;">(자사만의 기술/서비스)</td><td style="padding:12px; border:1px solid #ccc;">(경쟁사 A 비교점)</td><td style="padding:12px; border:1px solid #ccc;">(경쟁사 B 비교점)</td></tr>
                              </table>
                            </div>

                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 핵심경쟁력분석</h2>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:15px; text-align:center; table-layout: fixed;">
                              <tr>
                                <td style="border:1px solid #e0e0e0; border-radius:15px; padding:0; vertical-align:top; overflow:hidden; width:31.3%;"><div style="background-color:#e0f7fa; padding:15px; font-weight:bold; font-size:1.0em; border-bottom:1px solid #e0e0e0;">포인트 1<br><span style="font-size:1.15em; color:#00838F;">(핵심키워드 작성)</span></div><div style="padding:20px; font-size:0.95em; text-align:left; line-height:1.6;">&bull; (구체적 분석)</div></td><td style="width:3%;"></td>
                                <td style="border:1px solid #e0e0e0; border-radius:15px; padding:0; vertical-align:top; overflow:hidden; width:31.3%;"><div style="background-color:#e0f7fa; padding:15px; font-weight:bold; font-size:1.0em; border-bottom:1px solid #e0e0e0;">포인트 2<br><span style="font-size:1.15em; color:#00838F;">(핵심키워드 작성)</span></div><div style="padding:20px; font-size:0.95em; text-align:left; line-height:1.6;">&bull; (구체적 분석)</div></td><td style="width:3%;"></td>
                                <td style="border:1px solid #e0e0e0; border-radius:15px; padding:0; vertical-align:top; overflow:hidden; width:31.3%;"><div style="background-color:#e0f7fa; padding:15px; font-weight:bold; font-size:1.0em; border-bottom:1px solid #e0e0e0;">포인트 3<br><span style="font-size:1.15em; color:#00838F;">(핵심키워드 작성)</span></div><div style="padding:20px; font-size:0.95em; text-align:left; line-height:1.6;">&bull; (구체적 분석)</div></td>
                              </tr>
                            </table>

                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">5. 자금 사용계획 (총 신청자금: {req_fund})</h2>
                            <table style="width:100%; border-collapse: collapse; text-align:left; margin-bottom:15px;">
                             <tr style="background-color:#eceff1;"><th style="padding:15px; border:1px solid #ccc; width:20%; text-align:center;">구분 ({fund_type})</th><th style="padding:15px; border:1px solid #ccc; width:60%;">상세 사용계획 (외부 데이터 기반 구체적 산출)</th><th style="padding:15px; border:1px solid #ccc; width:20%; text-align:center;">사용예정금액</th></tr>
                             <tr><td style="padding:15px; border:1px solid #ccc; font-weight:bold; text-align:center;">(세부항목)<br>및<br>(용도)</td><td style="padding:15px; border:1px solid #ccc;">&bull; (구체적 기재)</td><td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0; text-align:center;">(금액)</td></tr>
                             <tr><td style="padding:15px; border:1px solid #ccc; font-weight:bold; text-align:center;">(세부항목)<br>및<br>(용도)</td><td style="padding:15px; border:1px solid #ccc;">&bull; (구체적 기재)</td><td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0; text-align:center;">(금액)</td></tr>
                             <tr><td style="padding:15px; border:1px solid #ccc; font-weight:bold; text-align:center;">(세부항목)<br>및<br>(용도)</td><td style="padding:15px; border:1px solid #ccc;">&bull; (구체적 기재)</td><td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0; text-align:center;">(금액)</td></tr>
                            </table>

                            <div style="page-break-before: always; page-break-inside: avoid; display: block; width: 100%;">
                                <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:0; font-size:24px; font-weight:bold;">6. 매출 1년 전망</h2>
                                <table style="width:100%; border-collapse: collapse; margin-bottom:15px; text-align:center; table-layout: fixed;">
                                  <tr>
                                    <td style="background-color:#e8eaf6; padding:20px; border-radius:15px; vertical-align:top; width:22.75%;"><div style="font-size:1.2em; font-weight:bold; color:#1565c0; margin-bottom:10px;">1단계 (도입)</div><div style="font-size:0.95em; text-align:left; line-height:1.6; margin-bottom:15px;">&bull; (전략 요약)</div><div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">목표: OOO만원</div></td><td style="width:3%;"></td>
                                    <td style="background-color:#e8eaf6; padding:20px; border-radius:15px; vertical-align:top; width:22.75%;"><div style="font-size:1.2em; font-weight:bold; color:#1565c0; margin-bottom:10px;">2단계 (성장)</div><div style="font-size:0.95em; text-align:left; line-height:1.6; margin-bottom:15px;">&bull; (전략 요약)</div><div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">목표: OOO만원</div></td><td style="width:3%;"></td>
                                    <td style="background-color:#e8eaf6; padding:20px; border-radius:15px; vertical-align:top; width:22.75%;"><div style="font-size:1.2em; font-weight:bold; color:#1565c0; margin-bottom:10px;">3단계 (확장)</div><div style="font-size:0.95em; text-align:left; line-height:1.6; margin-bottom:15px;">&bull; (전략 요약)</div><div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">목표: OOO만원</div></td><td style="width:3%;"></td>
                                    <td style="background-color:#e8eaf6; padding:20px; border-radius:15px; vertical-align:top; width:22.75%;"><div style="font-size:1.2em; font-weight:bold; color:#1565c0; margin-bottom:10px;">4단계 (안착)</div><div style="font-size:0.95em; text-align:left; line-height:1.6; margin-bottom:15px;">&bull; (전략 요약)</div><div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">최종목표: OOO만원</div></td>
                                  </tr>
                                </table>
                                [GRAPH_INSERT_POINT]
                            </div>

                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">7. 성장비전 및 AI 컨설턴트 코멘트</h2>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:20px; text-align:center; table-layout: fixed;">
                              <tr>
                                <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; vertical-align:top; width:31.3%;"><b style="font-size:1.1em;">🌱 단기 비전</b><br><br><div style="text-align:left; line-height:1.6;">&bull; (핵심 비전)</div></td><td style="width:3%;"></td>
                                <td style="background-color:#fff3e0; padding:20px; border-radius:15px; vertical-align:top; width:31.3%;"><b style="font-size:1.1em;">🚀 중기 비전</b><br><br><div style="text-align:left; line-height:1.6;">&bull; (핵심 비전)</div></td><td style="width:3%;"></td>
                                <td style="background-color:#ffebee; padding:20px; border-radius:15px; vertical-align:top; width:31.3%;"><b style="font-size:1.1em;">👑 장기 비전</b><br><br><div style="text-align:left; line-height:1.6;">&bull; (핵심 비전)</div></td>
                              </tr>
                            </table>
                            <div style="background-color:#eeeeee; border-left:5px solid #1565c0; padding:20px; border-radius:15px; margin-top:15px; line-height:1.6;">
                              <b>💡 핵심 인증 및 특허 확보 조언:</b><br><br>&bull; (업종 필수 인증 전략)<br>&bull; (지식재산권 전략)
                            </div>
                            """
                            
                            response = model.generate_content(prompt)
                            st.session_state["generated_report"] = response.text
                            status.update(label="✅ AI기업분석리포트 생성 완료!", state="complete")
                            st.balloons()
                        except Exception as e:
                            status.update(label=f"❌ 오류가 발생했습니다. (상세: {str(e)})", state="error")
                            st.stop()

                response_text = clean_html_output(st.session_state.get("generated_report", ""))

                if "[GRAPH_INSERT_POINT]" in response_text:
                    parts = response_text.partition("[GRAPH_INSERT_POINT]")
                    st.markdown(parts[0], unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown("<br><br>", unsafe_allow_html=True) 
                    st.markdown(parts[2], unsafe_allow_html=True)
                else:
                    st.markdown(response_text, unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)

                st.divider()
                st.subheader("💾 리포트 저장")
                safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
                if not safe_file_name: safe_file_name = "업체"
                
                html_export = f"""
                <!DOCTYPE html><html><head><meta charset="utf-8"><title>{c_name} AI기업분석리포트</title>
                <style>* {{ box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f4f4; padding: 40px 0; margin: 0; }}
                .document-container {{ max-width: 900px; margin: 0 auto; background-color: #fff; padding: 60px; box-shadow: 0 0 15px rgba(0,0,0,0.1); border-radius: 8px; color: #333; line-height: 1.6; font-size: 16px; white-space: pre-wrap; }}
                h1 {{ color: #111; text-align: center; margin-bottom: 40px; font-size: 32px; font-weight: bold; }}
                @media print {{ @page {{ size: A4; margin: 15mm; }} body {{ background-color: #fff; padding: 0 !important; font-size: 14px !important; color: black !important; max-width: 100% !important; }} 
                .document-container {{ box-shadow: none; padding: 0; max-width: 100%; border-radius: 0; }} h1 {{ margin: 0 0 30px 0 !important; font-size: 28px !important; }}
                h2.section-title {{ page-break-before: always !important; margin-top: 0 !important; font-size: 20px !important; padding-bottom: 4px !important; border-bottom: 2px solid #174EA6 !important; }}
                h2.section-title:first-of-type {{ page-break-before: avoid !important; margin-top: 20px !important; }}
                table {{ font-size: 13px !important; margin-bottom: 10px !important; width: 100% !important; table-layout: fixed !important; }}
                th, td {{ padding: 10px !important; word-wrap: break-word; vertical-align: top; }} }}</style></head>
                <body><div class="document-container"><h1>📋 AI기업분석리포트: {c_name}</h1><hr style="margin-bottom: 30px;">
                {response_text.replace('[GRAPH_INSERT_POINT]', plotly_html)}</div></body></html>
                """
                st.download_button(label="📥 리포트 HTML 파일로 다운로드", data=html_export, file_name=f"{safe_file_name}_기업분석리포트.html", mime="text/html", type="primary")
            except Exception as e:
                st.error(f"❌ 시스템 오류 발생: {str(e)}")

    # ---------------------------------------------------------
    # [모드 B: 2. 정책자금 매칭 리포트]
    # ---------------------------------------------------------
    elif st.session_state["view_mode"] == "MATCHING":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items(): st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력').strip()
        tax_status = d.get('in_tax_status', '무')
        fin_status = d.get('in_fin_status', '무')
        
        st.title("🎯 AI 정책자금 최적화 매칭 리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")
        
        if tax_status == '유' or fin_status == '유':
            st.error("🚨 세금체납 및 금융연체가 있을 시 자금 매칭이 진행되지 않습니다.")
        elif not st.session_state["api_key"]:
            st.error("⚠️ 좌측 사이드바에 API 키를 입력하세요.")
        else:
            try:
                if "generated_matching" not in st.session_state:
                    with st.status("🚀 매칭 심사 및 리포트 생성 중...", expanded=True) as status:
                        st.write("⏳ 1/3: 기업 재무 데이터 및 기대출 내역 로딩 중...")
                        time.sleep(1)
                        st.write("⏳ 2/3: 중진공/보증기관 지원 가능 여부 필터링 중...")
                        time.sleep(1)
                        st.write("⏳ 3/3: 최적 자금 매칭 로직 적용 중... (약 15~30초 소요)")
                        try:
                            model = genai.GenerativeModel(get_best_model_name())
                            
                            kibo_debt = safe_int(d.get('in_debt_kibo', 0))
                            kodit_debt = safe_int(d.get('in_debt_kodit', 0))
                            guarantee_status = "기보 이용중(신보 불가)" if kibo_debt > 0 else ("신보 이용중(기보 불가)" if kodit_debt > 0 else "신보/기보 자유선택 가능")
                            total_debt_val = sum([safe_int(d.get(k, 0)) for k in ['in_debt_kosme', 'in_debt_semas', 'in_debt_koreg', 'in_debt_kodit', 'in_debt_kibo', 'in_debt_etc', 'in_debt_credit', 'in_debt_coll']])
                            total_debt = format_kr_currency(total_debt_val)
                            
                            s_25 = format_kr_currency(d.get('in_sales_2025', 0))
                            c_ind, biz_type = d.get('in_industry', '미입력'), d.get('in_biz_type', '개인')
                            nice_score = safe_int(d.get('in_nice_score', 0))
                            req_fund = format_kr_currency(d.get('in_req_amount', 0))
                            
                            certs_names = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
                            certs_list = [f"{cert}({d.get(f'in_cert_date_{i}', '일자미상')})" for i, cert in enumerate(certs_names) if d.get(f"in_chk_{i}", False)]
                            cert_status = ", ".join(certs_list) if certs_list else "미보유"
                            
                            pat_str = ""
                            if d.get('in_has_patent') == '유':
                                pat_types = ["특허출원", "특허등록", "상표등록", "디자인등록"]
                                pat_parts = [f"{pt} {safe_int(d.get(f'in_{pt}_cnt', 0))}건" for pt in pat_types if safe_int(d.get(f"in_{pt}_cnt", 0)) > 0]
                                if pat_parts: pat_str += " ".join(pat_parts)
                            if not pat_str: pat_str = "특허/지재권 미보유"
                            
                            gov_str = f"지원사업 {safe_int(d.get('in_gov_cnt', 0))}건" if d.get('in_has_gov') == '유' and safe_int(d.get('in_gov_cnt', 0)) > 0 else "지원사업 이력 없음"
                            
                            biz_years = max(0, 2026 - int(d.get('in_start_date', '2026')[:4])) if d.get('in_start_date', '').strip() else 0
                            employee_count = safe_int(d.get('in_employee_count', 0))
                            
                            prompt = f"""
                            당신은 전문 경영컨설턴트입니다. 마크다운 기호 금지. 모든 문장은 명사형 종결. 
                            [입력] 기업명:{c_name} / 업종:{c_ind} / 상시근로자:{employee_count}명 / 전년매출:{s_25} / 총기대출:{total_debt} / 인증현황:{cert_status} / 특허:{pat_str} / 희망필요자금:{req_fund}
                            
                            [자금 추천 룰]
                            1. 보증기관 중복 금지: 현재 {guarantee_status}.
                            2. 1페이지 출력 제한으로 내용은 핵심만 1~2줄 간결 작성.
                            
                            [출력 양식]
                            <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업 스펙 진단 요약</h2>
                            <div style="background-color:#f8f9fa; padding:20px; border-radius:15px; border:1px solid #e0e0e0; margin-bottom:15px;">
                              <b>기업명:</b> {c_name} | <b>업종:</b> {c_ind} | <b>업력:</b> 약 {biz_years}년 | <b>근로자:</b> {employee_count}명 <br>
                              <b>인증:</b> {cert_status} | <b>특허:</b> {pat_str} | <b>정부지원:</b> {gov_str} <br>
                              <b>전년도매출:</b> <span style="color:#1565c0; font-weight:bold;">{s_25}</span> | <b>총 기대출:</b> <span style="color:red;">{total_debt}</span> | <b style="font-size:1.15em;">희망 필요자금: {req_fund}</b>
                            </div>
                            <div style="margin-bottom:20px;">(1~2줄 짧은 요약)</div>

                            <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. 우선순위 추천 정책자금 (1~2순위)</h2>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:15px; table-layout: fixed;">
                              <tr><td style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32; vertical-align:top; width:48.5%;"><b style="font-size:1.2em; color:#2e7d32;">🥇 1순위: [기관명] / [세부자금]<br>예상 한도</b><br><br>&bull; (사유 1줄)<br>&bull; (전략 1줄)</td><td style="width:3%;"></td><td style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32; vertical-align:top; width:48.5%;"><b style="font-size:1.2em; color:#2e7d32;">🥈 2순위: [신보/기보 택1] / [상품명]<br>예상 한도</b><br><br>&bull; (사유 1줄)<br>&bull; (전략 1줄)</td></tr>
                            </table>

                            <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 후순위 추천 (플랜 B)</h2>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:15px; table-layout: fixed;">
                              <tr><td style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00; vertical-align:top; width:48.5%;"><b style="font-size:1.2em; color:#ef6c00;">🥉 3순위: [지역신보]<br>예상 한도</b><br><br>&bull; (사유 1줄)<br>&bull; (전략 1줄)</td><td style="width:3%;"></td><td style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00; vertical-align:top; width:48.5%;"><b style="font-size:1.2em; color:#ef6c00;">🏅 4순위: [시중은행 등]<br>예상 한도</b><br><br>&bull; (사유 1줄)<br>&bull; (전략 1줄)</td></tr>
                            </table>

                            <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 심사 전 필수 체크리스트 및 보완 가이드</h2>
                            <div style="background-color:#ffebee; border-left:5px solid #d32f2f; padding:15px; border-radius:15px; margin-top:15px;"><b style="font-size:1.1em; color:#c62828;">🚨 보완 조언:</b><br><br>&bull; (특허/인증 활용 전략 1줄)<br>&bull; (추가 전략 1줄)</div>
                            """
                            
                            response = model.generate_content(prompt)
                            st.session_state["generated_matching"] = response.text
                            status.update(label="✅ 매칭 리포트 생성 완료!", state="complete")
                            st.balloons()
                        except Exception as e:
                            status.update(label=f"❌ 오류 발생. (상세: {str(e)})", state="error")
                            st.stop()
                
                response_text = clean_html_output(st.session_state.get("generated_matching", ""))
                st.markdown(response_text, unsafe_allow_html=True)
                
                st.divider()
                st.subheader("💾 리포트 저장")
                safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
                if not safe_file_name: safe_file_name = "업체"
                html_export = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{c_name} 매칭 리포트</title><style>* {{ box-sizing: border-box; }} body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f4f4; padding: 40px 0; margin: 0; }} .document-container {{ max-width: 900px; margin: 0 auto; background-color: #fff; padding: 60px; border-radius: 8px; line-height: 1.5; white-space: pre-wrap; }} table {{ width: 100%; border-collapse: collapse; }} td, th {{ padding: 8px !important; vertical-align: top; }}</style></head><body><div class="document-container"><h1>🎯 AI 정책자금 매칭 리포트: {c_name}</h1><hr>{response_text}</div></body></html>"""
                st.download_button(label="📥 매칭 리포트 HTML 다운로드", data=html_export, file_name=f"{safe_file_name}_매칭리포트.html", mime="text/html", type="primary")

            except Exception as e:
                st.error(f"❌ 분석 중 오류 발생: {str(e)}")

    # ---------------------------------------------------------
    # [모드 C: 3. 기관 맞춤형 융자/사업계획서 생성]
    # ---------------------------------------------------------
    elif st.session_state["view_mode"] == "PLAN":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items(): st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
            
        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력').strip()
        rep_name = d.get('in_rep_name', '미입력')
        biz_type = d.get('in_biz_type', '미입력')
        c_ind = d.get('in_industry', '미입력')
        address = d.get('in_biz_addr', '미입력')
        career = d.get('in_career', '미입력')
        edu_school = d.get('in_edu_school', '')
        edu_major = d.get('in_edu_major', '')
        home_addr = d.get('in_home_addr', '')
        process_desc = d.get('in_process_desc', '미입력')
        biz_no = str(d.get('in_raw_biz_no', '미입력'))
        
        s_25 = format_kr_currency(d.get('in_sales_2025', 0))
        s_cur = format_kr_currency(d.get('in_sales_current', 0))
        sales_24 = format_kr_currency(d.get('in_sales_2024', 0))
        sales_23 = format_kr_currency(d.get('in_sales_2023', 0))
        
        req_fund = format_kr_currency(d.get('in_req_amount', 0))
        fund_type, fund_purpose = d.get('in_fund_type', '운전자금'), d.get('in_fund_purpose', '미입력')
        item, market, diff, route = d.get('in_item_desc', '미입력'), d.get('in_market_status', '미입력'), d.get('in_diff_point', '미입력'), d.get('in_sales_route', '')
        lease_status = d.get('in_lease_status', '자가')
        start_date_str = d.get('in_start_date', '미입력').strip()
        
        biz_years = max(0, 2026 - int(start_date_str[:4])) if start_date_str and start_date_str != '미입력' else 0
        certs_list = [f"{cert}({d.get(f'in_cert_date_{i}', '일자미상')})" for i, cert in enumerate(["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]) if d.get(f"in_chk_{i}", False)]
        cert_status = ", ".join(certs_list) if certs_list else "미보유"

        pat_parts = [f"{pt} {safe_int(d.get(f'in_{pt}_cnt', 0))}건" for pt in ["특허출원", "특허등록", "상표등록", "디자인등록"] if d.get('in_has_patent') == '유' and safe_int(d.get(f"in_{pt}_cnt", 0)) > 0]
        pat_str = " ".join(pat_parts) if pat_parts else "특허/지재권 미보유"
        
        export_info = f"유 (24년 {format_kr_currency(d.get('in_exp_2024', 0))}, 25년 {format_kr_currency(d.get('in_exp_2025', 0))}, 금년 {format_kr_currency(d.get('in_exp_current', 0))})" if d.get('in_is_export') == '유' else "무 (전액 내수)"

        st.title("📝 기관별 맞춤형 융자·사업계획서 자동 생성기")
        tabs = st.tabs(["1. 중소벤처기업진흥공단", "2. 소상공인시장진흥공단"])

        # ==========================================
        # [1. 중진공 탭]
        # ==========================================
        with tabs[0]:
            st.subheader("🏢 중소벤처기업진흥공단 (중진공)")
            fund_categories = {
                "혁신창업화자금": ["청년전용창업자금", "개발기술사업화자금"],
                "신시장진출지원자금": ["내수기업 수출기업화자금", "수출기업 글로벌화 자금", "수출지원자금"],
                "신성장기반자금": ["혁신성장지원자금", "혁신성장지원자금(협동화포함)", "스케일업금융자금", "Net Zero 유망기업지원자금", "제조현장스마트화자금", "탄소중립전환자금", "스마트공장 연계자금"],
                "재도약지원자금": ["재창업자금", "구조개선전용자금", "사업전환지원자금", "통상변화대응지원사업", "선제적 자율구조개선프로그램"],
                "긴급경영안전자금": ["긴급경영안전자금(재해중소기업지원)", "긴급경영안전자금(일시적경영애로지원)"]
            }
            
            c_dd1, c_dd2 = st.columns(2)
            with c_dd1: main_fund_type = st.selectbox("💡 1. 대분류 자금종류 (중진공)", list(fund_categories.keys()))
            with c_dd2: kosme_fund_type = st.selectbox("💡 2. 세부 자금종류 (중진공)", fund_categories[main_fund_type])
            
            c_p1, c_p2 = st.columns(2)
            
            # --- 좌측: 융자신청서 (공통 양식) ---
            with c_p1:
                st.markdown("#### 📄 중진공 융자신청서(공통)")
                if st.button("🚀 중진공 융자신청서 바로보기", use_container_width=True):
                    with st.status("🚀 분석 및 생성 작업 시작...", expanded=True) as status:
                        st.write("⏳ 1/3: 기업 기본 데이터 및 재무 정보 연동 중...")
                        time.sleep(1)
                        st.write("⏳ 2/3: 해당 자금의 심사역 평가 기준 매칭 중...")
                        time.sleep(1)
                        st.write("⏳ 3/3: 맞춤형 서식으로 AI 렌더링 중...")
                        try:
                            model = genai.GenerativeModel(get_best_model_name())
                            prompt_loan = f"""
                            당신은 정책자금 전문 컨설턴트입니다. 마크다운 금지. 
                            [기업 데이터] 기업명:{c_name} / 매출(23/24/당기):{sales_23}/{sales_24}/{s_cur} / 신청자금:{req_fund} ({fund_type}) / 아이템:{item}
                            [작성 규칙] 체크박스 ▣ 사용. 제품생산공정도와 시장상황, 판매계획 등을 엄청나게 상세히(각 800자 이상) 작성. &bull;와 <b> 활용.
                            
                            <h2 style="text-align:center;">중소기업 정책자금 융자신청서</h2>
                            <h3>[신청내용]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:left; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">신청자금명</th><td style="border:1px solid #333; padding:8px;">▣ {kosme_fund_type}</td><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">신청금액</th><td style="border:1px solid #333; padding:8px;">{req_fund}</td></tr>
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">융자방식</th><td colspan="3" style="border:1px solid #333; padding:8px;">▣ 중진공 직접대출 &nbsp;&nbsp; □ 대리대출</td></tr>
                            </table>
                            <h3>[매출 현황]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:center; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">구분</th><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">23년</th><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">24년</th><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">금년(당월)</th><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">27년(예상)</th></tr>
                            <tr><td style="border:1px solid #333; padding:8px;">총매출액</td><td style="border:1px solid #333; padding:8px;">{sales_23}</td><td style="border:1px solid #333; padding:8px;">{sales_24}</td><td style="border:1px solid #333; padding:8px;">{s_cur}</td><td style="border:1px solid #333; padding:8px;">(자동계산)</td></tr>
                            </table>
                            <h3>[주요 생산제품 개요]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:left; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0; width:20%;">제품특성/공정도</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(엄청나게 상세히 작성)</td></tr>
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0;">시장상황/경쟁력</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(엄청나게 상세히 작성)</td></tr>
                            </table>
                            <div style="page-break-before: always; padding-top: 20px;"></div>
                            <h3>[사업계획서 (자금활용 계획)]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:left; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0; width:20%;">사업내용/효과</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(자금 활용 상세 효과 작성)</td></tr>
                            </table>
                            """
                            response = model.generate_content(prompt_loan)
                            st.session_state["kosme_result_type"] = "loan"
                            st.session_state["kosme_result_html"] = clean_html_output(response.text)
                            status.update(label="✅ 공통 융자신청서 생성 완료!", state="complete")
                        except Exception as e:
                            status.update(label=f"❌ 오류 발생: {str(e)}", state="error")
            
            # --- 우측: 사업계획서 (별첨 양식) ---
            with c_p2:
                st.markdown(f"#### 📝 중진공 사업계획서 ({kosme_fund_type})")
                if st.button(f"🚀 중진공 {kosme_fund_type} 바로보기", use_container_width=True):
                    with st.status(f"🚀 분석 및 생성 작업 시작...", expanded=True) as status:
                        st.write("⏳ 1/3: 기업 기본 데이터 연동 중...")
                        time.sleep(1)
                        st.write(f"⏳ 2/3: '{kosme_fund_type}' 1타 심사역 로직 주입 중...")
                        time.sleep(1)
                        st.write("⏳ 3/3: 서술형 프리미엄 문서 렌더링 중...")
                        
                        try:
                            # 🚨 [최적화 핵심] 긴 공통 프롬프트를 변수로 빼서 문자열 길이 축소
                            base_kosme_instruction = f"""
                            당신은 중소기업진흥공단의 깐깐한 심사역입니다. 마크다운 금지. 순수 HTML 사용. 들여쓰기 금지.
                            [기업데이터] 기업명:{c_name}/업력:{biz_years}년/아이템:{item}/시장현황:{market}/차별성:{diff}/매출:{s_cur}/수출:{export_info}
                            [AI 작성 흔적 제거 및 분량/가독성 강제] 
                            - "결론적으로", "요약하자면" 등 AI 특유 표현 금지. 단호하고 설득력 있는 실무 비즈니스 용어 사용.
                            - 핵심 포인트는 글머리 기호(&bull;)나 굵은 글씨(<b>)를 사용해 가독성 극대화. 적절히 줄바꿈(<br>) 적용.
                            - 외부 지식베이스(시장 데이터, 트렌드)를 끌어와 전체 출력이 A4 5장 분량이 되도록 엄청나게 쏟아낼 것.
                            <h1 style="text-align:center; font-size:32px; color:#002b5e; border-bottom:3px solid #002b5e; padding-bottom:10px; margin-bottom:10px;">{kosme_fund_type} 사업계획서</h1>
                            <h2 style="text-align:center; font-size:24px; color:#333; margin-top:0; margin-bottom:40px;">(주식회사 {c_name})</h2>
                            <p style="font-size:15px; line-height:1.8; color:#444; margin-bottom:30px;">(서론 형식 사업목적 500자)</p>
                            """

                            # 자금별 HTML 뼈대 분기
                            if kosme_fund_type == "청년전용창업자금":
                                prompt_plan = base_kosme_instruction + """
                                [작성 룰] 실행력, J커브 성장성, 성과 직결 구조 어필.
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">1. 창업 동기 및 기업 개요</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">2. 창업아이템의 개요 및 경쟁력</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">3. 사업추진 계획</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">4. 기대 효과 및 성장 비전</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                """
                            elif kosme_fund_type == "개발기술사업화자금":
                                prompt_plan = base_kosme_instruction + f"""
                                [작성 룰] 사업화(돈 버는 구조) 중심. TAM/SAM/SOM 수치 제시. J커브 어필.
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">1. 신청 개발기술의 제품 개요 및 차별성</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">2. 사업화(양산) 및 기대효과</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">3. 시장성 및 경쟁 현황</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">4. 판매계획 및 매출 시나리오</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                """
                            elif "수출" in kosme_fund_type:
                                prompt_plan = base_kosme_instruction + """
                                [작성 룰] 수출 실행능력, 진출국 논리, 필수 숫자 6종(계약규모, 투자규모, 수출목표 등), 비율 명시 어필.
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">1. 기업 수출역량 및 글로벌 진출 필요성</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">2. 목표 시장 선정 및 제품 경쟁력</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">3. 시장 진입 전략 및 매출 발생 계획</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">4. 자금 활용 계획 및 중장기 성장 전략</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                """
                            else: # 혁신성장 및 일반
                                prompt_plan = base_kosme_instruction + """
                                [작성 룰] 기술/공정 개선 수치, 확장성(TAM/SAM/SOM), 성장 투자(설비) 타당성, 3단계 로드맵 제시.
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">1. 기술 혁신성 및 차별성</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">2. 시장 분석 및 확장성</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">3. 사업화 체계 및 생산·운영 계획</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                <h2 style="font-size:22px; color:#002b5e; border-bottom:2px solid #002b5e; padding-bottom:5px;">4. 자금 사용 타당성 및 단계별 성장 전략</h2><p style="font-size:15px; line-height:1.8; margin-bottom:20px;">(상세서술)</p>
                                [GRAPH_INSERT_POINT]
                                """
                            
                            # J커브 그래프
                            val_cur = safe_int(d.get('in_sales_current', 0)) or 1000
                            sv, ev = val_cur / 12, (val_cur / 12) * 1.5
                            m_vals = [int(sv + (ev - sv) * (i/11.0) + (ev - sv) * 0.15 * np.sin((i/11.0) * np.pi * 3.5)) for i in range(12)]
                            fig = go.Figure(go.Scatter(x=[f"{i}월" for i in range(1, 13)], y=m_vals, mode='lines+markers+text', text=[format_kr_currency(v) for v in m_vals], textposition="top center", line=dict(color='#1E88E5', width=4, shape='spline')))
                            fig.update_layout(title="📈 향후 1년 월별 매출 상승 시각화", xaxis_title="진행 월", yaxis_title="매출액", template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
                            plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

                            model = genai.GenerativeModel(get_best_model_name())
                            response = model.generate_content(prompt_plan)
                            
                            cleaned_html = clean_html_output(response.text)
                            if "[GRAPH_INSERT_POINT]" in cleaned_html:
                                cleaned_html = cleaned_html.replace("[GRAPH_INSERT_POINT]", plotly_html)
                            else:
                                cleaned_html += f"<br><br>{plotly_html}"
                                
                            st.session_state["kosme_result_type"] = "plan"
                            st.session_state["kosme_result_html"] = cleaned_html
                            status.update(label="✅ 사업계획서(별첨) 생성 완료!", state="complete")
                            st.balloons()
                        except Exception as e:
                            status.update(label=f"❌ 오류 발생: {str(e)}", state="error")

            if "kosme_result_html" in st.session_state:
                st.divider()
                doc_title = "사업계획서(별첨)" if st.session_state["kosme_result_type"] == "plan" else "융자신청서(공통)"
                st.subheader(f"📄 생성된 문서 확인: {doc_title}")
                st.markdown(st.session_state["kosme_result_html"], unsafe_allow_html=True)
                
                safe_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip() or "업체"
                html_export = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{c_name} {doc_title}</title><style>* {{ box-sizing: border-box; }} body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f4f4; padding: 40px 0; margin: 0; }} .document-container {{ max-width: 900px; margin: 0 auto; background-color: #fff; padding: 60px; box-shadow: 0 0 15px rgba(0,0,0,0.1); border-radius: 8px; color: #333; line-height: 1.6; font-size: 15px; white-space: pre-wrap; }} table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; }} td, th {{ border: 1px solid #ccc; padding: 10px; }} th {{ background-color: #f0f0f0; }} @media print {{ @page {{ size: A4; margin: 15mm; }} body {{ background-color: #fff; padding: 0 !important; color: black !important; zoom: 0.9; }} .document-container {{ box-shadow: none; padding: 0; max-width: 100%; border-radius: 0; }} }}</style></head><body><div class="document-container">{st.session_state["kosme_result_html"]}</div></body></html>"""
                st.download_button(label=f"📥 {doc_title} HTML 다운로드", data=html_export, file_name=f"{safe_name}_{doc_title}.html", mime="text/html", type="primary")

        # ==========================================
        # [2. 소진공 탭]
        # ==========================================
        with tabs[1]:
            st.subheader("🏪 소상공인시장진흥공단 (소진공)")
            semas_fund_list = ["혁신성장촉진자금", "상생성장지원자금", "신용취약소상공인자금", "일시적경영애로자금", "재도전특별자금", "민간투자연계형매칭융자"]
            semas_fund_type = st.selectbox("💡 소진공 자금선택", semas_fund_list)
            st.markdown("#### 📄 소진공 기업현황 및 사업계획서(통합)")
            
            if st.button(f"🚀 소진공 {semas_fund_type} 생성", use_container_width=True):
                with st.status(f"🚀 분석 및 생성 작업 시작...", expanded=True) as status:
                    st.write("⏳ 1/3: 기업 기본 데이터 및 재무 정보 연동 중...")
                    time.sleep(1)
                    st.write(f"⏳ 2/3: '{semas_fund_type}' 소진공 맞춤 로직 매칭 중...")
                    time.sleep(1)
                    st.write("⏳ 3/3: 소상공인 공식 표 양식 렌더링 중...")
                    try:
                        past_close_html = ""
                        if semas_fund_type == "재도전특별자금":
                            past_close_html = """
                            <h4 style="color:#333;">■ 과거 폐업 기업 현황 (재도전특별자금 전용)</h4>
                            <table style="width:100%; border-collapse:collapse; border:1px solid #000; text-align:center; font-size:13px; margin-bottom:20px;">
                              <tr><th style="background:#f0f0f0; border:1px solid #000; padding:8px;">과거 업체명</th><td style="border:1px solid #000; padding:8px;">(과거 기업명)</td><th style="background:#f0f0f0; border:1px solid #000; padding:8px;">창업/폐업일</th><td style="border:1px solid #000; padding:8px;">(YYYY.MM ~ YYYY.MM)</td></tr>
                              <tr><th style="background:#f0f0f0; border:1px solid #000; padding:8px;">폐업 사유</th><td colspan="3" style="border:1px solid #000; padding:8px; text-align:left;">(실패 원인 명확히 기재)</td></tr>
                            </table>
                            """
                            
                        funding_plan_html = ""
                        if semas_fund_type == "신용취약소상공인자금":
                            funding_plan_html = """
                            <h4 style="color:#333;">■ 자금조달 계획 (단위: 백만원)</h4>
                            <table style="width:100%; border-collapse:collapse; border:1px solid #000; text-align:center; font-size:13px; margin-bottom:20px;">
                              <tr style="background:#f0f0f0;"><th style="border:1px solid #000; padding:8px;">본인 자체자금</th><th style="border:1px solid #000; padding:8px;">본건 대출금</th><th style="border:1px solid #000; padding:8px;">타기관 대출금 등</th><th style="border:1px solid #000; padding:8px;">합계</th></tr>
                              <tr><td style="border:1px solid #000; padding:8px;">(수치)</td><td style="border:1px solid #000; padding:8px;">(수치)</td><td style="border:1px solid #000; padding:8px;">(수치)</td><td style="border:1px solid #000; padding:8px; font-weight:bold;">(합계)</td></tr>
                            </table>
                            """

                        prompt_plan_semas = f"""
                        당신은 소상공인시장진흥공단의 깐깐한 심사역입니다. 마크다운 금지. 순수 HTML 사용.
                        [기업데이터] 기업명:{c_name} / 아이템:{item} / 시장현황:{market} / 신청자금:{req_fund}
                        
                        [작성 룰] 
                        - 에세이체 전면 금지. 개조식(Bullet point), 단문 위주, 핵심 팩트 위주.
                        - 짧은 문장 여러 개와 <br> 태그를 사용하여 표 안의 여백을 시원하게 채울 것.
                        - 자금명({semas_fund_type})의 특성(위기극복, 재창업, 투자연계, 기술도입 등)을 강력하게 반영.

                        [출력 HTML 뼈대]
                        <h2 style="text-align:center; color:#002b5e; margin-bottom:30px;">기업현황 및 사업계획서 ({semas_fund_type})</h2>

                        <h3 style="color:#333; border-bottom:2px solid #000; padding-bottom:5px;">1. 개요 및 매출 현황</h3>
                        <table style="width:100%; border-collapse:collapse; border:1px solid #000; text-align:center; font-size:13px; margin-bottom:20px;">
                          <tr><th style="background:#f0f0f0; border:1px solid #000; padding:8px;">업체명</th><td style="border:1px solid #000; padding:8px;">{c_name}</td><th style="background:#f0f0f0; border:1px solid #000; padding:8px;">대표자</th><td style="border:1px solid #000; padding:8px;">{rep_name}</td></tr>
                          <tr><th style="background:#f0f0f0; border:1px solid #000; padding:8px;">23년 매출</th><td style="border:1px solid #000; padding:8px;">{sales_23}</td><th style="background:#f0f0f0; border:1px solid #000; padding:8px;">24년 매출</th><td style="border:1px solid #000; padding:8px;">{sales_24}</td></tr>
                        </table>

                        <h3 style="color:#333; border-bottom:2px solid #000; padding-bottom:5px;">2. 사업계획서</h3>
                        {past_close_html}
                        <table style="width:100%; border-collapse:collapse; border:1px solid #000; font-size:13px; margin-bottom:20px;">
                          <tr><th style="background:#f0f0f0; border:1px solid #000; padding:15px; width:25%; text-align:center;">사업내용 및<br>대출금 사용목적</th><td style="border:1px solid #000; padding:15px; line-height:1.6;">(자금별 성격에 맞춰 개조식 4줄 작성)</td></tr>
                          <tr><th style="background:#f0f0f0; border:1px solid #000; padding:15px; text-align:center;">기술, 제품(상품),<br>점포의 경쟁력</th><td style="border:1px solid #000; padding:15px; line-height:1.6;">(경쟁력 개조식 4줄 작성)</td></tr>
                          <tr><th style="background:#f0f0f0; border:1px solid #000; padding:15px; text-align:center;">시장상황 및<br>판매계획</th><td style="border:1px solid #000; padding:15px; line-height:1.6;">(수요 대응 전략 개조식 4줄 작성)</td></tr>
                        </table>

                        {funding_plan_html}
                        <h4 style="color:#333;">□ 자금집행계획 (단위: 백만원)</h4>
                        <table style="width:100%; border-collapse:collapse; border:1px solid #000; text-align:center; font-size:13px; margin-bottom:20px;">
                          <tr style="background:#f0f0f0;"><th style="border:1px solid #000; padding:8px;">구분</th><th style="border:1px solid #000; padding:8px;">품목/내용</th><th style="border:1px solid #000; padding:8px;">소요금액</th></tr>
                          <tr><td style="border:1px solid #000; padding:8px;" rowspan="2">자금 사용내역</td><td style="border:1px solid #000; padding:8px; text-align:left;">(원부자재, 마케팅비 등 구체적 기재)</td><td style="border:1px solid #000; padding:8px;">(자동산출)</td></tr>
                          <tr><td style="border:1px solid #000; padding:8px; text-align:left;">(설비, 생산부대비용 등 구체적 기재)</td><td style="border:1px solid #000; padding:8px;">(자동산출)</td></tr>
                          <tr style="font-weight:bold; background:#fafafa;"><td style="border:1px solid #000; padding:8px;" colspan="2">총 소요금액</td><td style="border:1px solid #000; padding:8px; color:#c62828;">{req_fund}</td></tr>
                        </table>
                        """

                        model = genai.GenerativeModel(get_best_model_name())
                        response = model.generate_content(prompt_plan_semas)
                        st.session_state["semas_result_type"] = "plan"
                        st.session_state["semas_result_html"] = clean_html_output(response.text)
                        status.update(label="✅ 소진공 맞춤 통합 사업계획서 생성 완료!", state="complete")
                        st.balloons()
                    except Exception as e:
                        status.update(label=f"❌ 오류 발생: {str(e)}", state="error")
                        
            if "semas_result_html" in st.session_state:
                st.divider()
                doc_title = "기업현황 및 사업계획서(통합)"
                st.subheader(f"📄 생성된 문서 확인: {doc_title}")
                st.markdown(st.session_state["semas_result_html"], unsafe_allow_html=True)
                
                safe_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip() or "업체"
                html_export = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{c_name} 소진공 {doc_title}</title><style>* {{ box-sizing: border-box; }} body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f4f4; padding: 40px 0; margin: 0; }} .document-container {{ max-width: 900px; margin: 0 auto; background-color: #fff; padding: 60px; box-shadow: 0 0 15px rgba(0,0,0,0.1); border-radius: 8px; color: #333; line-height: 1.6; font-size: 15px; white-space: pre-wrap; }} table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; }} td, th {{ border: 1px solid #000; padding: 10px; }} th {{ background-color: #f0f0f0; }} @media print {{ @page {{ size: A4; margin: 15mm; }} body {{ background-color: #fff; padding: 0 !important; color: black !important; zoom: 0.9; }} .document-container {{ box-shadow: none; padding: 0; max-width: 100%; border-radius: 0; }} }}</style></head><body><div class="document-container">{st.session_state["semas_result_html"]}</div></body></html>"""
                st.download_button(label=f"📥 소진공 {doc_title} HTML 다운로드", data=html_export, file_name=f"{safe_name}_소진공_{doc_title}.html", mime="text/html", type="primary")

    # ---------------------------------------------------------
    # [모드 D: 4. 정식 사업계획서 (마스터)]
    # ---------------------------------------------------------
    elif st.session_state["view_mode"] == "FULL_PLAN":
        if st.button("⬅️ 대시보드로 돌아가기"):
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
            
        st.title("📑 AI 사업계획서 자동 생성")
        plan_type = st.radio("💡 사업계획서 용도를 선택하세요", ["기관제출용", "투자용(IR)"], horizontal=True)
        st.info(f"선택하신 **'{plan_type}'** 마스터 사업계획서 생성 메뉴입니다. (추후 고도화 업데이트 예정)")

    # --- [입력 화면 (메인 대시보드)] ---
    else:
        st.title("📊 AI 컨설팅 대시보드")
        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
        with col_t1:
            if st.button("📊 AI 기업분석리포트", use_container_width=True, type="primary"):
                if not is_valid_mandatory(): st.error("🚨 대시보드의 필수 입력란(*필수)을 모두 채워주세요.")
                else:
                    st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                    st.session_state["view_mode"] = "REPORT"
                    st.session_state.pop("generated_report", None)
                    st.rerun()
        with col_t2: 
            if st.button("💡 AI 정책자금 매칭리포트", use_container_width=True, type="primary"):
                if not is_valid_mandatory(): st.error("🚨 대시보드의 필수 입력란(*필수)을 모두 채워주세요.")
                else:
                    st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                    st.session_state["view_mode"] = "MATCHING"
                    st.session_state.pop("generated_matching", None)
                    st.rerun()
        with col_t3: 
            if st.button("📝 융자·사업계획서 맞춤형 AI 생성", use_container_width=True, type="primary"):
                if not is_valid_mandatory(): st.error("🚨 대시보드의 필수 입력란(*필수)을 모두 채워주세요.")
                else:
                    st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                    st.session_state["view_mode"] = "PLAN"
                    st.session_state.pop("kosme_result_html", None)
                    st.session_state.pop("semas_result_html", None)
                    st.rerun()
        with col_t4: 
            if st.button("📑 AI 사업계획서", use_container_width=True, type="primary"):
                if not is_valid_mandatory(): st.error("🚨 대시보드의 필수 입력란(*필수)을 모두 채워주세요.")
                else:
                    st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                    st.session_state["view_mode"] = "FULL_PLAN"
                    st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

        st.header("1. 기업현황 (*필수)")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("기업명 (*필수)", key="in_company_name")
            st.text_input("사업자번호 (*필수)", placeholder="숫자만 입력", key="in_raw_biz_no", on_change=cb_format_biz_no)
            biz_type = st.radio("사업자유형 (*필수)", ["개인", "법인"], horizontal=True, key="in_biz_type")
            if biz_type == "법인": 
                st.text_input("법인등록번호 (*필수)", placeholder="숫자만 입력", key="in_raw_corp_no", on_change=cb_format_corp_no)
        with c2:
            st.text_input("사업개시일 (*필수)", placeholder="예: 20200101", key="in_start_date", on_change=cb_format_date, args=("in_start_date",))
            st.selectbox("업종 (*필수)", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
            st.number_input("상시근로자수(명) (*필수)", value=None, placeholder="예: 5", step=1, key="in_employee_count")
            lease_status = st.radio("사업장 임대여부 (*필수)", ["자가", "임대"], horizontal=True, key="in_lease_status")
            if lease_status == "임대":
                lc1, lc2 = st.columns(2)
                with lc1: st.number_input("보증금(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_lease_deposit", help="단위: 만원 (예: 1억 원 = 10000 입력)")
                with lc2: st.number_input("월임대료(만원) (*필수)", value=None, placeholder="예: 100만=100", key="in_lease_rent", help="단위: 만원 (예: 100만 원 = 100 입력)")
        with c3:
            st.text_input("전화번호 (*필수)", placeholder="숫자만 입력", key="in_biz_tel", on_change=cb_format_phone, args=("in_biz_tel",))
            has_add_biz = st.radio("추가사업장현황", ["무", "유"], horizontal=True, key="in_has_additional_biz")
            if has_add_biz == "유": st.text_input("추가 사업장 정보 (예: 공장 주소 등)", key="in_additional_biz_addr")
            st.text_input("사업장 주소 (*필수)", key="in_biz_addr")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("2. 대표자 정보 (*필수)")
        dob_val = str(st.session_state.get("in_rep_dob", "") or "").replace(".", "").strip()
        is_youth = False
        if len(dob_val) == 8:
            try:
                if 2026 - int(dob_val[:4]) <= 39: is_youth = True
            except: pass
        dob_label = "생년월일 (*필수) 🌟 청년사업자" if is_youth else "생년월일 (*필수)"

        r1, r2, r3 = st.columns(3)
        with r1:
            rc1, rc2 = st.columns(2)
            with rc1: st.text_input("대표자명 (*필수)", key="in_rep_name")
            with rc2: st.text_input(dob_label, placeholder="예: 19900101", key="in_rep_dob", on_change=cb_format_date, args=("in_rep_dob",))
            st.text_input("연락처 (휴대폰) (*필수)", placeholder="숫자만 입력", key="in_rep_phone", on_change=cb_format_phone, args=("in_rep_phone",))
            st.selectbox("통신사 (*필수)", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")
            st.text_input("이메일 주소 (*필수)", key="in_rep_email")
        with r2:
            st.text_input("거주지 주소 (*필수)", key="in_home_addr")
            st.radio("거주지 상태 (*필수)", ["자가", "임대"], horizontal=True, key="in_home_status")
            st.text_input("부동산 현황 (*필수)", key="in_real_estate")
        with r3:
            st.text_input("최종학교 (*필수)", key="in_edu_school")
            st.text_input("학과 (*필수)", key="in_edu_major")
            st.text_area("경력(최근기준) (*필수)", key="in_career")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("3. 신용 및 연체 정보 (*필수)")
        cr1, cr2 = st.columns(2)
        with cr1:
            cc1, cc2 = st.columns(2)
            with cc1: st.radio("세금체납 (*필수)", ["무", "유"], horizontal=True, key="in_tax_status")
            with cc2: st.radio("금융연체 (*필수)", ["무", "유"], horizontal=True, key="in_fin_status")
            sc1, sc2 = st.columns(2)
            with sc1: kcb = st.number_input("KCB 점수 (*필수)", value=None, step=1, key="in_kcb_score")
            with sc2: nice = st.number_input("NICE 점수 (*필수)", value=None, step=1, key="in_nice_score")
        with cr2:
            st.info(f"#### 🏆 등급 판정 결과\n\n* **KCB (올크레딧):** {get_credit_grade(kcb, 'KCB')}등급\n* **NICE (나이스):** {get_credit_grade(nice, 'NICE')}등급")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("4. 매출현황 (*필수)")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.number_input("금년 당월 매출(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_sales_current", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        with m2: st.number_input("25년도 매출합계(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_sales_2025", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        with m3: st.number_input("24년도 매출합계(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_sales_2024", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        with m4: st.number_input("23년도 매출합계(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_sales_2023", help="단위: 만원 (예: 1억 원 = 10000 입력)")

        c_ind = st.session_state.get("in_industry", "기타")
        if c_ind in ["제조업", "도소매업"]:
            st.markdown("**(수출 정보)**")
            has_export = st.radio("수출 유무", ["무", "유"], horizontal=True, key="in_is_export")
            if has_export == "유":
                e1, e2, e3 = st.columns(3)
                with e1: st.number_input("26년도(금년) 수출액(만원)", value=None, placeholder="예: 1억=10000", key="in_exp_current", help="단위: 만원 (예: 1억 원 = 10000 입력)")
                with e2: st.number_input("25년도 수출액(만원)", value=None, placeholder="예: 1억=10000", key="in_exp_2025", help="단위: 만원 (예: 1억 원 = 10000 입력)")
                with e3: st.number_input("24년도 수출액(만원)", value=None, placeholder="예: 1억=10000", key="in_exp_2024", help="단위: 만원 (예: 1억 원 = 10000 입력)")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("5. 부채현황 (*필수)")
        d1, d2, d3, d4 = st.columns(4)
        with d1: st.number_input("중진공(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_debt_kosme", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        with d2: st.number_input("소진공(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_debt_semas", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        with d3: st.number_input("신용보증재단(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_debt_koreg", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        with d4: st.number_input("신용보증기금(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_debt_kodit", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        d5, d6, d7, d8 = st.columns(4)
        with d5: st.number_input("기술보증기금(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_debt_kibo", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        with d6: st.number_input("기타(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_debt_etc", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        with d7: st.number_input("신용대출(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_debt_credit", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        with d8: st.number_input("담보대출(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_debt_coll", help="단위: 만원 (예: 1억 원 = 10000 입력)")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("6. 필요자금 (*필수)")
        p1, p2, p3 = st.columns([1, 1, 2])
        with p1: st.selectbox("자금구분 (*필수)", ["운전자금", "시설자금"], key="in_fund_type")
        with p2: st.number_input("필요자금액(만원) (*필수)", value=None, placeholder="예: 1억=10000", key="in_req_amount", help="단위: 만원 (예: 1억 원 = 10000 입력)")
        with p3: st.text_input("자금사용용도 (*필수)", key="in_fund_purpose")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("7. 인증현황")
        certs = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
        c_cols = st.columns(4)
        for i, cert in enumerate(certs):
            with c_cols[i % 4]:
                if st.checkbox(cert, key=f"in_chk_{i}"):
                    st.text_input(f"↪ {cert} 발급일자", placeholder="예: 20250101", key=f"in_cert_date_{i}", on_change=cb_format_date, args=(f"in_cert_date_{i}",))

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("8. 특허 및 정부지원사업 정보")
        pat_col1, pat_col2 = st.columns(2)
        with pat_col1:
            if st.radio("특허/지식재산권 보유여부", ["무", "유"], horizontal=True, key="in_has_patent") == "유":
                for pt in ["특허출원", "특허등록", "상표등록", "디자인등록"]:
                    cnt = st.number_input(f"➤ {pt} (건수)", min_value=0, step=1, key=f"in_{pt}_cnt")
                    for i in range(int(cnt)): st.text_input(f" - {pt} {i+1}번 번호", key=f"in_{pt}_num_{i}")
                        
        with pat_col2:
            if st.radio("정부지원사업 진행이력", ["무", "유"], horizontal=True, key="in_has_gov") == "유":
                gov_cnt = st.number_input("➤ 지원사업 (건수)", min_value=0, step=1, key="in_gov_cnt")
                for i in range(int(gov_cnt)): st.text_input(f" - 지원사업 {i+1}번 사업명", key=f"in_gov_name_{i}")
                    
            st.markdown("---")
            if st.radio("특허매입예정", ["무", "유"], horizontal=True, key="in_buy_patent") == "유":
                st.text_input("희망특허 (분야/명칭)", key="in_buy_pat_desc")
                st.number_input("예상금액(만원)", value=None, placeholder="예: 1억=10000", key="in_buy_pat_amount", help="단위: 만원 (예: 1억 원 = 10000 입력)")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("9. 비즈니스 정보")
        st.text_area("[아이템] (*필수)", key="in_item_desc")
        st.text_input("[제품생산공정도 (간략 기재)]", placeholder="예: 원물 입고 -> 세척 -> 조리 -> 포장 -> 출하", key="in_process_desc")
        st.markdown("**[주거래처 정보]**")
        cli1, cli2, cli3 = st.columns(3)
        with cli1: st.text_input("거래처 1", key="in_client_1")
        with cli2: st.text_input("거래처 2", key="in_client_2")
        with cli3: st.text_input("거래처 3", key="in_client_3")
        st.text_area("[판매루트] (*필수)", key="in_sales_route")
        st.text_area("[시장현황]", key="in_market_status")
        st.text_area("[차별화]", key="in_diff_point")
        st.text_area("[앞으로의 계획] (*필수)", key="in_future_plan")

        st.markdown("<br>", unsafe_allow_html=True)
        st.success("✅ 세팅 완료! 필수 입력란(*필수)을 모두 작성 후 상단 버튼을 클릭해 주십시오.")
