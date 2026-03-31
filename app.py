import streamlit as st
from engine_analysis import generate_enterprise_report

# 1. 페이지 설정 및 데이터 보존 (session_state) 세팅
st.set_page_config(page_title="기업 분석 AI 시스템", layout="wide", initial_sidebar_state="expanded")

# 기업 정보가 다른 페이지 이동 시에도 사라지지 않도록 저장소 초기화
if 'company_data' not in st.session_state:
    st.session_state['company_data'] = {
        'name': "",
        'biz_no': "",
        'description': "",
        'is_saved': False
    }

# 2. 사이드바 메뉴 구성
with st.sidebar:
    st.title("🚀 분석 메뉴")
    menu = st.radio(
        "이동할 화면을 선택하세요",
        ["🏠 메인 대시보드", "📝 기업정보 입력", "📊 리포트 결과 보기", "💰 자금 매칭/대출 (엔진)"]
    )
    st.divider()
    if st.session_state['company_data']['is_saved']:
        st.success(f"현재 분석 중: {st.session_state['company_data']['name']}")

# 3. 각 메뉴별 화면 구성
# --- [메인 대시보드] ---
if menu == "🏠 메인 대시보드":
    st.title("🏢 기업 분석 메인 대시보드")
    st.write("분석 시스템에 오신 것을 환영합니다. 왼쪽 메뉴에서 정보를 입력하고 리포트를 생성하세요.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("분석 진행 상태", "입력 완료" if st.session_state['company_data']['is_saved'] else "입력 대기")
    with col2:
        st.metric("연동 엔진", "4개 작동 중")
    with col3:
        st.metric("AI 모델", "Gemini 1.5 Flash")

    st.divider()
    st.subheader("📌 진행 중인 기업 요약")
    if st.session_state['company_data']['is_saved']:
        st.json(st.session_state['company_data'])
    else:
        st.info("현재 분석 중인 기업이 없습니다.")

# --- [기업정보 입력] ---
elif menu == "📝 기업정보 입력":
    st.title("📝 기업 정보 입력")
    st.write("분석할 기업의 상세 정보를 입력하세요. 저장 후 페이지를 이동해도 데이터가 유지됩니다.")
    
    with st.form("input_form"):
        name = st.text_input("기업명", value=st.session_state['company_data']['name'])
        biz_no = st.text_input("사업자번호", value=st.session_state['company_data']['biz_no'])
        description = st.text_area("주요 업종 및 특이사항", value=st.session_state['company_data']['description'], height=150)
        
        save_btn = st.form_submit_button("정보 저장 및 확정")
        
        if save_btn:
            st.session_state['company_data'] = {
                'name': name,
                'biz_no': biz_no,
                'description': description,
                'is_saved': True
            }
            st.success(f"'{name}' 정보가 저장되었습니다. 이제 리포트 결과 메뉴로 이동하세요.")

# --- [리포트 결과 보기] ---
elif menu == "📊 리포트 결과 보기":
    st.title("📊 AI 분석 리포트")
    
    if not st.session_state['company_data']['is_saved']:
        st.warning("⚠️ 기업 정보가 없습니다. '기업정보 입력' 메뉴에서 먼저 저장해주세요.")
    else:
        st.write(f"### 분석 대상: **{st.session_state['company_data']['name']}**")
        
        if st.button("🚀 AI 리포트 생성 시작"):
            with st.spinner("AI 분석 엔진이 데이터를 분석 중입니다..."):
                # engine_analysis.py의 함수 호출
                report = generate_enterprise_report(st.session_state['company_data'])
                st.divider()
                st.markdown(report)
        
        st.divider()
        if st.button("⬅️ 입력 화면으로 돌아가기"):
            # 이 버튼을 눌러도 session_state가 유지되므로 데이터는 삭제되지 않습니다.
            st.info("정보가 유지된 상태로 입력 화면으로 이동할 수 있습니다. 사이드바 메뉴를 클릭하세요.")

# --- [기타 엔진 (더미)] ---
elif menu == "💰 자금 매칭/대출 (엔진)":
    st.title("💰 금융 엔진 분석")
    st.info("engine_loan.py 및 engine_matching.py 연동 구역입니다.")
