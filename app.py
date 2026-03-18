import streamlit as st
import json
import os
import time
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go

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

# --- 금액 변환 로직 (소수점 완벽 제거: float -> int 변환 강제) ---
def format_kr_currency(value):
    try:
        val = int(float(value)) # 소수점이 들어와도 정수로 강제 변환
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

if check_password():
    # --- 파일 관리 (API 키 및 업체 DB) ---
    KEY_FILE = "gemini_key.txt"
    DB_FILE = "company_db.json"
    
    # API 키 불러오기/저장 로직
    def load_key():
        if os.path.exists(KEY_FILE):
            try:
                with open(KEY_FILE, "r", encoding="utf-8") as f: return f.read().strip()
            except: return ""
        return ""
        
    def save_key(key):
        with open(KEY_FILE, "w", encoding="utf-8") as f: f.write(key.strip())

    # DB 불러오기/저장 로직
    def load_db():
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: return {}
        return {}
        
    def save_db(db_data):
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db_data, f, ensure_ascii=False, indent=4)

    # 신용등급 산출 로직
    def get_credit_grade(score, type="NICE"):
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
    # 1. 사이드바 (API 설정, 업체관리) - 백업기능 제거
    # ==========================================
    st.sidebar.header("⚙️ AI 엔진 설정")
    # 세션 시작 시 파일에서 API 키를 읽어옴
    if "api_key" not in st.session_state: 
        st.session_state["api_key"] = load_key()
        
    api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
    if st.sidebar.button("💾 API 키 영구 저장"):
        st.session_state["api_key"] = api_key_input
        save_key(api_key_input) # 파일에 쓰기
        st.sidebar.success("✅ API 키 영구 저장 완료!")
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
        st.sidebar.info("개발 중인 기능입니다.")
    if st.sidebar.button("📝 3. 사업계획서 생성", use_container_width=True):
        st.sidebar.info("개발 중인 기능입니다.")

    # ==========================================
    # 2. 화면 모드 제어 (리포트 vs 대시보드)
    # ==========================================
    if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
    if "permanent_data" not in st.session_state: st.session_state["permanent_data"] = {}

    # --- [리포트 화면] ---
    if st.session_state["view_mode"] == "REPORT":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력')
        
        st.title("📋 시각화 기반 AI 기업분석 리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")
        
        if not st.session_state["api_key"]:
            st.error("⚠️ 좌측 사이드바에 API 키를 입력하고 [영구 저장]을 눌러주세요.")
        else:
            try:
                with st.status("🚀 AI 전문가가 시각화 리포트를 생성 중입니다...", expanded=True) as status:
                    # 모델 탐색 로직 (404 에러 방지)
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
                    
                    # 변수 할당 및 포맷팅
                    c_ind = d.get('in_industry', '미입력')
                    rep_name = d.get('in_rep_name', '미입력')
                    biz_no = d.get('in_raw_biz_no', '미입력')
                    corp_no = d.get('in_raw_corp_no', '')
                    corp_text = f" ({corp_no})" if corp_no else ""
                    address = d.get('in_biz_addr', '미입력')
                    
                    # 임대여부 및 보증금/월세 텍스트 생성
                    lease_status = d.get('in_lease_status', '자가')
                    if lease_status == '임대':
                        deposit_kr = format_kr_currency(d.get('in_lease_deposit', 0))
                        rent_kr = format_kr_currency(d.get('in_lease_rent', 0))
                        lease_text = f"[임대: 보증금 {deposit_kr} / 월임대료 {rent_kr}]"
                    else:
                        lease_text = "[자가]"
                    
                    # 단위 변환 적용 (소수점 원천 차단)
                    s_cur = format_kr_currency(d.get('in_sales_current', 0))
                    s_25 = format_kr_currency(d.get('in_sales_2025', 0))
                    s_24 = format_kr_currency(d.get('in_sales_2024', 0))
                    s_23 = format_kr_currency(d.get('in_sales_2023', 0))
                    req_fund = format_kr_currency(d.get('in_req_amount', 0))
                    
                    kcb_s = d.get('in_kcb_score', 0)
                    nice_s = d.get('in_nice_score', 0)
                    item = d.get('in_item_desc', '미입력')
                    market = d.get('in_market_status', '미입력')
                    diff = d.get('in_diff_point', '미입력')
                    
                    total_debt = int(float(d.get('in_debt_kosme', 0))) + int(float(d.get('in_debt_semas', 0))) + int(float(d.get('in_debt_koreg', 0))) + int(float(d.get('in_debt_kodit', 0))) + int(float(d.get('in_debt_kibo', 0))) + int(float(d.get('in_debt_etc', 0))) + int(float(d.get('in_debt_credit', 0))) + int(float(d.get('in_debt_coll', 0)))
                    
                    # HTML 기반 강력한 프롬프트
                    prompt = f"""
                    당신은 20년 경력의 중소기업 경영컨설턴트입니다. 
                    출력 시 각 카테고리 제목에는 이모지나 부연 설명을 절대 붙이지 말고 오직 숫자와 제목만 적으세요 (예: '1. 기업현황분석').
                    마크다운과 HTML 태그(div, table 등)를 사용하여 아래 양식과 서식 규칙을 **반드시 100% 똑같이** 지켜서 출력하세요.

                    [데이터]
                    - 기업명: {c_name} / 대표자: {rep_name} / 업종: {c_ind}
                    - 사업자번호: {biz_no}{corp_text} 
                    - 주소 및 사업장형태: {address} {lease_text}
                    - 매출액: 23년 {s_23}, 24년 {s_24}, 25년예상 {s_25}, 금년 {s_cur}
                    - 총 기대출: {format_kr_currency(total_debt)}
                    - 비즈니스 아이템: {item} / 시장현황: {market} / 차별화: {diff}
                    - 필요자금: {req_fund}

                    [출력 양식 및 규칙]
                    
                    ### 1. 기업현황분석
                    <div style="background-color:#f8f9fa; padding:20px; border-radius:15px; border:1px solid #e0e0e0; margin-bottom:15px;">
                      <b>기업명:</b> {c_name} <br>
                      <b>대표자명:</b> {rep_name} <br>
                      <b>업종:</b> {c_ind} <br>
                      <b>사업자등록번호:</b> {biz_no}{corp_text} <br>
                      <b>사업장 주소:</b> {address} <span style="color:#1565c0; font-weight:bold;">{lease_text}</span>
                    </div>
                    (여기에 매출/대출 숫자는 노출하지 말고, 위 데이터를 바탕으로 한 기업의 건전성과 현재 상태에 대한 '분석 코멘트'만 3~4줄 작성하세요.)

                    ### 2. SWOT 분석
                    <table style="width:100%; text-align:center; border-collapse: separate; border-spacing: 10px;">
                      <tr>
                        <td style="background-color:#e3f2fd; padding:20px; border-radius:15px; width:50%;"><b>S (강점)</b><br>내용작성</td>
                        <td style="background-color:#ffebee; padding:20px; border-radius:15px; width:50%;"><b>W (약점)</b><br>내용작성</td>
                      </tr>
                      <tr>
                        <td style="background-color:#e8f5e9; padding:20px; border-radius:15px;"><b>O (기회)</b><br>내용작성</td>
                        <td style="background-color:#fff3e0; padding:20px; border-radius:15px;"><b>T (위협)</b><br>내용작성</td>
                      </tr>
                    </table>

                    ### 3. 시장현황 및 경쟁력
                    <div style="background-color:#f3e5f5; padding:20px; border-radius:15px; margin-bottom:10px;">
                      (이 둥근 사각형 박스 안에 시장현황과 경쟁력을 Bullet point로 작성하세요)
                    </div>

                    ### 4. 핵심경쟁력분석
                    <div style="background-color:#e0f7fa; padding:20px; border-radius:15px; margin-bottom:10px;">
                      (이 둥근 사각형 박스 안에 핵심 경쟁력과 차별화 포인트를 작성하세요)
                    </div>

                    ### 5. 정책자금 추천
                    (아래와 같이 순번을 매기고, 기관/금액은 크고 굵게, 사유는 그 아래에 일반 글씨로 작성. 총 3개 추천)
                    1. <b style="font-size:1.2em; color:#1565c0;">[기관명] / {req_fund}</b>
                       <div style="margin-top:5px; margin-bottom:15px; color:#555;">추천사유: (작성)</div>
                    (2번, 3번도 동일한 양식으로 작성)

                    ### 6. 추천 인증 및 교육
                    <div style="background-color:#fff8e1; padding:20px; border-radius:15px; margin-bottom:10px;">
                      (이 둥근 사각형 박스 안에 한도 확대를 위한 인증/교육 전략을 작성하세요)
                    </div>

                    ### 7. 자금 사용계획
                    <table style="width:100%; border-collapse: collapse; text-align:left;">
                     <tr style="background-color:#eceff1;">
                       <th style="padding:15px; border:1px solid #ccc; border-radius:10px 0 0 0;">구분</th>
                       <th style="padding:15px; border:1px solid #ccc; border-radius:0 10px 0 0;">상세 사용계획</th>
                     </tr>
                     <tr>
                       <td style="padding:15px; border:1px solid #ccc; font-weight:bold;">운전자금/시설자금</td>
                       <td style="padding:15px; border:1px solid #ccc; font-size:0.85em;">(작성)</td>
                     </tr>
                    </table>

                    ### 8. 매출 1년 전망
                    <div style="display:flex; justify-content:space-between; align-items:center; text-align:center; flex-wrap:wrap;">
                      <div style="background-color:#e8eaf6; padding:15px; border-radius:15px; flex:1; margin:5px; font-weight:bold;">1단계<br>(내용)</div>
                      <div style="font-size:1.5em;">➡️</div>
                      <div style="background-color:#e8eaf6; padding:15px; border-radius:15px; flex:1; margin:5px; font-weight:bold;">2단계<br>(내용)</div>
                      <div style="font-size:1.5em;">➡️</div>
                      <div style="background-color:#e8eaf6; padding:15px; border-radius:15px; flex:1; margin:5px; font-weight:bold;">3단계<br>(내용)</div>
                      <div style="font-size:1.5em;">➡️</div>
                      <div style="background-color:#e8eaf6; padding:15px; border-radius:15px; flex:1; margin:5px; font-weight:bold;">4단계<br>(내용)</div>
                    </div>

                    ### 9. 성장비전 및 AI 컨설턴트 코멘트
                    단기/중기/장기 로드맵 텍스트 작성 후,
                    <div style="background-color:#eeeeee; border-left:5px solid #1565c0; padding:20px; border-radius:15px; margin-top:15px;">
                      <b>💡 AI 컨설턴트 최종 코멘트:</b><br>
                      (작성)
                    </div>
                    """
                    
                    st.write("📍 지시하신 서식(도형, 화살표, 표) 기반 보고서 생성 중...")
                    response = model.generate_content(prompt)
                    status.update(label="✅ 분석 및 시각화 보고서 생성 완료!", state="complete")
                
                # HTML이 포함된 마크다운 렌더링
                st.markdown(response.text, unsafe_allow_html=True)
                
                # ---------------------------------------------------------
                # [8번 항목 보조] 월별 매출 상승 곡선 그래프 (Plotly)
                # ---------------------------------------------------------
                st.markdown("<br><br>", unsafe_allow_html=True)
                st.subheader("📊 [첨부] 향후 1년간 월별 매출 상승 곡선 (8번 항목 참조)")
                
                try:
                    val_24 = int(float(d.get('in_sales_2024', 0)))
                    val_25 = int(float(d.get('in_sales_2025', 0)))
                except:
                    val_24, val_25 = 1000, 2000
                
                start_val = val_24 / 12 if val_24 > 0 else 1000
                end_val = val_25 / 12 if val_25 > 0 else start_val * 1.5
                step = (end_val - start_val) / 11
                monthly_vals = [int(start_val + step * i) for i in range(12)]
                monthly_labels = [f"{i}월" for i in range(1, 13)]

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=monthly_labels, 
                    y=monthly_vals,
                    mode='lines+markers+text',
                    text=[format_kr_currency(v) for v in monthly_vals],
                    textposition="top center",
                    textfont=dict(size=11),
                    line=dict(color='#1E88E5', width=4, shape='spline'),
                    marker=dict(size=10, color='#FF5252', line=dict(width=2, color='white'))
                ))
                
                fig.update_layout(
                    xaxis_title="진행 월",
                    yaxis_title="예상 매출액",
                    xaxis=dict(tickangle=0, showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
                    template="plotly_white",
                    margin=dict(l=20, r=20, t=30, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)
                
                st.balloons()

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
        with col_t2: st.button("💡 2. 정책자금 매칭 리포트", use_container_width=True)
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
            
            # [수정 포인트] 임대 선택 시 보증금/월임대료 입력란 노출
            lease_status = st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
            if lease_status == "임대":
                lc1, lc2 = st.columns(2)
                with lc1: st.number_input("보증금(만원)", value=0, step=1, key="in_lease_deposit")
                with lc2: st.number_input("월임대료(만원)", value=0, step=1, key="in_lease_rent")
                
        with c3:
            st.text_input("전화번호", key="in_biz_tel")
            st.text_input("팩스번호", key="in_biz_fax")
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
        st.success("✅ 세팅 완료! 좌측에 API 키 저장하시고 상단의 [1. 기업분석리포트 생성] 버튼을 클릭해 주십시오.")
