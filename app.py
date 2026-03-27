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

# --- 자동 하이픈(-) 포맷팅 함수 ---
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
    req_texts = [
        "in_company_name", "in_raw_biz_no", "in_biz_type", "in_start_date", "in_industry", "in_biz_addr",
        "in_rep_name", "in_rep_dob", "in_rep_phone", "in_home_addr", "in_home_status", "in_item_desc",
        "in_sales_route", "in_future_plan", "in_fund_purpose"
    ]
    if st.session_state.get("in_biz_type") == "법인": req_texts.append("in_raw_corp_no")
        
    for k in req_texts:
        if not str(st.session_state.get(k, "") or "").strip(): return False
            
    req_nums = [
        "in_kcb_score", "in_nice_score",
        "in_sales_current", "in_sales_2025", "in_sales_2024", "in_sales_2023",
        "in_debt_kosme", "in_debt_semas", "in_debt_koreg", "in_debt_kodit",
        "in_debt_kibo", "in_debt_etc", "in_debt_credit", "in_debt_coll", "in_req_amount"
    ]
        
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
                # DB 로드 후 자동 포맷팅 강제 적용
                st.session_state["in_raw_biz_no"] = fmt_biz(st.session_state.get("in_raw_biz_no"))
                st.session_state["in_raw_corp_no"] = fmt_corp(st.session_state.get("in_raw_corp_no"))
                st.session_state["in_start_date"] = fmt_date(st.session_state.get("in_start_date"))
                st.session_state["in_rep_dob"] = fmt_date(st.session_state.get("in_rep_dob"))
                st.session_state["in_biz_tel"] = fmt_phone(st.session_state.get("in_biz_tel"))
                st.session_state["in_rep_phone"] = fmt_phone(st.session_state.get("in_rep_phone"))
                for i in range(8): st.session_state[f"in_cert_date_{i}"] = fmt_date(st.session_state.get(f"in_cert_date_{i}"))
                st.rerun()
    with col_s2:
        if st.button("🔄 초기화", use_container_width=True):
            keys_to_delete = [k for k in st.session_state.keys() if k.startswith("in_")]
            for k in keys_to_delete: del st.session_state[k]
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🚀 빠른 리포트 생성")
    
    if st.sidebar.button("📊 AI 기업분석리포트", use_container_width=True):
        if not is_valid_mandatory(): st.sidebar.error("🚨 필수 항목(*)을 모두 입력해주세요.")
        else:
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "REPORT"
            st.session_state.pop("generated_report", None)
            st.rerun()
        
    if st.sidebar.button("💡 AI 정책자금 매칭리포트", use_container_width=True):
        if not is_valid_mandatory(): st.sidebar.error("🚨 필수 항목(*)을 모두 입력해주세요.")
        else:
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "MATCHING"
            st.session_state.pop("generated_matching", None)
            st.rerun()
        
    if st.sidebar.button("📝 융자·사업계획서 맞춤형 AI 생성", use_container_width=True):
        if not is_valid_mandatory(): st.sidebar.error("🚨 필수 항목(*)을 모두 입력해주세요.")
        else:
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "PLAN"
            st.session_state.pop("kosme_result_html", None)
            st.session_state.pop("semas_result_html", None)
            st.rerun()
        
    if st.sidebar.button("📑 AI 사업계획서", use_container_width=True):
        if not is_valid_mandatory(): st.sidebar.error("🚨 필수 항목(*)을 모두 입력해주세요.")
        else:
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
                
                html_export = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{c_name} AI기업분석리포트</title>
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
                {response_text.replace('[GRAPH_INSERT_POINT]', plotly_html)}</div></body></html>"""
                st.download_button(label="📥 리포트 HTML 파일로 다운로드", data=html_export, file_name=f"{safe_file_name}_기업분석리포트.html", mime="text/html", type="primary")
            except Exception as e:
                st.error(f"❌ 시스템 오류 발생: {str(e)}")

    # ---------------------------------------------------------
    # [모드 B: 2. 정책자금 매칭 리포트]
    # ---------------------------------------------------------
