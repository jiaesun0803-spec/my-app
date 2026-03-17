import streamlit as st
import json
import os
import time
import pandas as pd
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

if check_password():
    # --- 파일 관리 및 신용등급 로직 ---
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
    # 1. 사이드바 (API 설정 및 업체관리)
    # ==========================================
    st.sidebar.header("⚙️ AI 엔진 설정")
    if "api_key" not in st.session_state: st.session_state["api_key"] = ""
    api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
    if st.sidebar.button("💾 API 키 적용"):
        st.session_state["api_key"] = api_key_input
        st.sidebar.success("✅ API 키 적용 완료!")
        st.rerun()

    if st.session_state["api_key"]:
        genai.configure(api_key=st.session_state["api_key"])

    st.sidebar.markdown("---")
    st.sidebar.header("📂 업체 관리")
    db = load_db()
    if st.sidebar.button("💾 현재 정보 저장", use_container_width=True):
        c_name = st.session_state.get("in_company_name", "").strip()
        if c_name:
            # 현재 화면의 in_ 데이터를 영구 저장
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
    # 3가지 탭 복원 완료
    if st.sidebar.button("📊 1. 기업분석리포트 생성", use_container_width=True):
        # [핵심] 화면 넘어가기 전에 데이터 유실 방지를 위해 강제 복사!
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
            # [핵심] 돌아갈 때 저장해둔 데이터를 다시 화면(session_state)에 뿌려줌 (증발 방지)
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        # 유실 방지된 데이터 불러오기
        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력')
        
        st.title("📋 시각화 기반 AI 기업분석 리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")
        
        # 상단 요약 대시보드 (입력값이 잘 넘어왔는지 확인용)
        st.markdown("""<hr style="height:3px;border:none;color:#174EA6;background-color:#174EA6;" />""", unsafe_allow_html=True)
        col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
        col_sum1.metric("25년 예상매출", f"{d.get('in_sales_2025', 0):,} 만원")
        col_sum2.metric("필요자금액", f"{d.get('in_req_amount', 0):,} 만원")
        col_sum3.metric("KCB 신용점수", f"{d.get('in_kcb_score', 0)} 점")
        col_sum4.metric("NICE 신용점수", f"{d.get('in_nice_score', 0)} 점")
        st.markdown("""<hr style="height:3px;border:none;color:#174EA6;background-color:#174EA6;" />""", unsafe_allow_html=True)

        if not st.session_state["api_key"]:
            st.error("⚠️ 좌측 사이드바에 API 키를 입력하고 [적용]을 눌러주세요.")
        else:
            try:
                with st.status("🚀 AI 전문가가 시각화 리포트를 생성 중입니다...", expanded=True) as status:
                    st.write("📍 연결 가능한 AI 모델 탐색 중...")
                    
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
                    
                    st.write("📍 대시보드 입력 데이터 100% 동기화 중...")
                    
                    c_ind = d.get('in_industry', '미입력')
                    s_23 = d.get('in_sales_2023', 0)
                    s_24 = d.get('in_sales_2024', 0)
                    s_25 = d.get('in_sales_2025', 0)
                    kcb_s = d.get('in_kcb_score', 0)
                    nice_s = d.get('in_nice_score', 0)
                    item = d.get('in_item_desc', '미입력')
                    market = d.get('in_market_status', '미입력')
                    diff = d.get('in_diff_point', '미입력')
                    req_fund = d.get('in_req_amount', 0)
                    kosme = d.get('in_debt_kosme', 0)
                    semas = d.get('in_debt_semas', 0)
                    koreg = d.get('in_debt_koreg', 0)
                    
                    # [핵심] 입력값을 무조건 사용하고 시각적으로 표현하도록 멱살 잡는 프롬프트
                    prompt = f"""
                    당신은 20년 경력의 중소기업 경영컨설턴트이자 파워포인트(PPT) 디자인 전문가입니다.
                    아래 [대시보드 실제 데이터]를 **절대적으로 100% 반영**하고, 부족한 정보는 최신 외부 시장 자료로 채워 리포트를 작성하세요.
                    
                    [대시보드 실제 데이터 - 이 수치들을 반드시 리포트 본문에 명시할 것!]
                    - 기업명: {c_name} / 업종: {c_ind}
                    - 매출액: 23년 {s_23}만원 ➡️ 24년 {s_24}만원 ➡️ 25년 {s_25}만원
                    - 신용점수: KCB {kcb_s}점, NICE {nice_s}점
                    - 기대출: 중진공({kosme}만), 소진공({semas}만), 신용보증재단({koreg}만)
                    - 비즈니스 아이템: {item}
                    - 시장현황: {market}
                    - 차별화 포인트: {diff}
                    - 필요자금: {req_fund}만원
                    
                    [작성 규칙 - 매우 중요!!!]
                    1. 글씨만 빽빽한 산문체는 절대 금지! PPT 슬라이드처럼 한눈에 들어오게 시각적으로 구성하세요.
                    2. 도형, 화살표(➡️, 📈, 🚀, 🎯, 📊, 🟢, 🔹), 표(| | |)를 적극 활용하여 디자인하세요.
                    3. 입력된 숫자는 무조건 리포트에 직접 언급하며 분석하세요. (예: "24년 매출 {s_24}만원 대비...")
                    4. 각 항목의 핵심 메시지는 굵은 글씨(** **)와 블릿 포인트(-)로 강조하세요.
                    
                    [작성 항목]
                    1. 기업현황분석 (매출/기대출/신용 점수 분석)
                    2. SWOT분석 (반드시 깔끔한 2x2 마크다운 표 형태)
                    3. 시장현황 및 경쟁력 (외부 데이터 참고)
                    4. 핵심경쟁력 분석 ({item} 및 {diff} 집중 조명)
                    5. 정책자금 추천 (해당 업종 및 {req_fund}만원 한도에 맞는 기관명/금액/사유 - 표 형태 권장)
                    6. 추천 인증 및 교육 (벤처, 이노비즈 등 한도 확대용)
                    7. 자금 사용계획 ({req_fund}만원 기준 상세 분배안)
                    8. 매출 1년 전망 (향후 12개월 상승 시나리오)
                    9. 성장비전 및 AI 컨설턴트 최종 코멘트
                    """
                    
                    st.write("📍 표, 도형, 그래프를 활용한 전문 보고서 생성 중...")
                    response = model.generate_content(prompt)
                    status.update(label="✅ 분석 및 시각화 보고서 생성 완료!", state="complete")
                
                # 결과 출력
                st.markdown(response.text, unsafe_allow_html=True)
                
                # [강력한 시각화 추가] Plotly를 이용한 아름다운 이중 차트
                st.divider()
                st.subheader("📊 [첨부] 연도별 매출 성장 트렌드 분석")
                
                fig = go.Figure()
                # 막대 그래프
                fig.add_trace(go.Bar(
                    x=['2023년', '2024년', '2025년(예상)'],
                    y=[s_23, s_24, s_25],
                    name='매출액',
                    marker_color=['#B0BEC5', '#90CAF9', '#1E88E5'],
                    text=[f"{s_23:,}만", f"{s_24:,}만", f"{s_25:,}만"],
                    textposition='auto'
                ))
                # 꺾은선 추세선
                fig.add_trace(go.Scatter(
                    x=['2023년', '2024년', '2025년(예상)'],
                    y=[s_23, s_24, s_25],
                    name='성장 곡선',
                    mode='lines+markers',
                    line=dict(color='#FF5252', width=3),
                    marker=dict(size=10, color='#FF5252')
                ))
                fig.update_layout(
                    title="📈 3개년 매출 추이 및 가속도",
                    xaxis_title="연도",
                    yaxis_title="매출액 (만원)",
                    template="plotly_white",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
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
                # 입력화면에서도 버튼 누를 때 강제 저장!
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
            st.radio("사업장 임대여부", ["임대", "자가"], horizontal=True, key="in_lease_status")
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
            with sc1: kcb = st.number_input("KCB 점수", 0, 1000, 800, key="in_kcb_score")
            with sc2: nice = st.number_input("NICE 점수", 0, 1000, 800, key="in_nice_score")
        with cr2:
            st.info(f"#### 🏆 등급 판정 결과\n\n* **KCB (올크레딧):** {get_credit_grade(kcb, 'KCB')}등급\n* **NICE (나이스):** {get_credit_grade(nice, 'NICE')}등급")

        st.markdown("<br>", unsafe_allow_html=True)

        # 4. 재무 현황
        st.header("4. 재무현황")
        m1, m2, m3 = st.columns(3)
        with m1: st.number_input("23년 매출(만원)", key="in_sales_2023")
        with m2: st.number_input("24년 매출(만원)", key="in_sales_2024")
        with m3: st.number_input("25년 매출(만원)", key="in_sales_2025")

        st.markdown("<br>", unsafe_allow_html=True)

        # 5. 기대출현황
        st.header("5. 기대출현황")
        d1, d2, d3, d4 = st.columns(4)
        with d1: st.number_input("중진공", key="in_debt_kosme")
        with d2: st.number_input("소진공", key="in_debt_semas")
        with d3: st.number_input("신용보증재단", key="in_debt_koreg")
        with d4: st.number_input("신용보증기금", key="in_debt_kodit")
        d5, d6, d7, d8 = st.columns(4)
        with d5: st.number_input("기술보증기금", key="in_debt_kibo")
        with d6: st.number_input("기타", key="in_debt_etc")
        with d7: st.number_input("신용대출", key="in_debt_credit")
        with d8: st.number_input("담보대출", key="in_debt_coll")

        st.markdown("<br>", unsafe_allow_html=True)

        # 6. 필요자금
        st.header("6. 필요자금")
        p1, p2, p3 = st.columns([1, 1, 2])
        with p1: st.selectbox("자금구분", ["운전자금", "시설자금"], key="in_fund_type")
        with p2: st.number_input("필요자금액(만원)", key="in_req_amount")
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
        st.success("✅ 세팅 완료! 좌측에 API 키 적용하고 상단의 [1. 기업분석리포트 생성] 눌러보자고!")
