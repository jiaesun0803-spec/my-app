# =========================================================
# AI 컨설팅 시스템 통합 안정 버전
# (기업명 유지 오류 + 리포트 이동 오류 해결)
# =========================================================

import streamlit as st
import json
import os


# =========================================================
# 기본 파일 설정
# =========================================================

DATA_FILE = "companies_data.json"


# =========================================================
# 데이터 로드 / 저장
# =========================================================

def load_companies():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_companies(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# =========================================================
# 세션 초기화
# =========================================================

if "company_list" not in st.session_state:
    st.session_state.company_list = load_companies()

if "view_mode" not in st.session_state:
    st.session_state.view_mode = "INPUT"

if "active_company" not in st.session_state:
    st.session_state.active_company = ""

if "selected_company_name" not in st.session_state:
    st.session_state.selected_company_name = ""


# =========================================================
# 입력 데이터 기본값
# =========================================================

DEFAULT_INPUTS = {
    "in_company_name": "",
    "in_industry": "",
    "in_rep_name": "",
    "in_sales_cur": 0,
    "in_kcb_score": 0,
    "in_nice_score": 0,
}


for key in DEFAULT_INPUTS:
    if key not in st.session_state:
        st.session_state[key] = DEFAULT_INPUTS[key]


# =========================================================
# 기업 데이터 가져오기
# =========================================================

def get_current_company_data():
    return {
        k: st.session_state.get(k, DEFAULT_INPUTS[k])
        for k in DEFAULT_INPUTS
    }


# =========================================================
# 기업 데이터 적용
# =========================================================

def apply_company_data(name, data):

    merged = DEFAULT_INPUTS.copy()
    merged.update(data)

    for k in merged:
        st.session_state[k] = merged[k]

    st.session_state.active_company = name
    st.session_state.selected_company_name = name


# =========================================================
# 정책자금 점수 계산
# =========================================================

def calc_policy_score(data):

    score = 50

    if data["in_kcb_score"] > 800:
        score += 20

    if data["in_sales_cur"] > 10000:
        score += 20

    return score


# =========================================================
# 보증 확률 계산
# =========================================================

def calc_guarantee_prob(data):

    score = 40

    if data["in_nice_score"] > 800:
        score += 25

    if data["in_sales_cur"] > 10000:
        score += 20

    return score


# =========================================================
# 사이드바 업체 관리
# =========================================================

st.sidebar.header("업체 관리")

company_names = list(st.session_state.company_list.keys())

if company_names:

    selected = st.sidebar.selectbox(
        "업체 선택",
        company_names,
        index=0
    )

    if st.sidebar.button("불러오기"):

        apply_company_data(
            selected,
            st.session_state.company_list[selected]
        )

        st.rerun()

    if st.sidebar.button("삭제"):

        del st.session_state.company_list[selected]

        save_companies(st.session_state.company_list)

        st.session_state.active_company = ""
        st.session_state.selected_company_name = ""

        st.rerun()


# =========================================================
# 상단 UI
# =========================================================

st.title("AI 컨설팅 대시보드")


if st.session_state.active_company:

    st.info(
        f"현재 진행중 업체: {st.session_state.active_company}"
    )


col1, col2, col3, col4 = st.columns(4)

if col1.button("기업진단 리포트"):
    st.session_state.view_mode = "REPORT"
    st.rerun()

if col2.button("정책자금 매칭 리포트"):
    st.session_state.view_mode = "MATCHING"
    st.rerun()

if col3.button("기관별 사업계획서"):
    st.session_state.view_mode = "PLAN"
    st.rerun()

if col4.button("AI 사업계획서"):
    st.session_state.view_mode = "AI"
    st.rerun()


# =========================================================
# 입력 화면
# =========================================================

if st.session_state.view_mode == "INPUT":

    st.text_input("기업명", key="in_company_name")

    st.text_input("업종", key="in_industry")

    st.text_input("대표자명", key="in_rep_name")

    st.number_input("매출", key="in_sales_cur")

    st.number_input("KCB", key="in_kcb_score")

    st.number_input("NICE", key="in_nice_score")


    if st.button("저장"):

        name = st.session_state.in_company_name

        st.session_state.company_list[name] = \
            get_current_company_data()

        save_companies(st.session_state.company_list)

        st.session_state.active_company = name

        st.success("저장 완료")


# =========================================================
# 리포트 화면
# =========================================================

else:

    if st.button("입력 화면으로 돌아가기"):

        st.session_state.selected_company_name = \
            st.session_state.get("active_company", "")

        st.session_state.view_mode = "INPUT"

        st.rerun()


    current_data = get_current_company_data()

    company_name = (

        current_data.get("in_company_name", "")

        or st.session_state.get("active_company", "")

    )


    if not company_name:

        st.warning("기업명을 먼저 입력하세요")

        st.stop()


    policy_score = calc_policy_score(current_data)

    guarantee_prob = calc_guarantee_prob(current_data)


    st.header("기업진단 리포트")

    st.write("기업명:", company_name)

    st.metric("정책자금 점수", policy_score)

    st.metric("보증 승인 확률", f"{guarantee_prob}%")
