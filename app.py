import streamlit as st

# [중요] 페이지 설정 및 데이터 초기화
st.set_page_config(page_title="기업 분석 대시보드", layout="wide")

# 다른 업체 정보를 선택하기 전까지 데이터를 유지하기 위한 저장소(Session State)
if 'company_info' not in st.session_state:
    st.session_state['company_info'] = {
        'name': "",
        'biz_no': "",
        'industry': ""
    }

def main():
    st.title("🏢 기업 정보 입력 대시보드")
    st.subheader("분석할 기업의 정보를 입력해 주세요.")

    # 기존에 저장된 데이터가 있다면 불러와서 입력창에 표시
    with st.form("company_form"):
        name = st.text_input("기업명", value=st.session_state['company_info']['name'])
        biz_no = st.text_input("사업자 번호", value=st.session_state['company_info']['biz_no'])
        industry = st.text_input("주요 업종", value=st.session_state['company_info']['industry'])
        
        submit_button = st.form_submit_button("기업 정보 저장 및 리포트 준비")

    if submit_button:
        # 입력한 정보를 저장소에 고정 (다른 업체 입력 전까지 유지)
        st.session_state['company_info'] = {
            'name': name,
            'biz_no': biz_no,
            'industry': industry
        }
        st.success(f"'{name}' 기업 정보가 저장되었습니다. 리포트 화면으로 이동하세요.")

    # 리포트 화면으로 이동하는 버튼
    if st.button("리포트 생성 화면으로 이동 👉"):
        if st.session_state['company_info']['name']:
            st.switch_page("pages/report.py") # 파일 경로에 맞춰 수정 필요
        else:
            st.error("먼저 기업 정보를 입력하고 저장 버튼을 눌러주세요.")

if __name__ == "__main__":
    main()
