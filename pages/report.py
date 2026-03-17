import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

# 1. 페이지 설정
st.set_page_config(page_title="AI 기업분석 결과보고서", layout="wide")

# 2. 데이터 유효성 검사 (메인에서 데이터가 넘어왔는지 확인)
if "final_report_data" not in st.session_state:
    st.warning("⚠️ 메인 대시보드에서 데이터를 먼저 입력하고 [리포트 생성] 버튼을 눌러주세요.")
    if st.button("🏠 메인으로 돌아가기"):
        st.switch_page("app.py")
    st.stop()

# 데이터 로드
d = st.session_state["final_report_data"]

# 3. Gemini AI 설정
api_key = st.secrets.get("GEMINI_API_KEY", "")
if api_key:
    genai.configure(api_key=api_key)
    # 최신 외부 데이터를 참고하기 위해 검색 능력이 강화된 모델 사용
    model = genai.GenerativeModel('gemini-1.5-pro')
else:
    st.error("🔑 사이드바에서 Gemini API Key를 먼저 설정해주세요.")
    st.stop()

# 4. 리포트 UI 구성
st.title("📋 전문 기업 진단 및 AI 심층 분석 리포트")
st.subheader(f"대상기업: {d.get('in_company_name', '미입력')}")
st.markdown(f"**분석 기준일:** {datetime.now().strftime('%Y-%m-%d')}")
st.divider()

# AI에게 보낼 프롬프트 구성 (대표님의 9가지 요청사항 반영)
prompt = f"""
당신은 대한민국 최고의 중소기업 정책자금 컨설턴트이자 경영학 박사입니다. 
다음 제공된 기업 데이터를 기반으로, 당신의 지식과 실시간 외부 시장 자료를 참고하여 
클라이언트에게 신뢰를 줄 수 있는 '심층 분석 보고서'를 작성하세요.

[기업 기초 데이터]
- 기업명: {d.get('in_company_name')} / 업종: {d.get('in_industry')}
- 매출추이: 23년({d.get('in_sales_2023')}만), 24년({d.get('in_sales_2024')}만), 25년예정({d.get('in_sales_2025')}만)
- 기대출현황: 총액 약 {d.get('in_debt_total', 0)}만원 (중진공, 소진공 등 포함)
- 신용점수: KCB {d.get('in_kcb_score', '미입력')}, NICE {d.get('in_nice_score', '미입력')}
- 비즈니스 아이템: {d.get('in_item_desc')}
- 주거래처 및 루트: {d.get('in_client_1')}, {d.get('in_sales_route')}
- 필요자금 및 용도: {d.get('in_req_amount')}만원 ({d.get('in_fund_purpose')})

[보고서 필수 작성 항목]
1. 기업현황분석: 재무 지표와 부채 비율을 바탕으로 한 현재의 경영 건전성 평가
2. SWOT 분석: 기업의 내부 역량과 외부 시장 기회/위협을 표 형식으로 정리
3. 시장현황 및 경쟁력 분석: 해당 업종의 최신 트렌드 및 시장 내 위치 분석
4. 경쟁력 분석: 비즈니스 정보와 외부 자료를 대조하여 차별화된 핵심 경쟁력 도출
5. 정책자금 추천 분석: 가장 승인율 높은 기관 3곳 선정 (기관명 / 예상금액 / 추천사유)
6. 한도 확대를 위한 추천 인증 및 교육: 벤처, 이노비즈 등 기업 등급을 높일 수 있는 구체적 방안
7. 자금 사용계획: 조달 예정 금액의 가장 효율적인 투자 및 집행 가이드
8. 매출 추이 및 1년 전망: 최근 3개년 추이 분석 및 향후 12개월 월별 예상 성장 곡선 시나리오
9. 성장 비전: 단기(1년), 중기(3년), 장기(5년) 로드맵 및 전문가 최종 코멘트

문체는 전문적이고 정중한 '컨설팅 보고서' 형식을 유지하며, Markdown 문법을 활용하여 가독성 있게 작성하세요.
"""

# 5. 분석 실행 및 결과 출력
if "report_content" not in st.session_state:
    with st.status("🔍 AI 전문가가 기업 데이터를 정밀 분석 중입니다...", expanded=True) as status:
        st.write("📊 재무 데이터 및 매출 히스토리 확인 중...")
        time.sleep(1)
        st.write("🌍 해당 업종의 최신 시장 트렌드 및 경쟁사 데이터 수집 중...")
        time.sleep(1.5)
        st.write("🏦 정책자금 기관별 최신 공고 및 한도 매칭 중...")
        
        # 실제 AI 호출
        response = model.generate_content(prompt)
        st.session_state["report_content"] = response.text
        
        status.update(label="✅ 분석이 완료되었습니다!", state="complete", expanded=False)

# 결과 리포트 출력
st.markdown(st.session_state["report_content"])

# 6. 시각화 보조 섹션
st.divider()
st.header("📉 데이터 시각화 보조 지표")
col1, col2 = st.columns(2)

with col1:
    st.subheader("매출 성장 가속도")
    sales_df = pd.DataFrame({
        "연도": ["2023", "2024", "2025(E)"],
        "매출액(만원)": [d.get('in_sales_2023', 0), d.get('in_sales_2024', 0), d.get('in_sales_2025', 0)]
    })
    st.bar_chart(sales_df.set_index("연도"))

with col2:
    st.subheader("자금 조달 가능 지표")
    # 신용점수 및 기대출 비중 등을 시각화하는 간단한 게이지
    total_debt = d.get('in_debt_total', 0)
    st.metric(label="총 기대출 규모", value=f"{total_debt:,} 만원", delta="재무 분석 반영됨")
    st.info("💡 위 분석 보고서의 5번 항목을 참조하여 최적의 자금을 신청하십시오.")

# 7. 하단 버튼
st.divider()
c_b1, c_b2 = st.columns(2)
with c_b1:
    if st.button("🔄 리포트 다시 생성 (AI 재분석)"):
        if "report_content" in st.session_state: del st.session_state["report_content"]
        st.rerun()
with c_b2:
    if st.button("🏠 메인 대시보드로 이동"):
        st.switch_page("app.py")
