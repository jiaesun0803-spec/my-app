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

def format_biz_no(raw_no):
    no = str(raw_no).replace("-", "").strip()
    if len(no) == 10: return f"{no[:3]}-{no[3:5]}-{no[5:]}"
    return raw_no

def format_corp_no(raw_no):
    no = str(raw_no).replace("-", "").strip()
    if len(no) == 13: return f"{no[:6]}-{no[6:]}"
    return raw_no

def get_best_model_name():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if 'models/gemini-1.5-flash' in available: return 'gemini-1.5-flash'
        if 'models/gemini-1.5-pro' in available: return 'gemini-1.5-pro'
        if 'models/gemini-1.0-pro' in available: return 'gemini-1.0-pro'
        if 'models/gemini-pro' in available: return 'gemini-pro'
        if available: return available[0].replace('models/', '')
    except:
        pass
    return 'gemini-pro'

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
        if st.session_state.get("view_mode", "INPUT") == "INPUT":
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = "REPORT"
        st.session_state.pop("generated_report", None)
        st.rerun()
        
    if st.sidebar.button("💡 2. 정책자금 매칭 리포트", use_container_width=True):
        if st.session_state.get("view_mode", "INPUT") == "INPUT":
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = "MATCHING"
        st.session_state.pop("generated_matching", None)
        st.rerun()
        
    if st.sidebar.button("📝 3. 기관 맞춤형 융자/사업계획서 AI자동 생성기", use_container_width=True):
        if st.session_state.get("view_mode", "INPUT") == "INPUT":
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = "PLAN"
        st.session_state.pop("kosme_result_html", None)
        st.session_state.pop("semas_result_html", None)
        st.rerun()
        
    if st.sidebar.button("📑 4. 정식 사업계획서 (마스터) 생성", use_container_width=True):
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
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력').strip()
        
        st.title("📋 AI기업분석리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")
        
        if not st.session_state["api_key"]:
            st.error("⚠️ 좌측 사이드바에 API 키를 입력하거나, 서버 설정에 키를 등록해주세요.")
        else:
            try:
                biz_type = d.get('in_biz_type', '개인')
                c_ind = d.get('in_industry', '미입력')
                rep_name = d.get('in_rep_name', '미입력')
                biz_no = format_biz_no(d.get('in_raw_biz_no', '미입력'))
                corp_no = format_corp_no(d.get('in_raw_corp_no', ''))
                
                corp_text = f"<br><span style='font-size:0.9em; color:#555;'>({corp_no})</span>" if corp_no else ""
                address = d.get('in_biz_addr', '미입력')
                
                add_biz_status = d.get('in_has_additional_biz', '무')
                add_biz_addr = d.get('in_additional_biz_addr', '').strip()
                
                add_biz_row = ""
                if add_biz_status == '유' and add_biz_addr:
                    add_biz_row = f"<tr><td style='padding:15px; background-color:#eceff1; font-size:0.95em; white-space:nowrap;'><b>추가사업장</b></td><td colspan='5' style='padding:15px; text-align:left;'>{add_biz_addr}</td></tr>"
                
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
                
                plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

                if "generated_report" not in st.session_state:
                    with st.status("🚀 제미나이(Gemini)가 가로형 레이아웃으로 완벽한 리포트를 생성 중입니다...", expanded=True) as status:
                        try:
                            model_name = get_best_model_name()
                            model = genai.GenerativeModel(model_name)
                            
                            prompt = f"""
                            당신은 20년 경력의 중소기업 경영컨설턴트입니다. 
                            아래 양식과 서식 규칙을 **반드시 100% 똑같이** 지켜서 출력하세요.

                            [작성 규칙 - 절대 엄수!!!]
                            1. 마크다운 사용 금지: 제목이나 강조에 마크다운 기호(##, **, - 등)를 절대 사용하지 마세요. 반드시 제공된 HTML 태그만 사용해야 합니다.
                            2. 어투: 모든 문장 끝은 '~있음', '~가능', '~함', '~필요함' 등 명사형(음/슴체)으로 마무리하세요.
                            3. 내용 풍성하게: 외부 지식을 총동원하여 각 항목을 3~4문장 이상으로 매우 상세하게 채우세요. 문장 끝마다 반드시 줄바꿈 &lt;br&gt; 태그를 넣으세요.
                            4. 자금 사용계획 작성 규칙: 5번의 좌측 항목명은 반드시 '및'을 기준으로 <br> 태그를 사용해 줄바꿈 하세요.
                            5. 경쟁사 비교 분석표 규칙: 헤더(주요 경쟁사 A, B) 작성 시, 미리 제공된 양식대로 괄호 부분은 반드시 <br> 태그 아래에 작성하여 줄바꿈을 강제하세요.

                            [기업 정보]
                            - 기업명: {c_name} / 대표자: {rep_name} / 업종: {c_ind} / 사업자유형: {biz_type}
                            - 아이템: {item} / 시장현황: {market} / 차별화: {diff}
                            - 신청자금: {req_fund} ({fund_type})

                            [출력 양식]
                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업현황분석</h2>
                            <table style="width:100%; border-collapse: collapse; font-size: 1.05em; background-color:#f8f9fa; border-radius:15px; overflow:hidden; margin-bottom:15px; text-align:center;">
                              <tr style="border-bottom:1px solid #e0e0e0;">
                                <td style="padding:15px; width:12%; background-color:#eceff1; font-size:0.95em; white-space:nowrap;"><b>기업명</b></td><td style="padding:15px; width:21%;">{c_name}</td>
                                <td style="padding:15px; width:12%; background-color:#eceff1; font-size:0.95em; white-space:nowrap;"><b>사업자유형</b></td><td style="padding:15px; width:21%;">{biz_type}</td>
                                <td style="padding:15px; width:12%; background-color:#eceff1; font-size:0.95em; white-space:nowrap;"><b>업종</b></td><td style="padding:15px; width:22%;">{c_ind}</td>
                              </tr>
                              <tr>
                                <td style="padding:15px; background-color:#eceff1; font-size:0.95em; white-space:nowrap;"><b>대표자명</b></td><td style="padding:15px;">{rep_name}</td>
                                <td style="padding:15px; background-color:#eceff1; font-size:0.95em; white-space:nowrap;"><b>사업자번호</b></td><td style="padding:15px; line-height:1.4;">{biz_no}{corp_text}</td>
                                <td style="padding:15px; background-color:#eceff1; font-size:0.95em; white-space:nowrap;"><b>사업장주소</b></td><td style="padding:15px;">{address}</td>
                              </tr>
                              {add_biz_row}
                            </table>
                            <div style="margin-bottom:15px;">(해당 업종과 아이템의 잠재력, 향후 긍정적인 기대감을 외부 지식을 활용하여 3~4문장 이상 상세히 작성. 마침표 뒤 줄바꿈 &lt;br&gt;)</div>

                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. SWOT 분석</h2>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:15px; table-layout: fixed;">
                              <tr>
                                <td style="background-color:#e3f2fd; padding:20px; border-radius:15px; vertical-align:top; width:48.5%;"><b>S (강점)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(3~4줄 이상의 상세 분석)</div></td>
                                <td style="width:3%;"></td>
                                <td style="background-color:#ffebee; padding:20px; border-radius:15px; vertical-align:top; width:48.5%;"><b>W (약점)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(3~4줄 이상의 상세 분석)</div></td>
                              </tr>
                            </table>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:15px; table-layout: fixed;">
                              <tr>
                                <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; vertical-align:top; width:48.5%;"><b>O (기회)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(3~4줄 이상의 상세 분석)</div></td>
                                <td style="width:3%;"></td>
                                <td style="background-color:#fff3e0; padding:20px; border-radius:15px; vertical-align:top; width:48.5%;"><b>T (위협)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(3~4줄 이상의 상세 분석)</div></td>
                              </tr>
                            </table>

                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 시장현황 및 경쟁력 비교</h2>
                            <div style="background-color:#f3e5f5; padding:20px; border-radius:15px; margin-bottom:15px;">
                              <b>📊 시장 현황 분석</b><br><br>&bull; (해당 업종 시장 트렌드를 동원하여 3~4줄 상세 요약)
                            </div>
                            <div style="margin-top:15px; padding:15px; background-color:#fff; border-radius:15px; border:1px solid #e0e0e0;">
                              <b>⚔️ 주요 경쟁사 비교 분석표</b><br>
                              <table style="width:100%; border-collapse: collapse; text-align:center; font-size:0.95em; margin-top:10px;">
                                <tr style="background-color:#eceff1;">
                                  <th style="padding:12px; border:1px solid #ccc; width:20%;">비교 항목</th>
                                  <th style="padding:12px; border:1px solid #ccc; width:26%;">{c_name} (자사)</th>
                                  <th style="padding:12px; border:1px solid #ccc; width:27%;">주요 경쟁사 A<br><span style="font-size:0.85em; font-weight:normal; color:#555;">(경쟁사 특징 기재)</span></th>
                                  <th style="padding:12px; border:1px solid #ccc; width:27%;">주요 경쟁사 B<br><span style="font-size:0.85em; font-weight:normal; color:#555;">(경쟁사 특징 기재)</span></th>
                                </tr>
                                <tr>
                                  <td style="padding:12px; border:1px solid #ccc; font-weight:bold;">핵심 타겟/<br>포지셔닝</td>
                                  <td style="padding:12px; border:1px solid #ccc;">(자사 강점 요약)</td>
                                  <td style="padding:12px; border:1px solid #ccc;">(경쟁사 A 특징)</td>
                                  <td style="padding:12px; border:1px solid #ccc;">(경쟁사 B 특징)</td>
                                </tr>
                                <tr>
                                  <td style="padding:12px; border:1px solid #ccc; font-weight:bold;">차별화 요소<br><span style="font-size:0.85em; font-weight:normal; color:#555;">(경쟁우위)</span></td>
                                  <td style="padding:12px; border:1px solid #ccc;">(자사만의 기술/서비스)</td>
                                  <td style="padding:12px; border:1px solid #ccc;">(경쟁사 A 비교점)</td>
                                  <td style="padding:12px; border:1px solid #ccc;">(경쟁사 B 비교점)</td>
                                </tr>
                              </table>
                            </div>

                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 핵심경쟁력분석</h2>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:15px; text-align:center; table-layout: fixed;">
                              <tr>
                                <td style="border:1px solid #e0e0e0; border-radius:15px; padding:0; vertical-align:top; overflow:hidden; width:31.3%;">
                                  <div style="background-color:#e0f7fa; padding:15px; font-weight:bold; font-size:1.0em; border-bottom:1px solid #e0e0e0;">포인트 1<br><span style="font-size:1.15em; color:#00838F;">(핵심키워드 작성, 괄호제외)</span></div>
                                  <div style="padding:20px; font-size:0.95em; text-align:left; line-height:1.6;">&bull; (외부 지식 활용 구체적 분석 3~4줄)</div>
                                </td>
                                <td style="width:3%;"></td>
                                <td style="border:1px solid #e0e0e0; border-radius:15px; padding:0; vertical-align:top; overflow:hidden; width:31.3%;">
                                  <div style="background-color:#e0f7fa; padding:15px; font-weight:bold; font-size:1.0em; border-bottom:1px solid #e0e0e0;">포인트 2<br><span style="font-size:1.15em; color:#00838F;">(핵심키워드 작성, 괄호제외)</span></div>
                                  <div style="padding:20px; font-size:0.95em; text-align:left; line-height:1.6;">&bull; (외부 지식 활용 구체적 분석 3~4줄)</div>
                                </td>
                                <td style="width:3%;"></td>
                                <td style="border:1px solid #e0e0e0; border-radius:15px; padding:0; vertical-align:top; overflow:hidden; width:31.3%;">
                                  <div style="background-color:#e0f7fa; padding:15px; font-weight:bold; font-size:1.0em; border-bottom:1px solid #e0e0e0;">포인트 3<br><span style="font-size:1.15em; color:#00838F;">(핵심키워드 작성, 괄호제외)</span></div>
                                  <div style="padding:20px; font-size:0.95em; text-align:left; line-height:1.6;">&bull; (외부 지식 활용 구체적 분석 3~4줄)</div>
                                </td>
                              </tr>
                            </table>

                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">5. 자금 사용계획 (총 신청자금: {req_fund})</h2>
                            <table style="width:100%; border-collapse: collapse; text-align:left; margin-bottom:15px;">
                             <tr style="background-color:#eceff1;">
                               <th style="padding:15px; border:1px solid #ccc; border-radius:10px 0 0 0; width:20%; text-align:center;">구분 ({fund_type})</th>
                               <th style="padding:15px; border:1px solid #ccc; width:60%;">상세 사용계획 (외부 데이터 기반 구체적 산출)</th>
                               <th style="padding:15px; border:1px solid #ccc; border-radius:0 10px 0 0; width:20%; text-align:center;">사용예정금액</th>
                             </tr>
                             <tr>
                               <td style="padding:15px; border:1px solid #ccc; font-weight:bold; text-align:center;">(세부항목)<br>및<br>(용도)</td>
                               <td style="padding:15px; border:1px solid #ccc;">&bull; (사용처 및 산출 근거를 3~4줄로 구체적으로 기재)</td>
                               <td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0; text-align:center;">(금액)</td>
                             </tr>
                             <tr>
                               <td style="padding:15px; border:1px solid #ccc; font-weight:bold; text-align:center;">(세부항목)<br>및<br>(용도)</td>
                               <td style="padding:15px; border:1px solid #ccc;">&bull; (사용처 및 산출 근거를 3~4줄로 구체적으로 기재)</td>
                               <td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0; text-align:center;">(금액)</td>
                             </tr>
                             <tr>
                               <td style="padding:15px; border:1px solid #ccc; font-weight:bold; text-align:center;">(세부항목)<br>및<br>(용도)</td>
                               <td style="padding:15px; border:1px solid #ccc;">&bull; (사용처 및 산출 근거를 3~4줄로 구체적으로 기재)</td>
                               <td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0; text-align:center;">(금액)</td>
                             </tr>
                            </table>

                            <div style="page-break-before: always; page-break-inside: avoid; display: block; width: 100%;">
                                <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:0; font-size:24px; font-weight:bold;">6. 매출 1년 전망</h2>
                                <table style="width:100%; border-collapse: collapse; margin-bottom:15px; text-align:center; table-layout: fixed;">
                                  <tr>
                                    <td style="background-color:#e8eaf6; padding:20px; border-radius:15px; vertical-align:top; width:22.75%;">
                                      <div style="font-size:1.2em; font-weight:bold; color:#1565c0; margin-bottom:10px;">1단계 (도입)</div>
                                      <div style="font-size:0.95em; text-align:left; line-height:1.6; margin-bottom:15px;">&bull; (성장 전략 요약 3~4줄)</div>
                                      <div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">목표: OOO만원</div>
                                    </td>
                                    <td style="width:3%;"></td>
                                    <td style="background-color:#e8eaf6; padding:20px; border-radius:15px; vertical-align:top; width:22.75%;">
                                      <div style="font-size:1.2em; font-weight:bold; color:#1565c0; margin-bottom:10px;">2단계 (성장)</div>
                                      <div style="font-size:0.95em; text-align:left; line-height:1.6; margin-bottom:15px;">&bull; (성장 전략 요약 3~4줄)</div>
                                      <div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">목표: OOO만원</div>
                                    </td>
                                    <td style="width:3%;"></td>
                                    <td style="background-color:#e8eaf6; padding:20px; border-radius:15px; vertical-align:top; width:22.75%;">
                                      <div style="font-size:1.2em; font-weight:bold; color:#1565c0; margin-bottom:10px;">3단계 (확장)</div>
                                      <div style="font-size:0.95em; text-align:left; line-height:1.6; margin-bottom:15px;">&bull; (성장 전략 요약 3~4줄)</div>
                                      <div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">목표: OOO만원</div>
                                    </td>
                                    <td style="width:3%;"></td>
                                    <td style="background-color:#e8eaf6; padding:20px; border-radius:15px; vertical-align:top; width:22.75%;">
                                      <div style="font-size:1.2em; font-weight:bold; color:#1565c0; margin-bottom:10px;">4단계 (안착)</div>
                                      <div style="font-size:0.95em; text-align:left; line-height:1.6; margin-bottom:15px;">&bull; (성장 전략 요약 3~4줄)</div>
                                      <div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">최종목표: OOO만원</div>
                                    </td>
                                  </tr>
                                </table>
                                [GRAPH_INSERT_POINT]
                            </div>

                            <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">7. 성장비전 및 AI 컨설턴트 코멘트</h2>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:20px; text-align:center; table-layout: fixed;">
                              <tr>
                                <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; vertical-align:top; width:31.3%;">
                                  <b style="font-size:1.1em;">🌱 단기 비전</b><br><br><div style="text-align:left; line-height:1.6;">&bull; (핵심 비전 3~4줄)</div>
                                </td>
                                <td style="width:3%;"></td>
                                <td style="background-color:#fff3e0; padding:20px; border-radius:15px; vertical-align:top; width:31.3%;">
                                  <b style="font-size:1.1em;">🚀 중기 비전</b><br><br><div style="text-align:left; line-height:1.6;">&bull; (핵심 비전 3~4줄)</div>
                                </td>
                                <td style="width:3%;"></td>
                                <td style="background-color:#ffebee; padding:20px; border-radius:15px; vertical-align:top; width:31.3%;">
                                  <b style="font-size:1.1em;">👑 장기 비전</b><br><br><div style="text-align:left; line-height:1.6;">&bull; (핵심 비전 3~4줄)</div>
                                </td>
                              </tr>
                            </table>
                            
                            <div style="background-color:#eeeeee; border-left:5px solid #1565c0; padding:20px; border-radius:15px; margin-top:15px; line-height:1.6;">
                              <b>💡 핵심 인증 및 특허 확보 조언:</b><br><br>
                              &bull; (기업 업종에 맞는 필수 인증 혜택 및 전략을 1~2줄로 핵심만 간결히 요약. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)<br>
                              &bull; (아이템 보호를 위한 지식재산권 전략을 1~2줄로 핵심만 간결히 요약. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)
                            </div>
                            """
                            
                            max_retries = 3
                            for attempt in range(max_retries):
                                try:
                                    response = model.generate_content(prompt)
                                    st.session_state["generated_report"] = response.text
                                    status.update(label="✅ AI기업분석리포트 생성 완료!", state="complete")
                                    st.balloons()
                                    break
                                except Exception as e:
                                    if "429" in str(e) and attempt < max_retries - 1:
                                        status.update(label=f"⏳ 구글 서버 지연 (할당량 초과). 5초 후 재시도합니다... ({attempt+1}/{max_retries})", state="running")
                                        time.sleep(5)
                                    else:
                                        raise e
                        except Exception as e:
                            status.update(label=f"❌ 오류가 발생했습니다. API 키 권한을 확인해주세요. (상세: {str(e)})", state="error")
                            st.stop()

                raw_text = st.session_state.get("generated_report", "")
                if "```html" in raw_text:
                    response_text = raw_text.split("```html")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    response_text = raw_text.split("```")[1].split("```")[0].strip()
                else:
                    response_text = raw_text.strip()
                    
                # 스트림릿 코드 블록 오작동 방지를 위해 줄 시작 공백 제거
                response_text = "\n".join([line.lstrip() for line in response_text.split("\n")])

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
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>{c_name} AI기업분석리포트</title>
                    <style>
                        * {{ box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                        body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; padding: 40px; line-height: 1.6; color: #333; max-width: 1000px; margin: 0 auto; font-size: 16px; background-color: #fff; }}
                        h1 {{ color: #111; text-align: center; margin-bottom: 40px; font-size: 32px; font-weight: bold; }}
                        @media print {{ 
                            @page {{ size: A4; margin: 15mm; }}
                            body {{ padding: 0 !important; font-size: 14px !important; color: black !important; max-width: 100% !important; }} 
                            h1 {{ margin: 0 0 30px 0 !important; font-size: 28px !important; }}
                            h2.section-title {{ page-break-before: always !important; margin-top: 0 !important; font-size: 20px !important; padding-bottom: 4px !important; border-bottom: 2px solid #174EA6 !important; }}
                            h2.section-title:first-of-type {{ page-break-before: avoid !important; margin-top: 20px !important; }}
                            table {{ font-size: 13px !important; margin-bottom: 10px !important; width: 100% !important; table-layout: fixed !important; }}
                            th, td {{ padding: 10px !important; word-wrap: break-word; vertical-align: top; }}
                        }}
                    </style>
                </head>
                <body>
                    <h1>📋 AI기업분석리포트: {c_name}</h1>
                    <hr style="margin-bottom: 30px;">
                    {response_text.replace('[GRAPH_INSERT_POINT]', plotly_html)}
                </body>
                </html>
                """
                st.download_button(label="📥 HTML 파일로 저장", data=html_export, file_name=f"{safe_file_name}_기업분석리포트.html", mime="text/html", type="primary")

            except Exception as e:
                st.error(f"❌ 시스템 오류 발생: {str(e)}")

    # ---------------------------------------------------------
    # [모드 B: 2. 정책자금 매칭 리포트]
    # ---------------------------------------------------------
    elif st.session_state["view_mode"] == "MATCHING":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력').strip()
        
        st.title("🎯 AI 정책자금 최적화 매칭 리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")
        
        if not st.session_state["api_key"]:
            st.error("⚠️ 좌측 사이드바에 API 키를 입력하세요.")
        else:
            try:
                if "generated_matching" not in st.session_state:
                    with st.status("🚀 제미나이(Gemini)가 전년도 매출 기준으로 심사를 진행 중입니다...", expanded=True) as status:
                        try:
                            model_name = get_best_model_name()
                            model = genai.GenerativeModel(model_name)
                            
                            tax_status, fin_status = d.get('in_tax_status', '무'), d.get('in_fin_status', '무')
                            
                            kibo_debt = safe_int(d.get('in_debt_kibo', 0))
                            kodit_debt = safe_int(d.get('in_debt_kodit', 0))
                            guarantee_status = "기보 이용중(신보 불가)" if kibo_debt > 0 else ("신보 이용중(기보 불가)" if kodit_debt > 0 else "신보/기보 자유선택 가능")
                            
                            total_debt_val = sum([
                                safe_int(d.get('in_debt_kosme', 0)), safe_int(d.get('in_debt_semas', 0)),
                                safe_int(d.get('in_debt_koreg', 0)), kodit_debt,
                                kibo_debt, safe_int(d.get('in_debt_etc', 0)),
                                safe_int(d.get('in_debt_credit', 0)), safe_int(d.get('in_debt_coll', 0))
                            ])
                            total_debt = format_kr_currency(total_debt_val)
                            
                            s_25_val = safe_int(d.get('in_sales_2025', 0))
                            s_25 = format_kr_currency(s_25_val)
                            s_cur = format_kr_currency(safe_int(d.get('in_sales_current', 0)))
                            
                            c_ind, biz_type, item = d.get('in_industry', '미입력'), d.get('in_biz_type', '개인'), d.get('in_item_desc', '미입력')
                            nice_score = safe_int(d.get('in_nice_score', 0))
                            fund_type = d.get('in_fund_type', '운전자금')
                            req_fund = format_kr_currency(safe_int(d.get('in_req_amount', 0)))
                            
                            certs = []
                            if d.get('in_chk_1', False): certs.append("소상공인")
                            if d.get('in_chk_2', False): certs.append("창업기업")
                            if d.get('in_chk_3', False): certs.append("여성기업")
                            if d.get('in_chk_4', False): certs.append("이노비즈")
                            if d.get('in_chk_6', False): certs.append("벤처")
                            if d.get('in_chk_7', False): certs.append("뿌리기업")
                            if d.get('in_chk_10', False): certs.append("ISO")
                            if d.get('in_chk_11', False): certs.append("HACCP")
                            cert_status = ", ".join(certs) if certs else "미보유"
                            
                            pat_str = ""
                            if d.get('in_has_patent') == '유':
                                pat_str += f"[보유] 특허출원 {d.get('in_pat_apply','0')}건, 특허등록 {d.get('in_pat_reg','0')}건, 상표등록 {d.get('in_tm_reg','0')}건, 디자인등록 {d.get('in_design_reg','0')}건. "
                            if d.get('in_buy_patent') == '유':
                                pat_str += f"[매입예정] 희망특허: {d.get('in_buy_pat_desc','')}, 예상금액: {d.get('in_buy_pat_amount',0)}만원. "
                            if not pat_str:
                                pat_str = "특허/지재권 없음"
                            
                            biz_years = 0
                            start_date_str = d.get('in_start_date', '').strip()
                            if start_date_str:
                                try: biz_years = max(0, 2026 - int(start_date_str[:4]))
                                except: pass
                                
                            employee_count = safe_int(d.get('in_employee_count', 0))
                            
                            prompt = f"""
                            당신은 전문 경영컨설턴트입니다. 마크다운 기호 절대 금지. 
                            ※ 모든 문장은 반드시 '~음', '~함', '~임', '~기대됨' 등의 명사형으로 끝내야 합니다. '~습니다', '~합니다', '~해요' 등의 서술어는 절대 사용 금지!!!
                            절대 HTML 태그를 들여쓰기(Indentation) 하지 마세요. 모든 코드는 왼쪽 끝에 붙여서 작성하세요.

                            [입력] 기업명:{c_name} / 업종:{c_ind} / 상시근로자수:{employee_count}명 / 전년매출:{s_25} / 총기대출:{total_debt} / 인증현황:{cert_status} / 특허현황:{pat_str} / 희망 필요자금:{req_fund}
                            
                            [AI 작성 흔적 제거 및 전문가 톤 강제]
                            - "결론적으로", "요약하자면", "이처럼", "도움이 될 것입니다" 등 AI 특유의 기계적인 표현을 절대 사용하지 마세요.
                            - 실제 1타 경영컨설턴트가 며칠간 분석하여 직접 작성한 것처럼, 단호하고 설득력 있는 실무 비즈니스 용어와 자연스러운 문장 흐름을 유지하세요.
                            - 귀하의 방대한 지식베이스(외부 시장 데이터, 최신 트렌드, 구체적 통계 수치)를 적극적으로 끌어와 내용을 극도로 풍성하고 전문적으로 채우세요.

                            [자금 추천 순위 및 절대 룰]
                            1. 업종 및 규모에 따른 순위 룰:
                               - 제조업: 중진공 -> 소진공 -> 신용보증기금/기술보증기금 -> 신용보증재단 -> 은행권 협약
                               - 비제조업 (직원 5명 이하 AND 전년매출 50억 이하): 소진공 -> 신용보증기금/기술보증기금 -> 신용보증재단 -> 은행권 협약
                               - 비제조업 (그 외): 중진공 -> 소진공 -> 신용보증기금/기술보증기금 -> 신용보증재단 -> 은행권 협약
                            2. 보증기관 중복 금지 룰:
                               - 현재 기업의 보증 이용 상태: {guarantee_status}
                               - 기대출에 '기술보증기금'이 있다면 무조건 '기술보증기금'과 '신용보증재단'만 이용 가능 (신용보증기금 절대 추천 불가).
                               - 기대출에 '신용보증기금'이 있다면 무조건 '신용보증기금'과 '신용보증재단'만 이용 가능 (기술보증기금 절대 추천 불가).
                            3. 예상 금액 추출 룰:
                               - 외부 지식 및 중진공/보증기관 한도 산출 방식(매출액, 기대출 등)을 참고하여 실현 가능한 예상 금액을 직접 추산해서 기재할 것.
                            4. 보완 조언 룰 (인증/특허 활용):
                               - 이 기업의 인증({cert_status}) 및 특허 현황({pat_str})을 바탕으로, 추가적인 자금 조달처나 금리 우대 혜택 등을 방대한 외부 데이터를 검색/참고하여 컨설팅할 것.
                            5. 연체 컷오프: 세금/금융연체 '유'인 경우 1~4순위 비우고 연체 해소 조언만 작성.
                            6. 분량 제한: PDF 인쇄 시 무조건 1페이지에 모두 들어갈 수 있도록, 각 항목의 사유와 전략은 핵심만 1~2줄로 아주 간결하게 작성하세요.

                            [출력 양식]
                            <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업 스펙 진단 요약</h2>
                            <div style="background-color:#f8f9fa; padding:20px; border-radius:15px; border:1px solid #e0e0e0; margin-bottom:15px;">
                              <b>기업명:</b> {c_name} | <b>업종:</b> {c_ind} ({biz_type}) | <b>업력:</b> 약 {biz_years}년 | <b>상시근로자:</b> {employee_count}명 <br>
                              <b>NICE 점수:</b> {nice_score}점 | <b>기술/벤처 인증:</b> {cert_status} | <b>특허정보:</b> {pat_str} <br>
                              <b>전년도매출:</b> <span style="color:#1565c0; font-weight:bold;">{s_25}</span> | <b>총 기대출:</b> <span style="color:red;">{total_debt}</span> | <b style="font-size:1.15em;">희망 필요자금: {req_fund}</b>
                            </div>
                            <div style="margin-bottom:20px;">(1~2줄 아주 짧은 요약. &lt;br&gt;)</div>

                            <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. 우선순위 추천 정책자금 (1~2순위)</h2>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:15px; table-layout: fixed;">
                              <tr>
                                <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32; vertical-align:top; width:48.5%;">
                                  <b style="font-size:1.2em; color:#2e7d32;">🥇 1순위: [추천 기관명] / [세부 자금명]<br>AI 추산 예상 한도</b><br><br>&bull; (사유 1~2줄 핵심만 &lt;br&gt;)<br>&bull; (전략 1~2줄 핵심만 &lt;br&gt;)
                                </td>
                                <td style="width:3%;"></td>
                                <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32; vertical-align:top; width:48.5%;">
                                  <b style="font-size:1.2em; color:#2e7d32;">🥈 2순위: [신보 or 기보 중 택1 (절대 룰 준수)] / [상품명]<br>AI 추산 예상 한도</b><br><br>&bull; (사유 1~2줄 핵심만 &lt;br&gt;)<br>&bull; (전략 1~2줄 핵심만 &lt;br&gt;)
                                </td>
                              </tr>
                            </table>

                            <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 후순위 추천 (플랜 B - 3~4순위)</h2>
                            <table style="width:100%; border-collapse: collapse; margin-bottom:15px; table-layout: fixed;">
                              <tr>
                                <td style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00; vertical-align:top; width:48.5%;">
                                  <b style="font-size:1.2em; color:#ef6c00;">🥉 3순위: [지역신보] / [자금명]<br>AI 추산 예상 한도</b><br><br>&bull; (사유 1~2줄 핵심만 &lt;br&gt;)<br>&bull; (기금 우선진행 전략 1~2줄 핵심만 &lt;br&gt;)
                                </td>
                                <td style="width:3%;"></td>
                                <td style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00; vertical-align:top; width:48.5%;">
                                  <b style="font-size:1.2em; color:#ef6c00;">🏅 4순위: [시중은행 연계자금 등] / [자금명]<br>AI 추산 예상 한도</b><br><br>&bull; (사유 1~2줄 핵심만 &lt;br&gt;)<br>&bull; (전략 1~2줄 핵심만 &lt;br&gt;)
                                </td>
                              </tr>
                            </table>

                            <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 심사 전 필수 체크리스트 및 보완 가이드</h2>
                            <div style="background-color:#ffebee; border-left:5px solid #d32f2f; padding:15px; border-radius:15px; margin-top:15px;">
                              <b style="font-size:1.1em; color:#c62828;">🚨 보완 조언 (특허/인증 활용 방안 포함):</b><br><br>&bull; (외부 데이터를 활용한 구체적인 전략 1~2줄 &lt;br&gt;)<br>&bull; (외부 데이터를 활용한 구체적인 전략 1~2줄 &lt;br&gt;)
                            </div>
                            """
                            
                            max_retries = 3
                            for attempt in range(max_retries):
                                try:
                                    response = model.generate_content(prompt)
                                    st.session_state["generated_matching"] = response.text
                                    status.update(label="✅ 최적화 매칭 리포트 생성 완료!", state="complete")
                                    st.balloons()
                                    break
                                except Exception as e:
                                    if "429" in str(e) and attempt < max_retries - 1:
                                        status.update(label=f"⏳ 구글 서버 지연 (할당량 초과). 5초 후 재시도합니다... ({attempt+1}/{max_retries})", state="running")
                                        time.sleep(5)
                                    else:
                                        raise e
                        except Exception as e:
                            status.update(label=f"❌ 오류 발생. API 키(새 계정)를 확인해주세요. (상세: {str(e)})", state="error")
                            st.stop()
                
                raw_text = st.session_state.get("generated_matching", "")
                if "```html" in raw_text:
                    response_text = raw_text.split("```html")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    response_text = raw_text.split("```")[1].split("```")[0].strip()
                else:
                    response_text = raw_text.strip()
                    
                response_text = "\n".join([line.lstrip() for line in response_text.split("\n")])
                    
                st.markdown(response_text, unsafe_allow_html=True)
                
                st.divider()
                st.subheader("💾 HTML 리포트 다운로드")
                safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
                if not safe_file_name: safe_file_name = "업체"
                
                html_export = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>{c_name} 정책자금 매칭 리포트</title>
                    <style>
                        * {{ box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                        body {{ font-family: 'Malgun Gothic', sans-serif; padding: 30px; line-height: 1.5; color: #333; max-width: 1000px; margin: 0 auto; background-color: #fff; }}
                        @media print {{ 
                            @page {{ size: A4; margin: 10mm; }}
                            body {{ padding: 0 !important; font-size: 11.5px !important; color: black !important; max-width: 100% !important; zoom: 0.85; }} 
                            h1 {{ margin: 0 0 10px 0 !important; font-size: 20px !important; }}
                            h2 {{ margin: 10px 0 5px 0 !important; font-size: 15px !important; padding-bottom: 2px !important; border-bottom: 2px solid #174EA6 !important; }}
                            div {{ padding: 10px !important; margin-bottom: 8px !important; border-radius: 8px !important; page-break-inside: avoid; line-height: 1.3 !important; }}
                            table {{ font-size: 11.5px !important; margin-bottom: 8px !important; width: 100% !important; table-layout: fixed !important; }}
                            th, td {{ padding: 8px !important; word-wrap: break-word; vertical-align: top; }}
                        }}
                    </style>
                </head>
                <body>
                    <h1>🎯 AI 정책자금 최적화 매칭 리포트: {c_name}</h1>
                    <hr style="margin-bottom: 15px;">
                    {response_text}
                </body>
                </html>
                """
                st.download_button(label="📥 매칭리포트 HTML 파일로 다운로드", data=html_export, file_name=f"{safe_file_name}_매칭리포트.html", mime="text/html", type="primary")

            except Exception as e:
                st.error(f"❌ 분석 중 오류 발생: {str(e)}")

    # ---------------------------------------------------------
    # [모드 C: 3. 기관 맞춤형 융자/사업계획서 생성]
    # ---------------------------------------------------------
    elif st.session_state["view_mode"] == "PLAN":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
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
        
        s_25 = format_kr_currency(d.get('in_sales_2025', 0))
        s_cur = format_kr_currency(d.get('in_sales_current', 0))
        sales_24 = format_kr_currency(d.get('in_sales_2024', 0))
        sales_23 = format_kr_currency(d.get('in_sales_2023', 0))
        
        req_fund = format_kr_currency(d.get('in_req_amount', 0))
        fund_type, fund_purpose = d.get('in_fund_type', '운전자금'), d.get('in_fund_purpose', '미입력')
        item, market, diff, route = d.get('in_item_desc', '미입력'), d.get('in_market_status', '미입력'), d.get('in_diff_point', '미입력'), d.get('in_sales_route', '')
        
        biz_years = 0
        if d.get('in_start_date', '').strip():
            try: biz_years = max(0, 2026 - int(d.get('in_start_date', '')[:4]))
            except: pass
            
        certs = []
        if d.get('in_chk_1', False): certs.append("소상공인")
        if d.get('in_chk_2', False): certs.append("창업기업")
        if d.get('in_chk_3', False): certs.append("여성기업")
        if d.get('in_chk_4', False): certs.append("이노비즈")
        if d.get('in_chk_6', False): certs.append("벤처")
        if d.get('in_chk_7', False): certs.append("뿌리기업")
        if d.get('in_chk_10', False): certs.append("ISO")
        if d.get('in_chk_11', False): certs.append("HACCP")
        cert_status = ", ".join(certs) if certs else "미보유"

        pat_str = ""
        if d.get('in_has_patent') == '유':
            pat_str += f"출원 {d.get('in_pat_apply','0')}건, 등록 {d.get('in_pat_reg','0')}건, 상표 {d.get('in_tm_reg','0')}건, 디자인 {d.get('in_design_reg','0')}건."
        else:
            pat_str = "특허/지재권 미보유"
            
        # 수출 정보 세팅
        is_export = d.get('in_is_export', '무')
        exp_24 = format_kr_currency(d.get('in_exp_2024', 0))
        exp_25 = format_kr_currency(d.get('in_exp_2025', 0))
        exp_cur = format_kr_currency(d.get('in_exp_current', 0))
        export_info = f"유 (24년 {exp_24}, 25년 {exp_25}, 금년 {exp_cur})" if is_export == '유' else "무 (전액 내수)"

        st.title("📝 기관/서류별 맞춤형 융자·사업계획서 자동 생성기")
        st.info("💡 좌측은 '공통 융자신청서', 우측은 '자금별 사업계획서(별첨)'입니다. 버튼을 누르면 완벽한 HTML 양식으로 생성됩니다.")

        tabs = st.tabs(["1. 중진공", "2. 소진공", "3. 신보/재단", "4. 기술보증기금", "5. 제안용(IR)"])

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
            
            col_dd1, col_dd2 = st.columns(2)
            with col_dd1:
                main_fund_type = st.selectbox("💡 1. 대분류 자금종류", list(fund_categories.keys()))
            with col_dd2:
                kosme_fund_type = st.selectbox("💡 2. 세부 자금종류", fund_categories[main_fund_type])
            
            col_p1, col_p2 = st.columns(2)
            
            # --- 좌측: 융자신청서 (공통 양식) ---
            with col_p1:
                st.markdown("#### 📄 중진공 융자신청서(공통)")
                st.caption("💡 포커스: 자금소요 내역, 상환계획, 27/28년 예상매출 및 공정도")
                
                if st.button("🚀 중진공 융자신청서(공통) 바로보기", use_container_width=True):
                    with st.status("🚀 융자신청서(공통양식) 빈칸을 완벽하게 채우는 중입니다...", expanded=True) as status:
                        try:
                            model_name = get_best_model_name()
                            model = genai.GenerativeModel(model_name)
                            
                            prompt_loan = f"""
                            당신은 정책자금 전문 경영컨설턴트입니다. 
                            중진공 융자신청서(공통양식)를 아래 [작성 규칙]에 맞춰 HTML 표로 출력하세요. 마크다운 절대 금지.
                            절대 HTML 태그를 들여쓰기(Indentation) 하지 마세요. 모든 코드는 왼쪽 끝에 붙여서 작성하세요.

                            [기업 데이터]
                            - 기업명: {c_name} / 대표자: {rep_name} / 사업자유형: {biz_type} / 업종: {c_ind}
                            - 본사주소: {address} / 학력: {edu_school} {edu_major} / 자택: {home_addr}
                            - 매출: 23년({sales_23}), 24년({sales_24}), 금년({s_cur})
                            - 수출여부: {export_info}
                            - 신청자금: {req_fund} ({fund_type} / {fund_purpose})
                            - 아이템: {item} / 시장: {market} / 차별성: {diff} / 판매루트: {route}
                            - 기초 공정: {process_desc}

                            [작성 규칙 - 절대 엄수]
                            1. 체크박스는 무조건 '▣' 기호를 사용하세요. 그 외는 '□'.
                            2. 아래 항목은 지정된 값으로 '▣' 처리: 담보(▣신용), 융자방식(▣직접대출), 고정금리(▣해당없음), 이차보전(▣해당없음), 기업진단(▣미신청)
                            3. 대시보드에 없는 정보(직원, 주주, 경영진 등) 칸은 무조건 공란(빈칸)으로 두세요.
                            4. [제품생산공정도]는 입력된 '기초 공정'을 바탕으로 제조/서비스업에 맞는 전문 용어를 사용하여 최소 3~4개의 상세한 단락으로 나누어 엄청나게 길고 풍성하게 살을 붙이세요.
                            5. [매출현황]의 '27년(예상)'과 '28년(예상)' 매출은 현재 매출을 기반으로 스케일업(J커브) 성장을 가정한 현실적인 금액을 자동으로 계산하여 채워 넣으세요. 수출액 칸에는 24년({exp_24}), 금년({exp_cur}) 수치를 넣고 예상 수출액도 채워주세요. 수출이 없으면 빈칸으로 두세요.
                            6. [사업계획서 (자금활용 계획)] 시작 직전에 반드시 `<div style="page-break-before: always; padding-top: 20px;"></div>` 태그를 삽입하여 인쇄 시 페이지가 1페이지(현황)와 2페이지(계획)로 깔끔하게 나뉘도록 하세요.
                            7. '윤리준수 약속' 표는 작성하지 마세요.

                            [AI 작성 흔적 제거 및 전문가 톤 강제]
                            - "결론적으로", "요약하자면", "이처럼", "도움이 될 것입니다" 등 AI 특유의 기계적인 표현을 절대 사용하지 마세요.
                            - 실제 1타 경영컨설턴트가 며칠간 분석하여 직접 작성한 것처럼, 단호하고 설득력 있는 실무 비즈니스 용어와 자연스러운 문장 흐름을 유지하세요.
                            - 출력 길이 제한을 무시하고, 각 서술 항목마다 당신이 생성할 수 있는 최대 길이의 텍스트(각 칸별로 800자 이상)를 쏟아내세요.
                            - 귀하의 방대한 지식베이스(외부 시장 데이터, 최신 트렌드, 구체적 통계 수치)를 적극적으로 끌어와 내용을 극도로 풍성하고 전문적으로 채우세요.

                            [출력 HTML 뼈대 - 반드시 아래 구조의 표를 사용할 것]
                            <h2 style="text-align:center;">중소기업 정책자금 융자신청서</h2>
                            
                            <h3>[신청내용]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:left; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">신청자금명</th><td style="border:1px solid #333; padding:8px;">▣ {kosme_fund_type}</td><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">신청금액</th><td style="border:1px solid #333; padding:8px;">{req_fund}</td></tr>
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">담보종류</th><td colspan="3" style="border:1px solid #333; padding:8px;">▣ 신용 &nbsp;&nbsp; □ 부동산 &nbsp;&nbsp; □ 기타</td></tr>
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">융자방식</th><td colspan="3" style="border:1px solid #333; padding:8px;">▣ 중진공 직접대출 &nbsp;&nbsp; □ 대리대출</td></tr>
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">고정금리/이차보전</th><td colspan="3" style="border:1px solid #333; padding:8px;">▣ 해당없음</td></tr>
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">기업진단 희망여부</th><td colspan="3" style="border:1px solid #333; padding:8px;">▣ 미신청 &nbsp;&nbsp; □ 신청</td></tr>
                            </table>

                            <h3>[기업현황 및 실질적 기업주]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:center; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">소재지</th><td colspan="3" style="border:1px solid #333; padding:8px; text-align:left;">본사: {address}</td></tr>
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">기업주 성명</th><td style="border:1px solid #333; padding:8px;">{rep_name}</td><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">직위</th><td style="border:1px solid #333; padding:8px;">대표</td></tr>
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">학력</th><td style="border:1px solid #333; padding:8px;">{edu_school} {edu_major}</td><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">주택</th><td style="border:1px solid #333; padding:8px;">{home_addr}</td></tr>
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">대표자와 동일여부</th><td colspan="3" style="border:1px solid #333; padding:8px; text-align:left;">▣ 같음 &nbsp;&nbsp; □ 다름</td></tr>
                            </table>

                            <h3>[매출 현황]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:center; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">구분</th><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">23년</th><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">24년</th><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">금년(당월)</th><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">27년(예상)</th><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">28년(예상)</th></tr>
                            <tr><td style="border:1px solid #333; padding:8px;">총매출액</td><td style="border:1px solid #333; padding:8px;">{sales_23}</td><td style="border:1px solid #333; padding:8px;">{sales_24}</td><td style="border:1px solid #333; padding:8px;">{s_cur}</td><td style="border:1px solid #333; padding:8px; color:blue; font-weight:bold;">(자동계산)</td><td style="border:1px solid #333; padding:8px; color:blue; font-weight:bold;">(자동계산)</td></tr>
                            <tr><td style="border:1px solid #333; padding:8px;">수출액</td><td style="border:1px solid #333; padding:8px;"> </td><td style="border:1px solid #333; padding:8px;">{exp_24}</td><td style="border:1px solid #333; padding:8px;">{exp_cur}</td><td style="border:1px solid #333; padding:8px;">(자동계산)</td><td style="border:1px solid #333; padding:8px;">(자동계산)</td></tr>
                            </table>
                            [GRAPH_INSERT_POINT]

                            <h3>[주요 생산제품 개요]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:left; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0; width:20%;">제품용도 및 특성</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(최소 3~4개의 거대한 문단으로 매우 깊이 있고 방대하게 작성할 것)</td></tr>
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0;">제품생산공정도</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(대시보드 공정도를 바탕으로 전문 용어를 사용하여 최소 3~4개 문단으로 방대하게 작성할 것)</td></tr>
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0;">시장상황</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(외부 데이터를 기반으로 시장규모, 경쟁업체 등 최소 3~4개 문단으로 방대하게 작성할 것)</td></tr>
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0;">기술품질경쟁력</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(경쟁사 대비 차별성을 최소 3~4개 문단으로 방대하게 작성할 것)</td></tr>
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0;">판매계획</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(타겟 고객 및 판매 시나리오를 최소 3~4개 문단으로 방대하게 작성할 것)</td></tr>
                            </table>

                            <div style="page-break-before: always; padding-top: 20px;"></div>

                            <h3>[사업계획서 (자금활용 계획)]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:left; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0; width:20%;">사업내용 및 목적/효과</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(자금 활용 시 예상되는 원가절감, 매출상승, 생산성 향상 효과를 최소 3~4개의 거대한 문단으로 방대하게 작성할 것)</td></tr>
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0;">자금 소요내역</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(시설/운전 자금을 구분하여, 인건비/마케팅/기계 등 세부 용도와 예상 금액을 표나 리스트 형태로 최소 3~4개 문단으로 방대하게 쪼개서 작성할 것)</td></tr>
                            </table>
                            """
                            # 그래프 데이터 생성
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
                            fig.add_trace(go.Scatter(
                                x=monthly_labels, y=monthly_vals, mode='lines+markers+text',
                                text=[format_kr_currency(v) for v in monthly_vals], textposition="top center",
                                textfont=dict(size=11), line=dict(color='#1E88E5', width=4, shape='spline'),
                                marker=dict(size=10, color='#FF5252', line=dict(width=2, color='white'))
                            ))
                            fig.update_layout(
                                title="📈 향후 1년 월별 매출 상승 곡선 시각화", xaxis_title="진행 월", yaxis_title="예상 매출액",
                                xaxis=dict(tickangle=0, showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
                                template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                            )
                            plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

                            response = model.generate_content(prompt_loan)
                            
                            # Markdown HTML block strip logic
                            raw_text = response.text
                            if "```html" in raw_text:
                                cleaned_html = raw_text.split("```html")[1].split("```")[0].strip()
                            elif "```" in raw_text:
                                cleaned_html = raw_text.split("```")[1].split("```")[0].strip()
                            else:
                                cleaned_html = raw_text.strip()
                            
                            # 들여쓰기(Indentation) 제거 로직 적용
                            cleaned_html = "\n".join([line.lstrip() for line in cleaned_html.split("\n")])
                            # 그래프 삽입
                            if "[GRAPH_INSERT_POINT]" in cleaned_html:
                                parts = cleaned_html.partition("[GRAPH_INSERT_POINT]")
                                cleaned_html = parts[0] + plotly_html + parts[2]
                                
                            st.session_state["kosme_result_type"] = "loan"
                            st.session_state["kosme_result_html"] = cleaned_html
                            status.update(label="✅ 공통 융자신청서 생성 완료!", state="complete")
                        except Exception as e:
                            status.update(label=f"❌ 오류 발생: {str(e)}", state="error")
            
            # --- 우측: 사업계획서 (별첨 양식) ---
            with col_p2:
                st.markdown(f"#### 📝 중진공 사업계획서 ({kosme_fund_type})")
                if kosme_fund_type == "청년전용창업자금":
                    st.caption("💡 포커스: 창업자 역량(실행력), J커브 성장성, 스케일업")
                elif kosme_fund_type == "개발기술사업화자금":
                    st.caption("💡 포커스: 양산 가능성, 시장성(매출), 기술의 사업화 구조")
                else:
                    st.caption("💡 포커스: 기술성, 양산 및 매출 확대, 고용창출 중심")
                
                if st.button(f"🚀 중진공 {kosme_fund_type} 바로보기", use_container_width=True):
                    with st.status(f"🚀 '{kosme_fund_type}' 전용 1타 심사역 로직으로 작성 중입니다...", expanded=True) as status:
                        try:
                            model_name = get_best_model_name()
                            model = genai.GenerativeModel(model_name)
                            
                            if kosme_fund_type == "청년전용창업자금":
                                prompt_plan = f"""
                                당신은 중소기업진흥공단의 깐깐한 심사역입니다. 마크다운 기호 금지. 순수 HTML 태그만 사용하세요.
                                절대 HTML 태그를 들여쓰기(Indentation) 하지 마세요. 모든 코드는 왼쪽 끝에 붙여서 작성하세요.
                                
                                [기업데이터]
                                - 기업명: {c_name} / 대표자: {rep_name} / 업력: {biz_years}년 / 경력: {career}
                                - 아이템: {item} / 시장현황: {market} / 경쟁우위: {diff}
                                
                                [청년전용창업자금 핵심 작성 룰]
                                1. 아이디어보다 "대표자의 문제 해결 능력과 실행력", "앞으로 폭발적으로 성장할 가능성"을 집중적으로 어필하세요.
                                2. 사업추진계획에는 작은 성과라도 테스트/피드백 결과를 반드시 포함시키고, 시장 성장 스토리(스케일업)를 엮으세요.
                                3. 자금 조달 계획은 "돈을 쓰면 반드시 성과로 직결되는 구조"로 설득력 있게 작성하세요.

                                [AI 작성 흔적 제거 및 분량 강제 (매우 중요!!!)]
                                - 전체 출력 결과물이 A4 용지 5장에 달하도록 당신이 생성할 수 있는 최대 길이의 텍스트를 쏟아내세요. 
                                - "결론적으로", "요약하자면", "이처럼", "도움이 될 것입니다" 등 AI 특유의 기계적인 표현을 절대 사용하지 마세요.
                                - 실제 1타 경영컨설턴트가 시장조사 보고서를 바탕으로 직접 작성한 것처럼, 단호하고 설득력 있는 실무 비즈니스 용어를 사용하세요.
                                - 귀하의 방대한 지식베이스(외부 시장 데이터, 최신 트렌드, 구체적 통계 수치)를 적극적으로 끌어와 내용을 꽉꽉 채우세요.

                                [출력 양식 - 무조건 이 HTML 표 양식을 100% 똑같이 유지할 것]
                                <h2 style="text-align:center; border:2px solid #333; padding:10px; margin-bottom:20px;">청년전용창업자금 세부계획서</h2>
                                
                                <table style="width:100%; border-collapse: collapse; border: 2px solid #333; text-align:center; font-size:14px; margin-bottom:30px;">
                                <tr>
                                <td rowspan="2" style="background-color:#f0f0f0; border:1px solid #333; width:15%; font-weight:bold;">신청내용</td>
                                <td style="background-color:#f0f0f0; border:1px solid #333; width:20%;">신청자 유형</td>
                                <td colspan="4" style="border:1px solid #333; text-align:left; padding-left:15px;">□ 예비창업자 <br>▣ 기창업자 (□ 3년 미만, □ 7년 미만)</td>
                                </tr>
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333;">자금구분</td>
                                <td colspan="4" style="border:1px solid #333; text-align:left; padding-left:15px;">▣ 청년전용창업자금 &nbsp;&nbsp;&nbsp;&nbsp; □ 청년전용창업자금(융복합)</td>
                                </tr>
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333; font-weight:bold;">참고항목</td>
                                <td style="background-color:#f0f0f0; border:1px solid #333;">창업관련 수상실적 및<br>정부지원사업 참여현황</td>
                                <td style="border:1px solid #333; background-color:#f0f0f0; padding:10px;">대회(사업)명</td>
                                <td style="border:1px solid #333; background-color:#f0f0f0;">수상(지원)내역</td>
                                <td style="border:1px solid #333; background-color:#f0f0f0;">일자(기간)</td>
                                <td style="border:1px solid #333; background-color:#f0f0f0;">주관기관</td>
                                </tr>
                                <tr>
                                <td style="border:1px solid #333;"></td><td style="border:1px solid #333;"></td><td style="border:1px solid #333; padding:15px;"></td><td style="border:1px solid #333;"></td><td style="border:1px solid #333;"></td><td style="border:1px solid #333;"></td>
                                </tr>
                                </table>

                                <h3>□ 사업 계획서</h3>
                                <table style="width:100%; border-collapse: collapse; border: 2px solid #333; font-size:14px; margin-bottom:20px;">
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:15px; width:20%; font-weight:bold; vertical-align:top;">창업 동기</td>
                                <td style="border:1px solid #333; padding:20px; vertical-align:top; text-align:left; line-height:1.8;">
                                (대표자의 뼈저린 현장 경험, 시장의 거시적 문제점, 타겟 고객의 미충족 수요를 엮어서 최소 4~5개의 거대한 문단으로 나누어, 1000자 이상의 압도적인 분량으로 매우 깊이 있게 서술. 일반적인 AI 요약체를 버리고 전문가의 통찰력이 담긴 긴 호흡의 칼럼처럼 작성할 것)
                                </td>
                                </tr>
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:15px; font-weight:bold; vertical-align:top;">창업아이템의 개요</td>
                                <td style="border:1px solid #333; padding:20px; vertical-align:top; text-align:left; line-height:1.8;">
                                (아이템의 핵심 내용, 타사 대비 차별성, 경쟁력, 기술 확장성을 외부 전문 데이터를 동원하여 최소 4~5개의 거대한 문단으로 나누어 1000자 이상 작성할 것)
                                </td>
                                </tr>
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:15px; font-weight:bold; vertical-align:top;">사업추진 계획</td>
                                <td style="border:1px solid #333; padding:20px; vertical-align:top; text-align:left; line-height:1.8;">
                                (1. 제품개발/품질관리 목표 2. 시장상황 및 수요 3. 마케팅 전략 4. 자금조달 및 중진공 상환계획을 각각 나누어 매우 구체적으로 최소 4~5개의 거대한 문단으로 1000자 이상 방대하게 작성할 것)
                                </td>
                                </tr>
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:15px; font-weight:bold; vertical-align:top;">기대 효과</td>
                                <td style="border:1px solid #333; padding:20px; vertical-align:top; text-align:left; line-height:1.8;">
                                (고용 창출 효과 및 사회/경제적 파급 효과를 구체적 숫자를 섞어 설득력 있게 최소 4~5개의 거대한 문단으로 1000자 이상 방대하게 작성할 것)
                                </td>
                                </tr>
                                </table>
                                [GRAPH_INSERT_POINT]
                                """
                            elif kosme_fund_type == "개발기술사업화자금":
                                prompt_plan = f"""
                                당신은 중소기업진흥공단의 깐깐한 심사역입니다. 마크다운 기호 금지. 순수 HTML 태그만 사용하세요.
                                절대 HTML 태그를 들여쓰기(Indentation) 하지 마세요. 모든 코드는 왼쪽 끝에 붙여서 작성하세요.
                                
                                [기업데이터]
                                - 기업명: {c_name} / 대표자: {rep_name} / 업력: {biz_years}년
                                - 아이템: {item} / 시장현황: {market} / 경쟁우위: {diff}
                                - 특허/인증: {cert_status} / {pat_str}
                                - 매출현황: 금년 {s_cur} / 수출여부: {export_info}
                                
                                [개발기술사업화자금 핵심 작성 룰]
                                1. R&D(기술개발) 중심이 아닌 "사업화(돈 버는 구조)" 중심으로 작성하세요. 기술 자체보다 '시장성', '양산 가능성', '실행력'을 압도적으로 강조해야 합니다.
                                2. 타겟 시장 규모(TAM/SAM/SOM), 구체적 고객, 구매 시나리오를 구체적인 수치와 함께 설득력 있게 제시하세요.
                                3. 차별성은 단순 스펙 비교가 아니라 "고객이 우리 제품을 사야만 하는 이유(수익성/원가/고객가치)"로 연결하세요.
                                4. "이 자금이 투입되면 즉각 양산/마케팅이 진행되어 J커브 매출이 발생할 기업"임을 강조하세요.
                                5. 판매계획 표의 3개 품목 줄을 모두 채우세요. 기업의 수출여부({export_info})를 반영하여, 수출이 없으면 수출액을 빈칸으로 두고 내수 위주로, 수출이 있으면 내수와 수출액을 현실적인 비율로 나누어 작성하세요.

                                [AI 작성 흔적 제거 및 분량 강제 (매우 중요!!!)]
                                - 전체 출력 결과물이 A4 용지 5장에 달하도록 당신이 생성할 수 있는 최대 길이의 텍스트를 쏟아내세요. 
                                - "결론적으로", "요약하자면", "이처럼", "도움이 될 것입니다" 등 AI 특유의 기계적인 표현을 절대 사용하지 마세요.
                                - 실제 1타 경영컨설턴트가 시장조사 보고서를 바탕으로 직접 작성한 것처럼, 단호하고 설득력 있는 실무 비즈니스 용어를 사용하세요.
                                - 귀하의 방대한 지식베이스(외부 시장 데이터, 최신 트렌드, 구체적 통계 수치)를 적극적으로 끌어와 서술형 칸을 각 800~1000자 이상의 꽉 찬 내용으로 채우세요.

                                [출력 양식 - 무조건 이 HTML 표 양식을 100% 똑같이 유지할 것]
                                <h2 style="text-align:center; border:2px solid #333; padding:10px; margin-bottom:20px;">개발기술사업화자금 신청기업 사업계획서</h2>
                                
                                <h3 style="margin-top:20px;">□ 신청 개발기술의 제품(상품 및 서비스) 개요</h3>
                                <table style="width:100%; border-collapse: collapse; border: 2px solid #333; font-size:14px; margin-bottom:20px; text-align:left;">
                                <tr>
                                <td rowspan="2" style="background-color:#f0f0f0; border:1px solid #333; width:20%; font-weight:bold; text-align:center;">사업화<br>제품·기술</td>
                                <td style="border:1px solid #333; padding:10px;">(제품명) {item}</td>
                                </tr>
                                <tr>
                                <td style="border:1px solid #333; padding:10px; line-height:1.6;">- R&D성공과제/특허기술 등: {pat_str}<br>- 관련기술 평가/인증 년월일: (가상 작성)</td>
                                </tr>
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:15px; font-weight:bold; text-align:center;">제품용도 및 특성<br><span style="font-size:0.9em; font-weight:normal;">(주요내용)</span></td>
                                <td style="border:1px solid #333; padding:20px; line-height:1.8;">
                                (고객의 Pain-point를 해결하는 제품/서비스의 핵심 용도와 특성을 최소 4~5개의 거대한 문단으로 1000자 이상 명확히 작성)
                                </td>
                                </tr>
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:15px; font-weight:bold; text-align:center;">대체, 경쟁제품과의<br>차별성</td>
                                <td style="border:1px solid #333; padding:20px; line-height:1.8;">
                                (경쟁사 대비 기술적 비교우위를 넘어, 수익성/원가/고객가치 측면의 사업적 차별성을 최소 4~5개의 거대한 문단으로 1000자 이상 작성)
                                </td>
                                </tr>
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:15px; font-weight:bold; text-align:center;">사업화(양산) 및<br>납품계획</td>
                                <td style="border:1px solid #333; padding:20px; line-height:1.8;">
                                - 양산 시작 후 3년 경과 여부: ▣ No <br>
                                (현재 시제품/MVP 완료 및 향후 구체적인 양산 일정, 유통망/납품처 확보 계획을 상세히 최소 4~5개의 거대한 문단으로 1000자 이상 작성)
                                </td>
                                </tr>
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:15px; font-weight:bold; text-align:center;">기대효과<br><span style="font-size:0.9em; font-weight:normal;">(기술의 파급효과)</span></td>
                                <td style="border:1px solid #333; padding:20px; line-height:1.8;">
                                (매출 증대, 수입 대체, 고용 창출 등 경제적/산업적 파급효과를 수치를 포함하여 최소 4~5개의 거대한 문단으로 1000자 이상 작성)
                                </td>
                                </tr>
                                </table>

                                <h3 style="margin-top:30px;">□ 신청 개발기술 제품(상품 또는 서비스) 영업계획</h3>
                                <h4 style="margin-top:10px;">○ 시장성</h4>
                                <table style="width:100%; border-collapse: collapse; border: 2px solid #333; text-align:center; font-size:13px; margin-bottom:20px; table-layout: fixed;">
                                <tr>
                                <td style="background-color:#f0f0f0; border:1px solid #333; font-weight:bold; padding:8px; width:16.6%;">판매형태</td>
                                <td colspan="5" style="border:1px solid #333; text-align:left; padding:8px;">주문판매( )%, 시장판매( )%, 임가공( )%, (내수( )%, 수출( )%) (합계 100%가 되도록 가상 분배)</td>
                                </tr>
                                <tr>
                                <td rowspan="2" style="background-color:#f0f0f0; border:1px solid #333; font-weight:bold; padding:8px; width:16.6%;">경쟁<br>현황</td>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:8px; width:16.6%;">제품명<br>(상품및서비스)</td>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:8px; width:16.6%;">시장규모</td>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:8px; width:16.6%;">주요기업체명<br>(1순위/2순위)</td>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:8px; width:16.6%;">귀사의 동업계 지위</td>
                                <td style="background-color:#f0f0f0; border:1px solid #333; padding:8px; width:16.6%;">경쟁<br>상태</td>
                                </tr>
                                <tr>
                                <td style="border:1px solid #333; padding:8px; line-height:1.4;">{item}</td>
                                <td style="border:1px solid #333; padding:8px;">(객관적 추산액)</td>
                                <td style="border:1px solid #333; padding:8px;">(가상의 주요경쟁사명)</td>
                                <td style="border:1px solid #333; padding:8px;">시설능력: (상/중/하)<br>시장지위: (상/중/하)</td>
                                <td style="border:1px solid #333; padding:8px;">(보통/과당/독점)</td>
                                </tr>
                                </table>
                                [GRAPH_INSERT_POINT]

                                <h4 style="margin-top:10px;">○ 판매계획</h4>
                                <table style="width:100%; border-collapse: collapse; border: 2px solid #333; text-align:center; font-size:13px; margin-bottom:20px; table-layout: fixed;">
                                <tr style="background-color:#f0f0f0;">
                                <th rowspan="2" style="border:1px solid #333; padding:8px; width:18%;">품목명</th>
                                <th rowspan="2" style="border:1px solid #333; padding:8px; width:18%;">생산능력<br>(수량/금액)</th>
                                <th rowspan="2" style="border:1px solid #333; padding:8px; width:18%;">판매처<br>(업체명)</th>
                                <th colspan="2" style="border:1px solid #333; padding:8px;">당해년도 판매액</th>
                                <th colspan="2" style="border:1px solid #333; padding:8px;">차년도 판매액</th>
                                </tr>
                                <tr style="background-color:#f0f0f0;">
                                <th style="border:1px solid #333; padding:8px; width:11.5%;">내수</th><th style="border:1px solid #333; padding:8px; width:11.5%;">수출</th>
                                <th style="border:1px solid #333; padding:8px; width:11.5%;">내수</th><th style="border:1px solid #333; padding:8px; width:11.5%;">수출</th>
                                </tr>
                                <tr>
                                <td style="border:1px solid #333; padding:8px; line-height:1.4;">(품목 1)</td>
                                <td style="border:1px solid #333; padding:8px;">(수치)</td>
                                <td style="border:1px solid #333; padding:8px;">(주요타겟처)</td>
                                <td style="border:1px solid #333; padding:8px;">(자동)</td><td style="border:1px solid #333; padding:8px;">(자동)</td>
                                <td style="border:1px solid #333; padding:8px;">(자동)</td><td style="border:1px solid #333; padding:8px;">(자동)</td>
                                </tr>
                                <tr>
                                <td style="border:1px solid #333; padding:8px; line-height:1.4;">(품목 2)</td>
                                <td style="border:1px solid #333; padding:8px;">(수치)</td>
                                <td style="border:1px solid #333; padding:8px;">(주요타겟처)</td>
                                <td style="border:1px solid #333; padding:8px;">(자동)</td><td style="border:1px solid #333; padding:8px;">(자동)</td>
                                <td style="border:1px solid #333; padding:8px;">(자동)</td><td style="border:1px solid #333; padding:8px;">(자동)</td>
                                </tr>
                                <tr>
                                <td style="border:1px solid #333; padding:8px; line-height:1.4;">(품목 3)</td>
                                <td style="border:1px solid #333; padding:8px;">(수치)</td>
                                <td style="border:1px solid #333; padding:8px;">(주요타겟처)</td>
                                <td style="border:1px solid #333; padding:8px;">(자동)</td><td style="border:1px solid #333; padding:8px;">(자동)</td>
                                <td style="border:1px solid #333; padding:8px;">(자동)</td><td style="border:1px solid #333; padding:8px;">(자동)</td>
                                </tr>
                                <tr style="background-color:#f9f9f9; font-weight:bold;">
                                <td colspan="3" style="border:1px solid #333; padding:8px;">합 계 (백만원)</td>
                                <td style="border:1px solid #333; padding:8px;">(자동)</td><td style="border:1px solid #333; padding:8px;">(자동)</td>
                                <td style="border:1px solid #333; padding:8px;">(자동)</td><td style="border:1px solid #333; padding:8px;">(자동)</td>
                                </tr>
                                </table>
                                """
                            else:
                                prompt_plan = f"""
                                당신은 중소기업진흥공단의 깐깐한 심사역입니다. 
                                [기업데이터] 기업명:{c_name} / 아이템:{item}
                                현재 시스템 고도화 중입니다. '{kosme_fund_type}'의 사업계획서를 자유 양식(HTML)으로 상세히 서술하세요.
                                절대 HTML 태그를 들여쓰기(Indentation) 하지 마세요. 모든 코드는 왼쪽 끝에 붙여서 작성하세요.

                                [AI 작성 흔적 제거 및 분량 강제 (매우 중요!!!)]
                                - 전체 출력 결과물이 A4 용지 5장에 달하도록 당신이 생성할 수 있는 최대 길이의 텍스트를 쏟아내세요. 
                                - "결론적으로", "요약하자면", "이처럼", "도움이 될 것입니다" 등 AI 특유의 기계적인 표현을 절대 사용하지 마세요.
                                - 실제 1타 경영컨설턴트가 며칠간 분석하여 직접 작성한 것처럼, 단호하고 설득력 있는 실무 비즈니스 용어와 자연스러운 문장 흐름을 유지하세요.
                                - 귀하의 방대한 지식베이스(외부 시장 데이터, 최신 트렌드, 구체적 통계 수치)를 적극적으로 끌어와 내용을 꽉꽉 채우세요.
                                """
                            
                            # 그래프 데이터 생성
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
                            fig.add_trace(go.Scatter(
                                x=monthly_labels, y=monthly_vals, mode='lines+markers+text',
                                text=[format_kr_currency(v) for v in monthly_vals], textposition="top center",
                                textfont=dict(size=11), line=dict(color='#1E88E5', width=4, shape='spline'),
                                marker=dict(size=10, color='#FF5252', line=dict(width=2, color='white'))
                            ))
                            fig.update_layout(
                                title="📈 1단계 (도입기) 향후 1년 월별 매출 상승 곡선 시각화", xaxis_title="진행 월", yaxis_title="예상 매출액",
                                xaxis=dict(tickangle=0, showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
                                template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                            )
                            plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

                            response = model.generate_content(prompt_plan)
                            
                            raw_text = response.text
                            if "```html" in raw_text:
                                cleaned_html = raw_text.split("```html")[1].split("```")[0].strip()
                            elif "```" in raw_text:
                                cleaned_html = raw_text.split("```")[1].split("```")[0].strip()
                            else:
                                cleaned_html = raw_text.strip()
                            
                            # 들여쓰기(Indentation) 제거 로직 적용
                            cleaned_html = "\n".join([line.lstrip() for line in cleaned_html.split("\n")])
                            
                            # 그래프 삽입
                            if "[GRAPH_INSERT_POINT]" in cleaned_html:
                                parts = cleaned_html.partition("[GRAPH_INSERT_POINT]")
                                cleaned_html = parts[0] + plotly_html + parts[2]
                                
                            st.session_state["kosme_result_type"] = "plan"
                            st.session_state["kosme_result_html"] = cleaned_html
                            status.update(label="✅ 사업계획서(별첨) 생성 완료!", state="complete")
                        except Exception as e:
                            status.update(label=f"❌ 오류 발생: {str(e)}", state="error")
                            
            # 결과 화면 출력 (하단 풀사이즈)
            if "kosme_result_html" in st.session_state:
                st.divider()
                doc_title = "사업계획서(별첨)" if st.session_state["kosme_result_type"] == "plan" else "융자신청서(공통)"
                st.subheader(f"📄 생성된 문서 확인: {doc_title}")
                
                # HTML 렌더링
                st.markdown(st.session_state["kosme_result_html"], unsafe_allow_html=True)
                
                # 다운로드 버튼
                safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
                if not safe_file_name: safe_file_name = "업체"
                
                html_export = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>{c_name} {doc_title}</title>
                    <style>
                        * {{ box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                        body {{ font-family: 'Malgun Gothic', sans-serif; padding: 40px; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; background-color: #fff; }}
                        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; }}
                        td, th {{ border: 1px solid #333; padding: 10px; }}
                        th {{ background-color: #f0f0f0; }}
                        @media print {{ 
                            @page {{ size: A4; margin: 15mm; }}
                        }}
                    </style>
                </head>
                <body>
                    {st.session_state["kosme_result_html"]}
                </body>
                </html>
                """
                st.download_button(
                    label=f"📥 {doc_title} HTML 파일로 다운로드", 
                    data=html_export, 
                    file_name=f"{safe_file_name}_{doc_title}.html", 
                    mime="text/html", 
                    type="primary"
                )

        # ==========================================
        # [2. 소진공 탭]
        # ==========================================
        with tabs[1]:
            st.subheader("🏪 소상공인시장진흥공단 (소진공)")
            
            semas_categories = {
                "혁신성장촉진자금": ["수출", "2년 연속 매출 10%이상 신장", "스마트 공장 도입", "강한 소상공인·로컬크리에이터", "소상공인졸업후보기업", "직접대출 성실상환", "스마트기술", "백년가게", "사회연대경제조직", "신사업창업사관학교 수료생"],
                "민간투자연계형매칭융자": ["민간투자연계형매칭융자"],
                "상생성장지원자금": ["일반형", "성장형", "도약형"],
                "일시적경영애로자금": ["일시적경영애로자금"],
                "신용취약소상공인자금": ["신용취약소상공인자금"],
                "재도전특별자금": ["일반: 재창업 준비단계", "일반: 재창업 초기단계", "일반: 채무조정", "희망형", "도약형"]
            }
            
            col_s_dd1, col_s_dd2 = st.columns(2)
            with col_s_dd1:
                main_semas_type = st.selectbox("💡 1. 대분류 자금종류 (소진공)", list(semas_categories.keys()))
            with col_s_dd2:
                semas_fund_type = st.selectbox("💡 2. 세부 자금종류 (소진공)", semas_categories[main_semas_type])
                
            col_sp1, col_sp2 = st.columns(2)
            
            # --- 좌측: 소진공 융자신청서 ---
            with col_sp1:
                st.markdown("#### 📄 소진공 융자신청서(공통)")
                st.caption("💡 포커스: 자금소요 내역, 상권 분석, 27/28년 예상매출")
                
                if st.button("🚀 소진공 융자신청서(공통) 바로보기", use_container_width=True):
                    with st.status("🚀 소진공 융자신청서 빈칸을 채우는 중입니다...", expanded=True) as status:
                        try:
                            model_name = get_best_model_name()
                            model = genai.GenerativeModel(model_name)
                            
                            prompt_loan_semas = f"""
                            당신은 소상공인시장진흥공단의 깐깐한 심사역입니다. 
                            아래 [기업 데이터]를 바탕으로 소진공 융자신청서(공통양식) 초안을 HTML 표로 출력하세요. 마크다운 절대 금지.
                            절대 HTML 태그를 들여쓰기(Indentation) 하지 마세요. 모든 코드는 왼쪽 끝에 붙여서 작성하세요.

                            [기업 데이터]
                            - 기업명: {c_name} / 대표자: {rep_name} / 업종: {c_ind}
                            - 매출: 24년({sales_24}), 금년({s_cur})
                            - 신청자금: {req_fund} ({fund_type} / {semas_fund_type})
                            - 아이템: {item} / 시장: {market}

                            [AI 작성 흔적 제거 및 전문가 톤 강제]
                            - "결론적으로", "요약하자면", "이처럼", "도움이 될 것입니다" 등 AI 특유의 기계적인 표현을 절대 사용하지 마세요.
                            - 실제 1타 경영컨설턴트가 며칠간 분석하여 직접 작성한 것처럼, 단호하고 설득력 있는 실무 비즈니스 용어와 자연스러운 문장 흐름을 유지하세요.
                            - 출력 길이 제한을 무시하고, 각 서술 항목마다 당신이 생성할 수 있는 최대 길이의 텍스트(각 칸별로 800자 이상)를 쏟아내세요.
                            
                            [출력 양식 - 무조건 이 HTML 표 양식을 사용할 것]
                            <h2 style="text-align:center;">소상공인 정책자금 융자신청서</h2>
                            
                            <h3>[신청내용]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:left; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">자금명</th><td style="border:1px solid #333; padding:8px;">▣ {main_semas_type} - {semas_fund_type}</td><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">신청금액</th><td style="border:1px solid #333; padding:8px;">{req_fund}</td></tr>
                            </table>

                            <h3>[기업현황]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:center; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">기업명</th><td style="border:1px solid #333; padding:8px;">{c_name}</td><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">대표자</th><td style="border:1px solid #333; padding:8px;">{rep_name}</td></tr>
                            <tr><th style="border:1px solid #333; padding:8px; background:#f0f0f0;">주소</th><td colspan="3" style="border:1px solid #333; padding:8px; text-align:left;">{address}</td></tr>
                            </table>

                            <h3>[매출 및 자금 소요계획]</h3>
                            <table style="width:100%; border-collapse: collapse; border: 1px solid #333; text-align:left; font-size:13px; margin-bottom:20px;">
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0; width:20%;">전년도 매출</th><td style="border:1px solid #333; padding:15px;">{sales_24}</td></tr>
                            <tr><th style="border:1px solid #333; padding:15px; background:#f0f0f0;">자금 활용계획</th><td style="border:1px solid #333; padding:15px; line-height:1.6;">(소상공인의 사업 생존과 자생력 강화, 지역 상권 내 영업 전략을 중심으로 자금 활용 목적을 최소 4~5개의 거대한 문단으로 매우 상세하게 작성)</td></tr>
                            </table>
                            [GRAPH_INSERT_POINT]
                            """
                            # 그래프 데이터 생성
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
                            fig.add_trace(go.Scatter(
                                x=monthly_labels, y=monthly_vals, mode='lines+markers+text',
                                text=[format_kr_currency(v) for v in monthly_vals], textposition="top center",
                                textfont=dict(size=11), line=dict(color='#1E88E5', width=4, shape='spline'),
                                marker=dict(size=10, color='#FF5252', line=dict(width=2, color='white'))
                            ))
                            fig.update_layout(
                                title="📈 향후 1년 월별 매출 상승 곡선 시각화", xaxis_title="진행 월", yaxis_title="예상 매출액",
                                xaxis=dict(tickangle=0, showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
                                template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                            )
                            plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

                            response = model.generate_content(prompt_loan_semas)
                            
                            raw_text = response.text
                            if "```html" in raw_text:
                                cleaned_html = raw_text.split("```html")[1].split("```")[0].strip()
                            elif "```" in raw_text:
                                cleaned_html = raw_text.split("```")[1].split("```")[0].strip()
                            else:
                                cleaned_html = raw_text.strip()
                            
                            cleaned_html = "\n".join([line.lstrip() for line in cleaned_html.split("\n")])
                            # 그래프 삽입
                            if "[GRAPH_INSERT_POINT]" in cleaned_html:
                                parts = cleaned_html.partition("[GRAPH_INSERT_POINT]")
                                cleaned_html = parts[0] + plotly_html + parts[2]
                                
                            st.session_state["semas_result_type"] = "loan"
                            st.session_state["semas_result_html"] = cleaned_html
                            status.update(label="✅ 소진공 융자신청서 생성 완료!", state="complete")
                        except Exception as e:
                            status.update(label=f"❌ 오류 발생: {str(e)}", state="error")
            
            # --- 우측: 소진공 사업계획서 ---
            with col_sp2:
                st.markdown(f"#### 📝 소진공 사업계획서 ({semas_fund_type})")
                st.caption("💡 포커스: 생존 가능성(자생력), 현실적인 지역 상권 매출 전략")
                
                if st.button(f"🚀 소진공 {semas_fund_type} 바로보기", use_container_width=True):
                    with st.status(f"🚀 '{semas_fund_type}' 전용 1타 심사역 로직으로 작성 중입니다...", expanded=True) as status:
                        try:
                            model_name = get_best_model_name()
                            model = genai.GenerativeModel(model_name)
                            
                            prompt_plan_semas = f"""
                            당신은 소상공인시장진흥공단의 깐깐한 심사역입니다. 
                            [기업데이터] 기업명:{c_name} / 아이템:{item}
                            현재 '{main_semas_type} - {semas_fund_type}' 전용 공식 양식 업데이트 전입니다. 해당 자금의 성격(예: 수출, 스마트기술, 일시적 애로 등)에 맞춰 소상공인의 생존 전략과 자생력 강화, 상권 분석에 초점을 맞춘 자유 양식 사업계획서(HTML)를 작성해 주세요. 
                            절대 HTML 태그를 들여쓰기(Indentation) 하지 마세요. 모든 코드는 왼쪽 끝에 붙여서 작성하세요.

                            [AI 작성 흔적 제거 및 분량 강제 (매우 중요!!!)]
                            - 전체 출력 결과물이 A4 용지 5장에 달하도록 당신이 생성할 수 있는 최대 길이의 텍스트를 쏟아내세요. 
                            - "결론적으로", "요약하자면", "이처럼", "도움이 될 것입니다" 등 AI 특유의 기계적인 표현을 절대 사용하지 마세요.
                            - 실제 1타 경영컨설턴트가 며칠간 분석하여 직접 작성한 것처럼, 단호하고 설득력 있는 실무 비즈니스 용어와 자연스러운 문장 흐름을 유지하세요.
                            - 외부 지식베이스(상권 데이터, 트렌드 등)를 적극 끌어와 서술형 칸을 전문적으로 아주 방대하게 채우세요.
                            """
                            # 그래프 데이터 생성
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
                            fig.add_trace(go.Scatter(
                                x=monthly_labels, y=monthly_vals, mode='lines+markers+text',
                                text=[format_kr_currency(v) for v in monthly_vals], textposition="top center",
                                textfont=dict(size=11), line=dict(color='#1E88E5', width=4, shape='spline'),
                                marker=dict(size=10, color='#FF5252', line=dict(width=2, color='white'))
                            ))
                            fig.update_layout(
                                title="📈 1단계 (도입기) 향후 1년 월별 매출 상승 곡선 시각화", xaxis_title="진행 월", yaxis_title="예상 매출액",
                                xaxis=dict(tickangle=0, showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
                                template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                            )
                            plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

                            response = model.generate_content(prompt_plan_semas)
                            
                            raw_text = response.text
                            if "```html" in raw_text:
                                cleaned_html = raw_text.split("```html")[1].split("```")[0].strip()
                            elif "```" in raw_text:
                                cleaned_html = raw_text.split("```")[1].split("```")[0].strip()
                            else:
                                cleaned_html = raw_text.strip()
                            
                            cleaned_html = "\n".join([line.lstrip() for line in cleaned_html.split("\n")])
                            # 그래프 삽입 (만약 AI가 그래프 포인트를 넣지 않았다면 수동으로 하단에 추가)
                            cleaned_html += f"<br><br>{plotly_html}"
                                
                            st.session_state["semas_result_type"] = "plan"
                            st.session_state["semas_result_html"] = cleaned_html
                            status.update(label="✅ 사업계획서(별첨) 생성 완료!", state="complete")
                        except Exception as e:
                            status.update(label=f"❌ 오류 발생: {str(e)}", state="error")
                            
            # 결과 화면 출력 (소진공 하단)
            if "semas_result_html" in st.session_state:
                st.divider()
                doc_title = "소진공 사업계획서(별첨)" if st.session_state["semas_result_type"] == "plan" else "소진공 융자신청서(공통)"
                st.subheader(f"📄 생성된 문서 확인: {doc_title}")
                st.markdown(st.session_state["semas_result_html"], unsafe_allow_html=True)
                
                safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
                if not safe_file_name: safe_file_name = "업체"
                html_export = f"""
                <!DOCTYPE html>
                <html><head><meta charset="utf-8"><title>{c_name} {doc_title}</title>
                <style>body {{ font-family: 'Malgun Gothic', sans-serif; padding: 40px; line-height: 1.6; max-width: 900px; margin: 0 auto; }} table {{ width: 100%; border-collapse: collapse; }} td, th {{ border: 1px solid #333; padding: 15px; }} th {{ background-color: #f0f0f0; }}</style></head>
                <body>{st.session_state["semas_result_html"]}</body></html>
                """
                st.download_button(label=f"📥 {doc_title} HTML 파일로 다운로드", data=html_export, file_name=f"{safe_file_name}_{doc_title}.html", mime="text/html", type="primary")

        with tabs[2]:
            st.subheader("🏦 신용보증기금/재단 (준비 중)")

        with tabs[3]:
            st.subheader("🔬 기술보증기금 (준비 중)")

        with tabs[4]:
            st.subheader("📈 제안용 (IR / PSST) (준비 중)")
            
    # ---------------------------------------------------------
    # [모드 D: 4. 정식 사업계획서 (마스터)] - 뼈대 추가
    # ---------------------------------------------------------
    elif st.session_state["view_mode"] == "FULL_PLAN":
        if st.button("⬅️ 대시보드로 돌아가기"):
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
            
        st.title("📑 마스터 사업계획서 자동 생성 (IR / FSS 등)")
        st.info("투자 유치 및 대형 자금 조달을 위한 '풀버전(Full-Version) 정식 사업계획서' 생성 메뉴입니다. (곧 업데이트 예정)")

    # --- [입력 화면 (대시보드)] ---
    else:
        st.title("📊 AI 컨설팅 대시보드")
        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
        with col_t1:
            if st.button("📊 1. 기업분석리포트 생성", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "REPORT"
                st.session_state.pop("generated_report", None)
                st.rerun()
        with col_t2: 
            if st.button("💡 2. 정책자금 매칭 리포트", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "MATCHING"
                st.session_state.pop("generated_matching", None)
                st.rerun()
        with col_t3: 
            if st.button("📝 3. 기관 맞춤형 융자/사업계획서 AI자동 생성기", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "PLAN"
                st.session_state.pop("kosme_result_html", None)
                st.session_state.pop("semas_result_html", None)
                st.rerun()
        with col_t4: 
            if st.button("📑 4. 정식 사업계획서 (마스터) 생성", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "FULL_PLAN"
                st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

        st.header("1. 기업현황")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("기업명", key="in_company_name")
            st.text_input("사업자번호", key="in_raw_biz_no")
            biz_type = st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
            if biz_type == "법인": st.text_input("법인등록번호", key="in_raw_corp_no")
        with c2:
            st.text_input("사업개시일", placeholder="2020.01.01", key="in_start_date")
            st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
            st.number_input("상시근로자수(명)", value=0, step=1, key="in_employee_count")
            lease_status = st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
            if lease_status == "임대":
                lc1, lc2 = st.columns(2)
                with lc1: st.number_input("보증금(만원)", value=0, step=1, key="in_lease_deposit")
                with lc2: st.number_input("월임대료(만원)", value=0, step=1, key="in_lease_rent")
        with c3:
            st.text_input("전화번호", key="in_biz_tel")
            has_add_biz = st.radio("추가사업장현황", ["무", "유"], horizontal=True, key="in_has_additional_biz")
            if has_add_biz == "유": st.text_input("추가 사업장 정보 (예: 공장 주소 등)", key="in_additional_biz_addr")
            st.text_input("사업장 주소", key="in_biz_addr")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("2. 대표자 정보")
        r1, r2, r3 = st.columns(3)
        with r1:
            rc1, rc2 = st.columns(2)
            with rc1: st.text_input("대표자명", key="in_rep_name")
            with rc2: st.text_input("생년월일", key="in_rep_dob")
            st.text_input("연락처", key="in_rep_phone")
            st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")
            st.text_input("이메일 주소", key="in_rep_email")
        with r2:
            st.text_input("거주지 주소", key="in_home_addr")
            st.radio("거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status")
            st.text_input("부동산 현황", key="in_real_estate")
        with r3:
            st.text_input("최종학교", key="in_edu_school")
            st.text_input("학과", key="in_edu_major")
            st.text_area("경력(최근기준)", key="in_career")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("3. 신용 및 연체 정보")
        cr1, cr2 = st.columns(2)
        with cr1:
            cc1, cc2 = st.columns(2)
            with cc1: st.radio("세금체납", ["무", "유"], horizontal=True, key="in_tax_status")
            with cc2: st.radio("금융연체", ["무", "유"], horizontal=True, key="in_fin_status")
            sc1, sc2 = st.columns(2)
            with sc1: kcb = st.number_input("KCB 점수", value=0, step=1, key="in_kcb_score")
            with sc2: nice = st.number_input("NICE 점수", value=0, step=1, key="in_nice_score")
        with cr2:
            st.info(f"#### 🏆 등급 판정 결과\n\n* **KCB (올크레딧):** {get_credit_grade(kcb, 'KCB')}등급\n* **NICE (나이스):** {get_credit_grade(nice, 'NICE')}등급")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("4. 재무현황")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.number_input("금년 매출(만원)", value=0, step=1, key="in_sales_current")
        with m2: st.number_input("25년도 매출합계(만원)", value=0, step=1, key="in_sales_2025")
        with m3: st.number_input("24년도 매출합계(만원)", value=0, step=1, key="in_sales_2024")
        with m4: st.number_input("23년도 매출합계(만원)", value=0, step=1, key="in_sales_2023")

        c_ind = st.session_state.get("in_industry", "기타")
        if c_ind in ["제조업", "도소매업"]:
            st.markdown("**(수출 정보)**")
            has_export = st.radio("수출 유무", ["무", "유"], horizontal=True, key="in_is_export")
            if has_export == "유":
                e1, e2, e3 = st.columns(3)
                with e1: st.number_input("24년도 수출액(만원)", value=0, step=1, key="in_exp_2024")
                with e2: st.number_input("25년도 수출액(만원)", value=0, step=1, key="in_exp_2025")
                with e3: st.number_input("26년도(금년) 수출액(만원)", value=0, step=1, key="in_exp_current")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("5. 기대출현황")
        d1, d2, d3, d4 = st.columns(4)
        with d1: st.number_input("중진공(만원)", value=0, step=1, key="in_debt_kosme")
        with d2: st.number_input("소진공(만원)", value=0, step=1, key="in_debt_semas")
        with d3: st.number_input("신용보증재단(만원)", value=0, step=1, key="in_debt_koreg")
        with d4: st.number_input("신용보증기금(만원)", value=0, step=1, key="in_debt_kodit")
        d5, d6, d7, d8 = st.columns(4)
        with d5: st.number_input("기술보증기금(만원)", value=0, step=1, key="in_debt_kibo")
        with d6: st.number_input("기타(만원)", value=0, step=1, key="in_debt_etc")
        with d7: st.number_input("신용대출(만원)", value=0, step=1, key="in_debt_credit")
        with d8: st.number_input("담보대출(만원)", value=0, step=1, key="in_debt_coll")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("6. 필요자금")
        p1, p2, p3 = st.columns([1, 1, 2])
        with p1: st.selectbox("자금구분", ["운전자금", "시설자금"], key="in_fund_type")
        with p2: st.number_input("필요자금액(만원)", value=0, step=1, key="in_req_amount")
        with p3: st.text_input("자금사용용도", key="in_fund_purpose")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("7. 인증현황")
        ac1, ac2, ac3, ac4 = st.columns(4)
        with ac1: st.checkbox("소상공인확인서", key="in_chk_1"); st.checkbox("창업확인서", key="in_chk_2")
        with ac2: st.checkbox("여성기업확인서", key="in_chk_3"); st.checkbox("이노비즈", key="in_chk_4")
        with ac3: st.checkbox("벤처인증", key="in_chk_6"); st.checkbox("뿌리기업확인서", key="in_chk_7")
        with ac4: st.checkbox("ISO인증", key="in_chk_10"); st.checkbox("HACCP인증", key="in_chk_11")

        # [신설] 8. 특허정보
        st.markdown("<br>", unsafe_allow_html=True)
        st.header("8. 특허정보")
        pat_col1, pat_col2 = st.columns(2)
        with pat_col1:
            has_patent = st.radio("특허/지식재산권 보유여부", ["무", "유"], horizontal=True, key="in_has_patent")
            if has_patent == "유":
                st.text_input("특허출원 (건)", key="in_pat_apply")
                st.text_input("특허등록 (건)", key="in_pat_reg")
                st.text_input("상표등록 (건)", key="in_tm_reg")
                st.text_input("디자인등록 (건)", key="in_design_reg")
        with pat_col2:
            buy_patent = st.radio("특허매입예정", ["무", "유"], horizontal=True, key="in_buy_patent")
            if buy_patent == "유":
                st.text_input("희망특허 (분야/명칭)", key="in_buy_pat_desc")
                st.number_input("예상금액(만원)", value=0, step=1, key="in_buy_pat_amount")

        # [번호 밀림] 9. 비즈니스 정보 (+공정도 신설)
        st.markdown("<br>", unsafe_allow_html=True)
        st.header("9. 비즈니스 정보")
        st.text_area("[아이템]", key="in_item_desc")
        st.text_input("[제품생산공정도 (간략 기재)]", placeholder="예: 원물 입고 -> 세척 -> 조리 -> 포장 -> 출하", key="in_process_desc")
        st.markdown("**[주거래처 정보]**")
        cli1, cli2, cli3 = st.columns(3)
        with cli1: st.text_input("거래처 1", key="in_client_1")
        with cli2: st.text_input("거래처 2", key="in_client_2")
        with cli3: st.text_input("거래처 3", key="in_client_3")
        st.text_area("[판매루트]", key="in_sales_route")
        st.text_area("[시장현황]", key="in_market_status")
        st.text_area("[차별화]", key="in_diff_point")
        st.text_area("[앞으로의 계획]", key="in_future_plan")

        st.markdown("<br>", unsafe_allow_html=True)
        st.success("✅ 세팅 완료! 좌측에 API 키 저장하시고 상단 버튼을 클릭해 주십시오.")
