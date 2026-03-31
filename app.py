import streamlit as st
# engine_analysis.py에서 리포트 생성 함수를 불러옵니다.
from engine_analysis import generate_enterprise_report

# [설정] 페이지 기본 설정
st.set_page_config(page_title="기업 분석 AI 시스템", layout="wide")

# [핵심] 데이터 초기화 - 이 부분이 가장 먼저 실행되어야 에러가 안 납니다.
if 'company_data' not in st.session_state:
    st.session_state['company_data'] = {
        'name': "",
        'biz_no': "",
        'description': "",
        'is_saved': False
    }

def main():
    # 사이드바 메뉴 구성
    with st.sidebar:
        st.title("🚀 분석 메뉴")
        menu = st.radio(
            "이동할 화면을 선택하세요",
            ["🏠 메인 대시보드", "📝 기업정보 입력", "📊 리포트 결과 보기"]
        )
        st.divider()
        
        # [에러 해결 부분] 데이터가 있는지 안전하게 확인하고 표시
        company_info = st.session_state.get('company_data', {})
        if company_info.get('is_saved'):
            st.success(f"✅ 분석 중: {company_info.get('name')}")

    # --- 1. 메인 대시보드 화면 ---
    if menu == "🏠 메인 대시보드":
        st.title("🏢 기업 분석 메인 대시보드")
        st.write("분석 시스템에 오신 것을 환영합니다. 왼쪽 메뉴에서 정보를 입력하고 리포트를 생성하세요.")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            status = "입력 완료" if st.session_state['company_data']['is_saved'] else "입력 대기"
            st.metric("분석 진행 상태", status)
        with col2:
            st.metric("연동 엔진", "4개 작동 중")
        with col3:
            st.metric("AI 모델", "Gemini 1.5 Flash")

        st.divider()
        st.subheader("📌 현재 선택된 기업")
        if st.session_state['company_data']['is_saved']:
            st.info(f"기업명: {st.session_state['company_data']['name']} / 사업자번호: {st.session_state['company_data']['biz_no']}")
        else:
            st.info("현재 분석 중인 기업이 없습니다. '기업정보 입력' 메뉴를 이용해 주세요.")

    # --- 2. 기업정보 입력 화면 ---
    elif menu == "📝 기업정보 입력":
        st.title("📝 기업 정보 입력")
        
        # 폼(Form)을 사용해 입력값 관리
        with st.form("input_form"):
            c_name = st.text_input("기업명", value=st.session_state['company_data']['name'])
            c_no = st.text_input("사업자번호", value=st.session_state['company_data']['biz_no'])
            c_desc = st.text_area("기업 설명 및 특이사항", value=st.session_state['company_data']['description'], height=150)
            
            save_btn = st.form_submit_button("기업 정보 저장 및 고정")
            
            if save_btn:
                st.session_state['company_data'] = {
                    'name': c_name,
                    'biz_no': c_no,
                    'description': c_desc,
                    'is_saved': True
                }
                st.success(f"'{c_name}' 정보가 저장되었습니다. '리포트 결과 보기' 메뉴로 이동해 보세요!")

    # --- 3. 리포트 결과 보기 화면 ---
    elif menu == "📊 리포트 결과 보기":
        st.title("📊 AI 분석 리포트 결과")
        
        if not st.session_state['company_data']['is_saved']:
            st.warning("⚠️ 입력된 기업 정보가 없습니다. '기업정보 입력' 메뉴에서 정보를 먼저 저장해 주세요.")
        else:
            st.write(f"### 분석 대상: **{st.session_state['company_data']['name']}**")
            
            if st.button("🚀 AI 리포트 생성 시작"):
                with st.spinner("AI가 리포트를 생성하고 있습니다. 잠시만 기다려 주세요..."):
                    # engine_analysis.py의 함수 호출
                    report = generate_enterprise_report(st.session_state['company_data'])
                    st.divider()
                    st.markdown(report)
            
            st.divider()
            # 입력화면으로 돌아가기 버튼 (데이터는 session_state 덕분에 유지됨)
            if st.button("⬅️ 입력 화면으로 돌아가기"):
                st.info("사이드바의 '📝 기업정보 입력' 메뉴를 클릭하면 이전 데이터를 수정할 수 있습니다.")

if __name__ == "__main__":
    main()
