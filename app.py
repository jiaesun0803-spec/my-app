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

# [수정] 사업자번호 및 법인등록번호 자동 포맷팅 함수 추가
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
        st.sidebar.info("개발 중인 기능입니다.")

    # ==========================================
    # 2. 화면 모드 제어 (리포트 vs 대시보드)
    # ==========================================
    if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
    if "permanent_data" not in st.session_state: st.session_state["permanent_data"] = {}

    # ---------------------------------------------------------
    # [모드 A: 기존 1. 기업분석리포트 - 내용 알차게 & 그래프 유동성 & 페이지 분할]
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
                with st.status("🚀 잼(Jam)이 외부 지식을 동원하여 심도 있는 분석 리포트를 생성 중입니다...", expanded=True) as status:
                    try:
                        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    except Exception as e:
                        raise Exception(f"API 키 권한 오류입니다. 새 API 키를 적용해주세요. (상세: {e})")

                    if 'models/gemini-1.5-flash' in available_models: target_model = 'gemini-1.5-flash'
                    elif 'models/gemini-1.5-pro' in available_models: target_model = 'gemini-1.5-pro'
                    elif 'models/gemini-pro' in available_models: target_model = 'gemini-pro'
                    elif len(available_models) > 0: target_model = available_models[0].replace('models/', '')
                    else: raise Exception("사용 가능한 생성형 모델이 없습니다.")

                    model = genai.GenerativeModel(target_model)
                    
                    c_ind = d.get('in_industry', '미입력')
                    rep_name = d.get('in_rep_name', '미입력')
                    
                    # [수정] 사업자 및 법인등록번호 포맷팅
                    biz_no = format_biz_no(d.get('in_raw_biz_no', '미입력'))
                    corp_no = format_corp_no(d.get('in_raw_corp_no', ''))
                    corp_text = f" (법인: {corp_no})" if corp_no else ""
                    
                    address = d.get('in_biz_addr', '미입력')
                    add_biz_status = d.get('in_has_additional_biz', '무')
                    add_biz_addr = d.get('in_additional_biz_addr', '').strip()
                    if add_biz_status == '유' and add_biz_addr:
                        address += f" <br>(추가사업장: {add_biz_addr})"
                    
                    s_cur = format_kr_currency(d.get('in_sales_current', 0))
                    s_25 = format_kr_currency(d.get('in_sales_2025', 0))
                    s_24 = format_kr_currency(d.get('in_sales_2024', 0))
                    s_23 = format_kr_currency(d.get('in_sales_2023', 0))
                    
                    fund_type = d.get('in_fund_type', '운전자금')
                    req_fund = format_kr_currency(d.get('in_req_amount', 0))
                    
                    item = d.get('in_item_desc', '미입력')
                    market = d.get('in_market_status', '미입력')
                    diff = d.get('in_diff_point', '미입력')
                    
                    # [수정] 그래프 유동성 부여 (사인 파동을 활용한 리얼한 곡선)
                    val_cur = safe_int(d.get('in_sales_current', 0))
                    if val_cur <= 0: val_cur = 1000
                    start_val = val_cur / 12
                    end_val = start_val * 1.5
                    
                    monthly_vals = []
                    for i in range(12):
                        progress = i / 11.0
                        linear_part = start_val + (end_val - start_val) * progress
                        # 오르락내리락 하는 변동성(Fluctuation) 추가 (최대 증감폭의 15%)
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

                    # [수정] 프롬프트 퀄리티 강화, 경쟁사 표 추가, 특허/인증 조언 추가, 카테고리 클래스(section-title) 할당
                    prompt = f"""
                    당신은 20년 경력의 중소기업 경영컨설턴트입니다. 
                    아래 양식과 서식 규칙을 **반드시 100% 똑같이** 지켜서 출력하세요.

                    [작성 규칙 - 절대 엄수!!!]
                    1. 마크다운 사용 금지: 제목이나 강조에 마크다운 기호(##, **, - 등)를 절대 사용하지 마세요. 반드시 제공된 <h2 class="section-title">, <b>, <div> 등의 HTML 태그만 사용해야 합니다.
                    2. 어투: 모든 문장 끝은 '~있음', '~가능', '~함', '~필요함' 등 명사형(음/슴체)으로 마무리하세요.
                    3. 내용 풍성하게: 외부 지식(최신 시장 트렌드, 인증 절차, 정책 방향 등)을 총동원하여 각 항목을 4~5문장 이상으로 매우 상세하고 알차게 꽉 채워 작성하세요. 절대 내용이 빈약하면 안 됩니다.

                    [기업 정보]
                    - 기업명: {c_name} / 대표자: {rep_name} / 업종: {c_ind}
                    - 아이템: {item} / 시장현황: {market} / 차별화: {diff}
                    - 신청자금: {req_fund} ({fund_type})

                    [출력 양식]
                    <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업현황분석</h2>
                    <table style="width:100%; border-collapse: collapse; font-size: 1.1em; background-color:#f8f9fa; border-radius:15px; overflow:hidden; margin-bottom:15px;">
                      <tr>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0; width:15%;"><b>기업명</b></td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0; width:35%;">{c_name}</td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0; width:15%;"><b>대표자명</b></td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0; width:35%;">{rep_name}</td>
                      </tr>
                      <tr>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0;"><b>업종</b></td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0;">{c_ind}</td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0;"><b>사업/법인번호</b></td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0;">{biz_no}{corp_text}</td>
                      </tr>
                      <tr>
                        <td style="padding:15px;"><b>사업장 주소</b></td>
                        <td colspan="3" style="padding:15px;">{address}</td>
                      </tr>
                    </table>
                    <div style="margin-bottom:15px;">(해당 업종과 아이템의 잠재력, 향후 긍정적인 기대감을 외부 지식을 활용하여 4~5문장 이상 상세하고 깊이 있게 작성. 숫자는 기재하지 말 것. 마침표 뒤 줄바꿈 &lt;br&gt;)</div>

                    <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. SWOT 분석</h2>
                    <table style="width:100%; text-align:center; border-collapse: separate; border-spacing: 10px;">
                      <tr>
                        <td style="background-color:#e3f2fd; padding:20px; border-radius:15px; width:50%;"><b>S (강점)</b><br><div style="text-align:left;">(3~4줄 이상의 상세 분석 내용)</div></td>
                        <td style="background-color:#ffebee; padding:20px; border-radius:15px; width:50%;"><b>W (약점)</b><br><div style="text-align:left;">(3~4줄 이상의 상세 분석 내용)</div></td>
                      </tr>
                      <tr>
                        <td style="background-color:#e8f5e9; padding:20px; border-radius:15px;"><b>O (기회)</b><br><div style="text-align:left;">(3~4줄 이상의 상세 분석 내용)</div></td>
                        <td style="background-color:#fff3e0; padding:20px; border-radius:15px;"><b>T (위협)</b><br><div style="text-align:left;">(3~4줄 이상의 상세 분석 내용)</div></td>
                      </tr>
                    </table>

                    <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 시장현황 및 경쟁력 비교</h2>
                    <div style="display:flex; gap:15px; margin-bottom:15px;">
                      <div style="flex:1; background-color:#f3e5f5; padding:20px; border-radius:15px;"><b>📊 시장 현황 분석</b><br><br>&bull; (해당 업종 시장 트렌드, 외부 데이터를 동원하여 4~5줄 상세 요약)</div>
                    </div>
                    <div style="margin-top:15px; padding:15px; background-color:#fff; border-radius:15px; border:1px solid #e0e0e0;">
                      <b>⚔️ 주요 경쟁사 비교 분석표</b><br>
                      <table style="width:100%; border-collapse: collapse; text-align:center; font-size:0.95em; margin-top:10px;">
                        <tr style="background-color:#eceff1;">
                          <th style="padding:12px; border:1px solid #ccc;">비교 항목</th>
                          <th style="padding:12px; border:1px solid #ccc;">{c_name} (자사)</th>
                          <th style="padding:12px; border:1px solid #ccc;">주요 경쟁사 A</th>
                          <th style="padding:12px; border:1px solid #ccc;">주요 경쟁사 B</th>
                        </tr>
                        <tr>
                          <td style="padding:12px; border:1px solid #ccc; font-weight:bold;">핵심 타겟/포지셔닝</td>
                          <td style="padding:12px; border:1px solid #ccc;">(자사 강점 요약)</td>
                          <td style="padding:12px; border:1px solid #ccc;">(경쟁사 A 특징)</td>
                          <td style="padding:12px; border:1px solid #ccc;">(경쟁사 B 특징)</td>
                        </tr>
                        <tr>
                          <td style="padding:12px; border:1px solid #ccc; font-weight:bold;">차별화 요소(경쟁우위)</td>
                          <td style="padding:12px; border:1px solid #ccc;">(자사만의 기술/서비스)</td>
                          <td style="padding:12px; border:1px solid #ccc;">(경쟁사 A 비교점)</td>
                          <td style="padding:12px; border:1px solid #ccc;">(경쟁사 B 비교점)</td>
                        </tr>
                      </table>
                    </div>

                    <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 핵심경쟁력분석</h2>
                    <div style="display:flex; gap:15px; margin-bottom:10px; text-align:center;">
                      <div style="flex:1; border:1px solid #e0e0e0; border-radius:15px; overflow:hidden;">
                        <div style="background-color:#e0f7fa; padding:15px; font-weight:bold; font-size:1.1em;">포인트 1 (키워드)</div>
                        <div style="padding:20px; font-size:0.95em; text-align:left;">&bull; (외부 지식 활용 3~4줄 구체적 분석)</div>
                      </div>
                      <div style="flex:1; border:1px solid #e0e0e0; border-radius:15px; overflow:hidden;">
                        <div style="background-color:#e0f7fa; padding:15px; font-weight:bold; font-size:1.1em;">포인트 2 (키워드)</div>
                        <div style="padding:20px; font-size:0.95em; text-align:left;">&bull; (외부 지식 활용 3~4줄 구체적 분석)</div>
                      </div>
                      <div style="flex:1; border:1px solid #e0e0e0; border-radius:15px; overflow:hidden;">
                        <div style="background-color:#e0f7fa; padding:15px; font-weight:bold; font-size:1.1em;">포인트 3 (키워드)</div>
                        <div style="padding:20px; font-size:0.95em; text-align:left;">&bull; (외부 지식 활용 3~4줄 구체적 분석)</div>
                      </div>
                    </div>

                    <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">5. 자금 사용계획 (총 신청자금: {req_fund})</h2>
                    <table style="width:100%; border-collapse: collapse; text-align:left;">
                     <tr style="background-color:#eceff1;">
                       <th style="padding:15px; border:1px solid #ccc; border-radius:10px 0 0 0;">구분 ({fund_type})</th>
                       <th style="padding:15px; border:1px solid #ccc;">상세 사용계획</th>
                       <th style="padding:15px; border:1px solid #ccc; border-radius:0 10px 0 0;">배정 금액</th>
                     </tr>
                     <tr>
                       <td style="padding:15px; border:1px solid #ccc; font-weight:bold;">(세부항목 1)</td>
                       <td style="padding:15px; border:1px solid #ccc;">&bull; (사용처 2~3줄 구체적 기재)</td>
                       <td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0;">(금액)</td>
                     </tr>
                     <tr>
                       <td style="padding:15px; border:1px solid #ccc; font-weight:bold;">(세부항목 2)</td>
                       <td style="padding:15px; border:1px solid #ccc;">&bull; (사용처 2~3줄 구체적 기재)</td>
                       <td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0;">(금액)</td>
                     </tr>
                    </table>

                    <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">6. 매출 1년 전망</h2>
                    <div style="display:flex; justify-content:space-between; align-items:stretch; text-align:center; flex-wrap:wrap; gap:10px;">
                      <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; flex:1;">
                        <div style="font-size:1.3em; font-weight:bold; color:#1565c0;">1단계 (도입)</div>
                        <div style="margin:15px 0; font-size:0.95em; text-align:left;">(성장 전략 2~3줄)</div>
                        <div style="color:#d32f2f; font-weight:bold;">목표: OOO만원</div>
                      </div>
                      <div style="font-size:2em; align-self:center;">➡️</div>
                      <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; flex:1;">
                        <div style="font-size:1.3em; font-weight:bold; color:#1565c0;">2단계 (성장)</div>
                        <div style="margin:15px 0; font-size:0.95em; text-align:left;">(성장 전략 2~3줄)</div>
                        <div style="color:#d32f2f; font-weight:bold;">목표: OOO만원</div>
                      </div>
                      <div style="font-size:2em; align-self:center;">➡️</div>
                      <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; flex:1;">
                        <div style="font-size:1.3em; font-weight:bold; color:#1565c0;">3단계 (확장)</div>
                        <div style="margin:15px 0; font-size:0.95em; text-align:left;">(성장 전략 2~3줄)</div>
                        <div style="color:#d32f2f; font-weight:bold;">목표: OOO만원</div>
                      </div>
                      <div style="font-size:2em; align-self:center;">➡️</div>
                      <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; flex:1;">
                        <div style="font-size:1.3em; font-weight:bold; color:#1565c0;">4단계 (안착)</div>
                        <div style="margin:15px 0; font-size:0.95em; text-align:left;">(성장 전략 2~3줄)</div>
                        <div style="color:#d32f2f; font-weight:bold;">최종목표: OOO만원</div>
                      </div>
                    </div>
                    
                    [GRAPH_INSERT_POINT]

                    <h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">7. AI 컨설턴트 핵심 코멘트 (인증 및 특허 전략 중심)</h2>
                    <div style="background-color:#eeeeee; border-left:5px solid #1565c0; padding:25px; border-radius:15px; margin-top:15px; line-height:1.8;">
                      <b>💡 벤처/이노비즈, ISO 등 필수 인증 및 특허 확보 조언:</b><br><br>
                      &bull; (기업 업종에 맞는 인증 제도 혜택 및 취득 방법 등 외부 지식을 동원하여 5~6줄 이상 매우 상세하고 전문적으로 조언. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)<br>
                      &bull; (아이템 보호를 위한 지식재산권(특허, 실용신안 등) 전략을 5~6줄 이상 구체적으로 조언. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)
                    </div>
                    """
                    
                    response = model.generate_content(prompt)
                    status.update(label="✅ 기업분석리포트 생성 완료!", state="complete")
                
                try:
                    response_text = response.text
                except:
                    response_text = ""

                if "[GRAPH_INSERT_POINT]" in response_text:
                    parts = response_text.partition("[GRAPH_INSERT_POINT]")
                    st.markdown(parts[0], unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown("<br><br>", unsafe_allow_html=True) 
                    st.markdown(parts[2], unsafe_allow_html=True)
                else:
                    st.markdown(response_text, unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)

                st.balloons()
                
                st.divider()
                st.subheader("💾 리포트 저장 (카테고리별 분할 인쇄)")
                safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
                if not safe_file_name: safe_file_name = "업체"
                
                # [수정] h2.section-title 에 page-break-before 옵션 적용 (첫 번째 제외)
                html_export = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>{c_name} 기업분석리포트</title>
                    <style>
                        * {{ box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                        body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; padding: 40px; line-height: 1.8; color: #333; max-width: 1000px; margin: 0 auto; font-size: 16px; background-color: #fff; }}
                        h1 {{ color: #111; text-align: center; margin-bottom: 40px; font-size: 32px; font-weight: bold; }}
                        h2 {{ color: #174EA6; border-bottom: 2px solid #174EA6; padding-bottom: 8px; margin-top: 50px; font-size: 26px; font-weight: bold; }}
                        .print-btn {{ display: block; width: 100%; padding: 15px; background-color: #174EA6; color: white; font-size: 18px; font-weight: bold; border: none; border-radius: 10px; cursor: pointer; margin-bottom: 30px; text-align: center; }}
                        .print-btn:hover {{ background-color: #123C85; }}
                        
                        @media print {{ 
                            .print-btn {{ display: none; }} 
                            @page {{ size: A4; margin: 15mm; }}
                            body {{ padding: 0 !important; font-size: 15px !important; color: black !important; max-width: 100% !important; }} 
                            h1 {{ margin: 0 0 30px 0 !important; font-size: 28px !important; }}
                            
                            /* 카테고리별 페이지 나누기 핵심 마법! */
                            h2.section-title {{ page-break-before: always; margin-top: 0 !important; }}
                            h2.section-title:first-of-type {{ page-break-before: avoid; margin-top: 20px !important; }}
                            
                            h2 {{ font-size: 24px !important; padding-bottom: 5px !important; border-bottom: 2px solid #174EA6 !important; }}
                            div {{ padding: 15px !important; margin-bottom: 20px !important; border-radius: 10px !important; page-break-inside: avoid; line-height: 1.6 !important; }}
                            table {{ font-size: 14px !important; margin-bottom: 15px !important; }}
                            th, td {{ padding: 10px !important; }}
                            br {{ display: block; content: ""; margin-top: 5px; }}
                        }}
                    </style>
                </head>
                <body>
                    <button class="print-btn" onclick="window.print()">🖨️ 클릭하여 PDF로 저장하기 (카테고리별 페이지 분할 적용)</button>
                    <h1>📋 AI 기업분석 결과보고서: {c_name}</h1>
                    <hr style="margin-bottom: 30px;">
                    {response_text.replace('[GRAPH_INSERT_POINT]', '<div style="padding:15px; margin: 20px 0; background:#e3f2fd; text-align:center; border-radius:10px; font-weight:bold; color:#1565c0; border: 1px dashed #1565c0;">[📈 1년 매출 상승 곡선 차트는 웹 대시보드 시스템에서 확인 가능합니다]</div>')}
                </body>
                </html>
                """
                st.download_button(label="📥 기업분석리포트 다운로드 (페이지 분할 PDF)", data=html_export, file_name=f"{safe_file_name}_기업분석리포트.html", mime="text/html", type="primary")

            except Exception as e:
                st.error(f"❌ 분석 중 오류 발생: {str(e)}")

    # ---------------------------------------------------------
    # [모드 B: 신규 2. 정책자금 매칭 리포트]
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
            st.error("⚠️ 좌측 사이드바에 API 키를 입력하거나, 서버 설정에 키를 등록해주세요.")
        else:
            try:
                with st.status("🚀 잼(Jam)이 기관별 컷오프, 한도, 유동화자금(P-CBO) 예외 룰을 철저히 심사 중입니다...", expanded=True) as status:
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
                    
                    tax_status = d.get('in_tax_status', '무')
                    fin_status = d.get('in_fin_status', '무')
                    
                    kibo_debt = safe_int(d.get('in_debt_kibo', 0))
                    kodit_debt = safe_int(d.get('in_debt_kodit', 0))
                    
                    total_debt_val = sum([
                        safe_int(d.get('in_debt_kosme', 0)),
                        safe_int(d.get('in_debt_semas', 0)),
                        safe_int(d.get('in_debt_koreg', 0)),
                        safe_int(d.get('in_debt_kodit', 0)),
                        safe_int(d.get('in_debt_kibo', 0)),
                        safe_int(d.get('in_debt_etc', 0)),
                        safe_int(d.get('in_debt_credit', 0)),
                        safe_int(d.get('in_debt_coll', 0))
                    ])
                    total_debt = format_kr_currency(total_debt_val)
                    
                    s_cur_val = safe_int(d.get('in_sales_current', 0))
                    s_cur = format_kr_currency(s_cur_val)
                    
                    c_ind = d.get('in_industry', '미입력')
                    biz_type = d.get('in_biz_type', '개인')
                    item = d.get('in_item_desc', '미입력')
                    nice_score = safe_int(d.get('in_nice_score', 0))
                    fund_type = d.get('in_fund_type', '운전자금')
                    
                    req_val = safe_int(d.get('in_req_amount', 0))
                    fund_req = format_kr_currency(req_val)
                    
                    has_cert = d.get('in_chk_6', False) or d.get('in_chk_4', False) or d.get('in_chk_10', False)
                    cert_status = "보유 (벤처/이노비즈 등)" if has_cert else "미보유"
                    
                    # 업력 계산 로직
                    start_date_str = d.get('in_start_date', '').strip()
                    biz_years = 0
                    if start_date_str:
                        try:
                            biz_start_year = int(start_date_str[:4])
                            biz_years = max(0, 2026 - biz_start_year)
                        except:
                            pass
                    
                    prompt = f"""
                    당신은 20년 경력의 중소기업 정책자금 전문 경영컨설턴트입니다. 
                    아래 [입력 데이터]와 [절대 매칭 비법 DB]를 100% 반영하여, 제공된 [출력 양식]의 HTML 태그만 사용하여 리포트를 출력하세요.

                    [작성 및 포맷팅 규칙 - 절대 엄수!!!]
                    1. 마크다운 사용 금지: 제목 기호(##), 볼드체(**), 리스트(-) 등 **마크다운 기호를 절대 사용하지 마세요.** 출력 양식에 제공된 `<h2>`, `<b>`, `&bull;`, `<br>` 등의 순수 HTML 태그만 사용해야 합니다. 
                    2. 어투: 모든 문장은 '~있음', '~가능', '~함', '~필요함' 등 명사형(음/슴체)으로 간결하게 작성하세요.
                    3. 줄바꿈: 문장이 마침표('.')로 끝날 때마다 무조건 HTML 태그 `<br>`을 삽입하여 시원하게 줄바꿈 하세요.
                    4. 내용 분량 (A4 1장 절대 사수): A4 1장에 완벽하게 들어갈 수 있도록 각 세부 항목(추천사유, 합격꿀팁 등)은 무조건 외부지식을 동원하되 **2~3줄 이내로 팩트만 압축해서** 작성하세요. 절대 4줄 이상 길게 쓰지 마세요.

                    [절대 매칭 비법 DB - 기관별 한도 및 순위 룰 (가장 중요!)]
                    ※ 순위 슬롯을 절대 마음대로 바꾸거나 빼지 마세요! (1순위:직접대출, 2순위:신보/기보, 3순위:지역신보, 4순위:유동화/특화)
                    1. 🥇 1순위 (직접대출): '중소벤처기업진흥공단(중진공)' 또는 '소상공인시장진흥공단(소진공)' 중 택 1 하세요.
                       - [소진공/중진공 중복 룰]: 두 기관의 자금은 **중복 이용이 가능**하다는 점을 꿀팁에 반드시 언급하세요.
                       - [중진공 컷오프 룰]: 비제조업(도소매업, 서비스업 등)은 연매출 50억 이상, 상시근로자 5인 이상이어야 신청 가능합니다. 비제조업인데 매출 50억 미만이면 무조건 소진공을 추천하세요.
                       - [소진공 룰]: 소진공은 최대 한도 7천만 원을 원칙으로 하되, 신용취약(NICE 839 이하)은 3,000만 원으로 제한합니다. 절대 1억 5천 등의 가짜 한도를 적지 마세요.
                    2. 🥈 2순위 (메이저 보증 - 절대 고정!): **2순위 자리는 무슨 일이 있어도 무조건 '신용보증기금(신보)' 또는 '기술보증기금(기보)'을 배정하세요.** - [1억 절대 룰 - 경고!]: 신보와 기보는 **무조건 1억 원 이상부터** 진행 가능합니다. 예상 한도 칸에 5천만원 등 1억 미만의 금액은 절대 적지 마세요. 무조건 최소 1억 원 이상으로 표기하세요!
                       - [한도 산출]: 제조업은 매출 1/2, 그 외는 매출 1/6~1/10 수준에서 총 기대출({total_debt})을 차감합니다. 만약 산출 금액이 적더라도, 리포트에는 신보/기보의 특징을 살려 **"최소 1억 원 (또는 한도 1억 이상 타겟팅)"**이라고 적고 2순위 자리를 무조건 사수하세요!
                       - [매출 4억 룰]: 매출액 4억(40,000만 원) 이상이면 신용보증기금(신보)을 강력하게 추천하세요.
                       - [기보 예외 룰]: 도소매/서비스업이라도 '벤처/이노비즈'나 '특허' 보유시 신보 대신 기보를 강력 추천하세요.
                       - [중복 금지]: 신보와 기보는 중복 불가.
                    3. 🥉 3순위 (지역재단 - 절대 고정!): **3순위 자리는 무조건 '지역신용보증재단'을 배정하세요.**
                       - [보증기관 순서 룰 - 핵심!!!]: 보증기관은 **반드시 '신보/기보(2순위) 먼저 ➡️ 지역신보(3순위) 나중' 순서로 진행**해야만 두 기관을 중복 이용할 수 있습니다. (지역신보를 먼저 쓰면 신보/기보 한도가 막혀버림). 꿀팁에 이 순서의 중요성을 강력하게 강조하세요. 한도는 최대 2억입니다.
                    4. 🏅 4순위 (유동화/기타): 
                       - 법인기업({biz_type})이고 성장성이 뚜렷하나 일반보증이 꽉 찼다면 P-CBO 추천 (신보 P-CBO: 업력 4년 이상 / 중진공 스케일업: 업력 5년+매출 20억 이상).
                       - 조건 미달시 다른 특화자금을 추천하세요.
                    5. 🚫 연체 컷오프: 세금체납({tax_status}), 금융연체({fin_status}) '유'인 경우 1~4순위 전부 비우고 연체 해소 조언만 작성.

                    [입력 데이터]
                    - 기업명: {c_name} / 사업자유형: {biz_type} / 업종: {c_ind} / 업력: 약 {biz_years}년
                    - 세금체납: {tax_status} / 금융연체: {fin_status} / NICE 점수: {nice_score}점
                    - 기술/벤처 인증: {cert_status} / 아이템: {item}
                    - 금년 매출: {s_cur} / 총 기대출 합계: {total_debt} / 희망자금: {fund_req}

                    [출력 양식 - HTML 태그 및 양식 100% 동일하게 유지. 마크다운(##, **) 절대 쓰지 말것]
                    <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업 스펙 진단 요약</h2>
                    <div style="background-color:#f8f9fa; padding:20px; border-radius:15px; border:1px solid #e0e0e0; margin-bottom:15px;">
                      <b>기업명:</b> {c_name} &nbsp;|&nbsp; <b>업종:</b> {c_ind} ({biz_type}) &nbsp;|&nbsp; <b>업력:</b> 약 {biz_years}년 <br>
                      <b>NICE 점수:</b> {nice_score}점 &nbsp;|&nbsp; <b>기술/벤처 인증:</b> {cert_status} <br>
                      <b>금년매출:</b> {s_cur} &nbsp;|&nbsp; <b>총 기대출:</b> <span style="color:red;">{total_debt}</span> &nbsp;|&nbsp; <b style="font-size:1.15em;">필요자금: {fund_req}</b>
                    </div>
                    <div style="margin-bottom:20px;">
                      (데이터를 바탕으로 정책자금 합격 가능성에 대한 팩트폭격 스펙 평가. 2~3줄 요약, 문장마다 마침표 뒤 줄바꿈 &lt;br&gt;)
                    </div>

                    <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. 우선순위 추천 정책자금 (1~2순위)</h2>
                    <div style="display:flex; gap:15px; margin-bottom:15px; align-items:stretch;">
                      <div style="flex:1; background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32;">
                        <b style="font-size:1.2em; color:#2e7d32;">🥇 1순위: [추천 기관명] / [세부 자금명] / 예상 한도</b><br><br>
                        &bull; (추천 사유 2~3줄 상세 작성. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)<br>
                        &bull; (합격 꿀팁 및 전략 2~3줄 상세 작성. 소진공/중진공 중복가능 언급. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)
                      </div>
                      <div style="flex:1; background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32;">
                        <b style="font-size:1.2em; color:#2e7d32;">🥈 2순위: [신용보증기금 또는 기술보증기금] / [보증 상품명] / 예상 한도 (최소 1억 원 이상)</b><br><br>
                        &bull; (추천 사유 2~3줄 상세 작성. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)<br>
                        &bull; (합격 꿀팁 및 심사절차 2~3줄 상세 작성. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)
                      </div>
                    </div>

                    <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 후순위 추천 (플랜 B - 3~4순위)</h2>
                    <div style="display:flex; gap:15px; margin-bottom:15px; align-items:stretch;">
                      <div style="flex:1; background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00;">
                        <b style="font-size:1.2em; color:#ef6c00;">🥉 3순위: [지역신용보증재단] / [세부 자금명] / 예상 한도 (최대 2억 원)</b><br><br>
                        &bull; (추천 사유 2~3줄 상세 작성. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)<br>
                        &bull; (기금 우선, 재단 나중 순서의 중요성 등 전략 2~3줄 상세 작성. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)
                      </div>
                      <div style="flex:1; background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00;">
                        <b style="font-size:1.2em; color:#ef6c00;">🏅 4순위: [추천 기관명] / [세부 자금명(또는 P-CBO)] / 예상 한도</b><br><br>
                        &bull; (추천 사유 2~3줄 상세 작성. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)<br>
                        &bull; (접근 전략 2~3줄 상세 작성. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)
                      </div>
                    </div>

                    <h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 심사 전 필수 체크리스트 및 보완 가이드</h2>
                    <div style="background-color:#ffebee; border-left:5px solid #d32f2f; padding:20px; border-radius:15px; margin-top:15px;">
                      <b style="font-size:1.1em; color:#c62828;">🚨 AI 컨설턴트 보완 조언:</b><br><br>
                      &bull; (보완 전략 1 2~3줄 작성. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)<br>
                      &bull; (보완 전략 2 2~3줄 작성. 마침표 뒤 줄바꿈 &lt;br&gt; 필수)
                    </div>
                    """
                    
                    response = model.generate_content(prompt)
                    status.update(label="✅ 잼(Jam)의 최적화 매칭 리포트 생성 완료!", state="complete")
                
                st.markdown(response.text, unsafe_allow_html=True)
                st.balloons()
                
                # --- [다운로드 버튼 기능] ---
                st.divider()
                st.subheader("💾 매칭 리포트 저장 (화면 폰트 100% 보존 1페이지 출력)")
                
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
                        body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; padding: 40px; line-height: 1.8; color: #333; max-width: 1000px; margin: 0 auto; font-size: 16px; background-color: #fff; }}
                        h1 {{ color: #111; text-align: center; margin-bottom: 40px; font-size: 32px; font-weight: bold; }}
                        h2 {{ color: #174EA6; border-bottom: 2px solid #174EA6; padding-bottom: 8px; margin-top: 40px; font-size: 26px; font-weight: bold; }}
                        .print-btn {{ display: block; width: 100%; padding: 15px; background-color: #174EA6; color: white; font-size: 18px; font-weight: bold; border: none; border-radius: 10px; cursor: pointer; margin-bottom: 30px; text-align: center; }}
                        .print-btn:hover {{ background-color: #123C85; }}
                        
                        @media print {{ 
                            .print-btn {{ display: none; }} 
                            @page {{ size: A4; margin: 10mm; }}
                            body {{ padding: 0 !important; font-size: 14.5px !important; color: black !important; max-width: 100% !important; line-height: 1.5 !important; zoom: 0.82; }} 
                            h1 {{ margin: 0 0 10px 0 !important; font-size: 24px !important; }}
                            h2 {{ margin: 15px 0 5px 0 !important; font-size: 18px !important; padding-bottom: 4px !important; border-bottom: 2px solid #174EA6 !important; }}
                            div {{ padding: 12px 15px !important; margin-bottom: 8px !important; border-radius: 8px !important; page-break-inside: avoid; line-height: 1.4 !important; }}
                            br {{ display: block; content: ""; margin-top: 2px; }}
                            hr {{ margin-bottom: 15px !important; margin-top: 10px !important; }}
                        }}
                    </style>
                </head>
                <body>
                    <button class="print-btn" onclick="window.print()">🖨️ 클릭하여 PDF로 저장하기</button>
                    <h1>🎯 AI 정책자금 최적화 매칭 리포트: {c_name}</h1>
                    <hr style="margin-bottom: 15px;">
                    {response.text}
                </body>
                </html>
                """
                st.download_button(label="📥 매칭 리포트 다운로드", data=html_export, file_name=f"{safe_file_name}_매칭리포트.html", mime="text/html", type="primary")

            except Exception as e:
                st.error(f"❌ 분석 중 오류 발생: {str(e)}")

    # --- [입력 화면 (대시보드)] ---
    else:
        st.title("📊 AI 컨설팅 대시보드")
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            if st.button("📊 1. 기업분석리포트 생성", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "REPORT"
                st.rerun()
        with col_t2: 
            if st.button("💡 2. 정책자금 매칭 리포트", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "MATCHING"
                st.rerun()
        with col_t3: st.button("📝 3. 사업계획서 생성", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # 1. 기업현황
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
            
            lease_status = st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
            if lease_status == "임대":
                lc1, lc2 = st.columns(2)
                with lc1: st.number_input("보증금(만원)", value=0, step=1, key="in_lease_deposit")
                with lc2: st.number_input("월임대료(만원)", value=0, step=1, key="in_lease_rent")
                
        with c3:
            st.text_input("전화번호", key="in_biz_tel")
            
            has_add_biz = st.radio("추가사업장현황", ["무", "유"], horizontal=True, key="in_has_additional_biz")
            if has_add_biz == "유":
                st.text_input("추가 사업장 정보 (예: 공장 주소 등)", key="in_additional_biz_addr")
                
            st.text_input("사업장 주소", key="in_biz_addr")

        st.markdown("<br>", unsafe_allow_html=True)

        # 2. 대표자 정보
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

        # 3. 신용 및 연체 정보
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

        # 4. 재무 현황
        st.header("4. 재무현황")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.number_input("금년 매출(만원)", value=0, step=1, key="in_sales_current")
        with m2: st.number_input("25년도 매출합계(만원)", value=0, step=1, key="in_sales_2025")
        with m3: st.number_input("24년도 매출합계(만원)", value=0, step=1, key="in_sales_2024")
        with m4: st.number_input("23년도 매출합계(만원)", value=0, step=1, key="in_sales_2023")

        st.markdown("<br>", unsafe_allow_html=True)

        # 5. 기대출현황
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

        # 6. 필요자금
        st.header("6. 필요자금")
        p1, p2, p3 = st.columns([1, 1, 2])
        with p1: st.selectbox("자금구분", ["운전자금", "시설자금"], key="in_fund_type")
        with p2: st.number_input("필요자금액(만원)", value=0, step=1, key="in_req_amount")
        with p3: st.text_input("자금사용용도", key="in_fund_purpose")

        st.markdown("<br>", unsafe_allow_html=True)

        # 7. 인증현황
        st.header("7. 인증현황")
        ac1, ac2, ac3, ac4 = st.columns(4)
        with ac1: st.checkbox("소상공인확인서", key="in_chk_1"); st.checkbox("창업확인서", key="in_chk_2")
        with ac2: st.checkbox("여성기업확인서", key="in_chk_3"); st.checkbox("이노비즈", key="in_chk_4")
        with ac3: st.checkbox("벤처인증", key="in_chk_6"); st.checkbox("뿌리기업확인서", key="in_chk_7")
        with ac4: st.checkbox("ISO인증", key="in_chk_10")

        st.markdown("<br>", unsafe_allow_html=True)

        # 8. 비즈니스 정보
        st.header("8. 비즈니스 정보")
        st.text_area("[아이템]", key="in_item_desc")
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
        st.success("✅ 세팅 완료! 좌측에 API 키 저장하시고 상단의 [1/2 리포트 생성] 버튼을 클릭해 주십시오.")
