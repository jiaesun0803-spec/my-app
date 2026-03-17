import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import json

# 1. 🔐 폐쇄형 보안 설정 (로그인 기능)
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 AI 컨설팅 시스템")
        # Secrets 설정을 아직 안 하셨을 경우를 대비해 기본 비번 '1234'로 세팅해둡니다.
        # 나중에 Secrets에 LOGIN_PASSWORD를 설정하면 그 값으로 작동합니다.
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

# 2. 메인 프로그램 시작
if check_password():
    # API 설정 (Secrets에서 가져오기)
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if api_key:
        genai.configure(api_key=api_key)

    st.title("📊 AI 컨설팅 시스템")
    st.markdown("---")

    # --- 대시보드 내용 시작 ---
    
    # 1. 일반 현황 (기본값 유지)
    st.subheader("🏢 1. 일반 현황 및 대표자 정보")
    c1, c2, c3 = st.columns(3)
    with c1:
        company_name = st.text_input("기업명(상호)", value="테스트기업(주)")
        industry = st.selectbox("업종", ["제조업", "도소매업", "서비스업", "IT업", "건설업", "기타"])
    with c2:
        rep_name = st.text_input("대표자명")
    with c3:
        biz_address = st.text_input("사업장 주소")

    st.markdown("---")

    # 2. 재무 및 신용현황 (수정 요청 반영)
    st.subheader("💳 2. 재무 및 신용 현황")
    
    st.markdown("##### 📌 최근 매출 추이 (만 원 단위)")
    rc1, rc2, rc3, rc4 = st.columns(4)
    with rc1: sales_current = st.number_input("금년 매출", value=0)
    with rc2: sales_2025 = st.number_input("25년도 매출", value=0)
    with rc3: sales_2024 = st.number_input("24년도 매출", value=0)
    with rc4: sales_2023 = st.number_input("23년도 매출", value=0)

    st.divider()

    st.markdown("##### 📌 신용 및 연체 정보")
    col_v1, col_v2, col_v3 = st.columns([1, 1, 2])
    with col_v1:
        tax_overdue = st.radio("세금체납 여부", ["무", "유"], horizontal=True)
    with col_v2:
        fin_overdue = st.radio("금융연체 여부", ["무", "유"], horizontal=True)
    with col_v3:
        credit_score = st.slider("나이스(NICE) 신용점수", 0, 1000, 800)
        
        # 반달형 그래프
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = credit_score,
            gauge = {
                'axis': {'range': [0, 1000]},
                'bar': {'color': "#174EA6"},
                'steps': [
                    {'range': [0, 600], 'color': "#FCE8E6"},
                    {'range': [600, 800], 'color': "#FEF7E0"},
                    {'range': [800, 1000], 'color': "#E6F4EA"}
                ],
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': credit_score}
            }))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 3. 기대출 및 필요자금 (수정 요청 반영)
    st.subheader("💰 3. 기대출 및 필요자금 현황")
    
    st.markdown("##### 📌 기대출 세부 내역 (기관별 / 만 원 단위)")
    # 첫 번째 줄
    d_row1_1, d_row1_2, d_row1_3 = st.columns(3)
    with d_row1_1: debt_kosme = st.number_input("중진공(중소벤처기업진흥공단)", value=0)
    with d_row1_2: debt_semas = st.number_input("소진공(소상공인정책자금)", value=0)
    with d_row1_3: debt_koreg = st.number_input("신용보증재단", value=0)
    
    # 두 번째 줄
    d_row2_1, d_row2_2, d_row2_3, d_row2_4, d_row2_5 = st.columns(5)
    with d_row2_1: debt_kodit = st.number_input("신용보증기금", value=0)
    with d_row2_2: debt_kibo = st.number_input("기술보증기금", value=0)
    with d_row2_3: debt_etc = st.number_input("기타", value=0)
    with d_row2_4: debt_credit = st.number_input("신용대출", value=0)
    with d_row2_5: debt_coll = st.number_input("담보대출", value=0)

    st.divider()

    st.markdown("##### 📌 필요자금 현황")
    f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
    with f_col1: fund_type = st.selectbox("자금 구분", ["운전자금", "시설자금"])
    with f_col2: req_fund = st.number_input("필요자금액(만원)", value=0)
    with f_col3: fund_purpose = st.text_input("자금사용용도")

    st.markdown("---")

    # 4. 비즈니스 세부 현황 (4번으로 배치)
    st.subheader("📝 4. 비즈니스 세부 현황 및 인증")
    actual_work = st.text_area("아이템(주요사업) 및 상세 현황")
    
    if st.button("📊 기업분석 리포트 생성 (Gemini AI)", type="primary", use_container_width=True):
        st.info("리포트 생성 기능을 실행합니다. (API 키 설정 필요)")
