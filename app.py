import streamlit as st
# engine_analysis.py 파일에서 함수를 가져옵니다.
from engine_analysis import generate_enterprise_report

# [1단계] 페이지 설정 (반드시 가장 위에 와야 합니다)
st.set_page_config(page_title="기업 분석 AI 시스템", layout="wide")

# [2단계] 데이터 저장소 초기화 (에러 방지 핵심)
# 프로그램이 시작될 때 'company_data'라는 바구니를 미리 만들어둡니다.
if 'company_data' not in st.session_state:
    st.session_state['company_data'] = {
        'name': "",
        'biz_no': "",
        'description': "",
        'is_saved': False # 이 값이 없어서 에러가 났던 부분을 해결합니다.
    }

def main():
    # [3단계] 사이드바 구성
    with st.sidebar:
        st.title("🚀 분석 메뉴")
        menu = st.radio(
            "이동할 화면을 선택하세요",
            ["🏠 메인 대시보드", "📝 기업정보 입력", "📊 리포트 결과 보기"]
        )
        st.divider()
        
        # 데이터가 저장되어 있을 때만 사이드바에 기업명 표시
        if st.session_state['company_data'].get('is_saved', False):
            st.success(f"✅ 분석 중: {st.session_state['company_data']['name']}")

    # --- 화면 1: 메인 대시보드 ---
    if menu == "🏠 메인 대시보드":
        st.title("🏢 기업 분석 메인 대시보드")
        st.write("왼쪽 메뉴에서 기업 정보를 입력하면 AI 리포트를 생성할 수 있습니다.")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            # .get()을 사용하여 값이 없어도 에러가 나지 않게 안전하게 가져옵니다.
            is_saved = st.session_state['company_data'].get('is_saved', False)
            status_text = "입력 완료" if is_saved else "입력 대기"
            st.metric("분석 진행 상태", status_text)
        with col2:
            st.metric("연동 엔진", "정상 작동 중")
        with col3:
            st.metric("AI 모델", "Gemini 1.5 Flash")

        st.divider()
        st.subheader("📌 현재 선택된 기업 정보")
        if st.session_state['company_data'].get('is_saved', False):
            st.info(f"**기업명:** {st.session_state['company_data']['name']}  \n**사업자번호:** {st.session_state['company_data']['biz_no']}")
        else:
            st.info("현재 분석 중인 기업이 없습니다. '기업정보 입력' 메뉴에서 정보를 입력해 주세요.")

    # --- 화면 2: 기업정보 입력 (데이터 유지의 핵심) ---
    elif menu == "📝 기업정보 입력":
        st.title("📝 기업 정보 입력")
        st.write("정보를 입력하고 저장하면, 다른 메뉴로 이동해도 내용이 사라지지 않습니다.")
        
        with st.form("input_form"):
            # 기존에 입력된 값이 있다면 (st.session_state에서) 가져와서 보여줍니다.
            c_name = st.text_input("기업명", value=st.session_state['company_data']['name'])
            c_no = st.text_input("사업자번호", value=st.session_state['company_data']['biz_no'])
            c_desc = st.text_area("기업 상세 설명", value=st.session_state['company_data']['description'], height=150)
            
            save_btn = st.form_submit_button("기업 정보 저장 및 확정")
            
            if save_btn:
                # 사용자가 입력한 정보를 저장소에 덮어씌웁니다.
                st.session_state['company_data'] = {
                    'name': c_name,
                    'biz_no': c_no,
                    'description': c_desc,
                    'is_saved': True
                }
                st.success(f"'{c_name}' 정보가 안전하게 저장되었습니다! 리포트 메뉴로 이동하세요.")

    # --- 화면 3: 리포트 결과 보기 ---
    elif menu == "📊 리포트 결과 보기":
        st.title("📊 AI 분석 리포트 결과")
        
        # 저장된 데이터가 없는 경우 경고 표시
        if not st.session_state['company_data'].get('is_saved', False):
            st.warning("⚠️ 입력된 기업 정보가 없습니다. '기업정보 입력' 메뉴에서 먼저 저장해 주세요.")
        else:
            st.write(f"### 분석 대상: **{st.session_state['company_data']['name']}**")
            
            if st.button("🚀 AI 리포트 생성 시작"):
                with st.spinner("AI가 심층 분석 리포트를 작성 중입니다..."):
                    # engine_analysis.py 파일의 분석 함수 실행
                    report = generate_enterprise_report(st.session_state['company_data'])
                    st.divider()
                    st.markdown(report)
            
            st.divider()
            # 이 버튼을 클릭해도 session_state는 그대로이므로 데이터는 유지됩니다.
            if st.button("⬅️ 입력 화면으로 돌아가기"):
                st.info("왼쪽 메뉴에서 '📝 기업정보 입력'을 클릭하세요. 기존 데이터는 모두 보존되어 있습니다.")

if __name__ == "__main__":
    main()
