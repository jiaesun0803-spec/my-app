import streamlit as st
from engine_analysis import generate_enterprise_report

# [설정] 페이지 기본 설정
st.set_page_config(page_title="기업 분석 시스템", layout="wide")

# [데이터 유지] 다른 업체를 선택하기 전까지 정보를 저장하는 저장소 생성
if 'company_data' not in st.session_state:
    st.session_state['company_data'] = {
        'name': "",
        'biz_no': "",
        'description': ""
    }

def main():
    st.sidebar.title("메뉴")
    page = st.sidebar.radio("이동", ["입력화면 및 대시보드", "리포트 결과"])

    # --- 1. 입력화면 및 대시보드 ---
    if page == "입력화면 및 대시보드":
        st.title("🏢 기업 정보 입력 및 대시보드")
        
        with st.container():
            st.info("현재 입력된 정보를 유지합니다. 다른 업체를 분석하려면 내용을 수정 후 '저장'하세요.")
            
            # session_state에 저장된 값을 불러와서 입력창에 표시 (데이터 유지의 핵심)
            c_name = st.text_input("기업명", value=st.session_state['company_data']['name'])
            c_no = st.text_input("사업자번호", value=st.session_state['company_data']['biz_no'])
            c_desc = st.text_area("기업 설명/특이사항", value=st.session_state['company_data']['description'])

            if st.button("기업 정보 저장 및 확정"):
                st.session_state['company_data'] = {
                    'name': c_name,
                    'biz_no': c_no,
                    'description': c_desc
                }
                st.success(f"'{c_name}' 기업 정보가 고정되었습니다. 이제 리포트를 생성할 수 있습니다.")

    # --- 2. 리포트 결과 화면 ---
    elif page == "리포트 결과":
        st.title("📊 AI 분석 리포트")
        
        # 저장된 데이터가 있는지 확인
        current_info = st.session_state['company_data']
        
        if not current_info['name']:
            st.warning("입력화면에서 기업 정보를 먼저 입력하고 '저장' 버튼을 눌러주세요.")
        else:
            st.write(f"### 분석 대상: {current_info['name']} ({current_info['biz_no']})")
            
            if st.button("AI 리포트 생성 시작"):
                with st.spinner("AI 분석 엔진이 작동 중입니다..."):
                    # engine_analysis.py에 있는 함수를 호출합니다.
                    report = generate_enterprise_report(current_info)
                    st.markdown("---")
                    st.markdown(report)

            # [문제 해결] 입력화면으로 돌아가기 버튼
            # 이 버튼을 눌러도 위에서 설정한 session_state 덕분에 데이터는 그대로 유지됩니다.
            if st.button("⬅️ 입력화면으로 돌아가기"):
                st.info("입력화면으로 돌아갑니다. 데이터는 유지됩니다.")
                # 실제 페이지 전환은 상단 사이드바나 상태 변경으로 제어됩니다.

if __name__ == "__main__":
    main()
