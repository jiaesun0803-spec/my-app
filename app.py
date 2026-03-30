import streamlit as st
import json
import os
import time
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime

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

# --- 금액 변환 및 안전 로직 ---
def safe_int(value):
    try:
        clean_val = str(value).replace(',', '').strip()
        if not clean_val: return 0
        return int(float(clean_val))
    except:
        return 0

def format_kr_currency(value):
    try:
        val = safe_int(value)
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

def format_biz_no(raw_no):
    no = str(raw_no).replace("-", "").strip()
    if len(no) == 10: return f"{no[:3]}-{no[3:5]}-{no[5:]}"
    return raw_no

def format_corp_no(raw_no):
    no = str(raw_no).replace("-", "").strip()
    if len(no) == 13: return f"{no[:6]}-{no[6:]}"
    return raw_no

def get_best_model_name():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # 대표님 계정에서 가장 빠르고 안정적인 모델 우선 선택
        if 'models/gemini-1.5-flash' in available: return 'gemini-1.5-flash'
        if 'models/gemini-pro' in available: return 'gemini-pro'
        if available: return available[0].replace('models/', '')
    except:
        pass
    return 'gemini-1.5-flash'

def clean_html(text): 
    return "\n".join([l.lstrip() for l in text.replace("```html", "").replace("```", "").strip().split("\n")])

if check_password():
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
        score = safe_int(score)
        if score == 0: return "-"
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

    # 포맷팅 콜백 (NameError 방지를 위해 상단 정의)
    def cb_format_biz_no(): st.session_state["in_raw_biz_no"] = format_biz_no(st.session_state.get("in_raw_biz_no", ""))
    def cb_format_corp_no(): st.session_state["in_raw_corp_no"] = format_corp_no(st.session_state.get("in_raw_corp_no", ""))

    # ==========================================
    # 1. 사이드바 (API 설정, 업체관리)
    # ==========================================
    st.sidebar.header("⚙️ AI 엔진 설정")
    if "api_key" not in st.session_state: 
        st.session_state["api_key"] = st.secrets.get("GEMINI_API_KEY", "")
        
    api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
    if st.sidebar.button("💾 API KEY 저장"):
        st.session_state["api_key"] = api_key_input
        st.sidebar.success("✅ API 키가 저장되었습니다.")
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
                st.session_state["view_mode"] = "INPUT"
                st.rerun()
    with col_s2:
        if st.button("🔄 초기화", use_container_width=True):
            # 모든 입력값 및 리포트 캐시 삭제
            keys_to_clear = [k for k in st.session_state.keys() if k.startswith("in_") or k in ["permanent_data", "generated_report", "generated_matching", "kosme_result_html", "semas_result_html"]]
            for k in keys_to_clear:
                del st.session_state[k]
            st.session_state["view_mode"] = "INPUT"
            st.cache_data.clear()
            st.rerun()

    # 탭 변경 및 데이터 백업 로직
    def change_mode(mode):
        if st.session_state.get("view_mode", "INPUT") == "INPUT":
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = mode
        st.session_state.pop("generated_report", None)
        st.session_state.pop("generated_matching", None)

    st.sidebar.markdown("---")
    st.sidebar.header("🚀 빠른 리포트 생성")
    
    if st.sidebar.button("📊 1. AI기업분석리포트", use_container_width=True):
        if st.session_state.get("in_company_name", "").strip():
            change_mode("REPORT"); st.rerun()
        else: st.sidebar.error("🚨 기업명을 입력해주세요.")
        
    if st.sidebar.button("💡 2. AI 정책자금 매칭리포트", use_container_width=True):
        if st.session_state.get("in_company_name", "").strip():
            change_mode("MATCHING"); st.rerun()
        else: st.sidebar.error("🚨 기업명을 입력해주세요.")
        
    if st.sidebar.button("📝 3. 기관별 융자/사업계획서", use_container_width=True):
        if st.session_state.get("in_company_name", "").strip():
            change_mode("PLAN"); st.rerun()
        
    if st.sidebar.button("📑 4. AI 사업계획서", use_container_width=True):
        if st.session_state.get("in_company_name", "").strip():
            change_mode("FULL_PLAN"); st.rerun()

    # ==========================================
    # 2. 메인 UI 및 리포트 렌더링
    # ==========================================
    if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

    st.title("📊 AI 컨설팅 대시보드")
    t1, t2, t3, t4 = st.columns(4)
    with t1: 
        if st.button("📊 AI기업분석리포트", key="top_1", use_container_width=True, type="primary"):
            if st.session_state.get("in_company_name", "").strip(): change_mode("REPORT"); st.rerun()
            else: st.error("🚨 기업명을 입력해주세요.")
    with t2: 
        if st.button("💡 AI 정책자금 매칭리포트", key="top_2", use_container_width=True, type="primary"):
            if st.session_state.get("in_company_name", "").strip(): change_mode("MATCHING"); st.rerun()
            else: st.error("🚨 기업명을 입력해주세요.")
    with t3: 
        if st.button("📝 기관별 융자/사업계획서", key="top_3", use_container_width=True, type="primary"):
            if st.session_state.get("in_company_name", "").strip(): change_mode("PLAN"); st.rerun()
            else: st.error("🚨 기업명을 입력해주세요.")
    with t4: 
        if st.button("📑 AI 사업계획서", key="top_4", use_container_width=True, type="primary"):
            if st.session_state.get("in_company_name", "").strip(): change_mode("FULL_PLAN"); st.rerun()
            
    st.markdown("<hr style='margin-top:0; margin-bottom:20px;'>", unsafe_allow_html=True)

    # 리포트 공통 데이터 추출
    d = st.session_state.get("permanent_data", {})
    c_name = d.get('in_company_name', '미입력').strip()
    biz_type = d.get('in_biz_type', '미입력')
    c_ind = d.get('in_industry', '미입력')
    rep_name = d.get('in_rep_name', '미입력')
    biz_no = format_biz_no(d.get('in_raw_biz_no', '미입력'))
    corp_no = format_corp_no(d.get('in_raw_corp_no', ''))
    address = d.get('in_biz_addr', '미입력')
    req_fund = format_kr_currency(d.get('in_req_amount', 0))
    item = d.get('in_item_desc', '미입력')
    s_cur = format_kr_currency(d.get('in_sales_current', 0))

    # ---------------------------------------------------------
    # [모드 A: 1. AI기업분석리포트]
    # ---------------------------------------------------------
    if st.session_state["view_mode"] == "REPORT":
        if st.button("⬅️ 입력 화면으로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items(): st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"; st.rerun()
        
        st.subheader(f"📋 AI기업분석리포트: {c_name}")
        
        try:
            if "generated_report" not in st.session_state:
                with st.status("🚀기업분석리포트는 생성중입니다", expanded=True):
                    model = genai.GenerativeModel(get_best_model_name())
                    prompt = f"전문 경영컨설턴트로서 {c_name} 기업에 대한 분석 리포트를 HTML 형식으로 상세히 작성해줘. 업종: {c_ind}, 아이템: {item}."
                    response = model.generate_content(prompt)
                    st.session_state["generated_report"] = clean_html(response.text)
            
            st.markdown(st.session_state["generated_report"], unsafe_allow_html=True)
            st.download_button("📥 리포트 다운로드", st.session_state["generated_report"], f"{c_name}_분석리포트.html", "text/html")
        except Exception as e:
            st.error(f"❌ 생성 중 오류 발생: {str(e)}")

    # ---------------------------------------------------------
    # [모드 B: 2. AI 정책자금 매칭리포트]
    # ---------------------------------------------------------
    elif st.session_state["view_mode"] == "MATCHING":
        if st.button("⬅️ 입력 화면으로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items(): st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"; st.rerun()
        
        st.subheader(f"🎯 AI 정책자금 매칭리포트: {c_name}")
        
        try:
            if "generated_matching" not in st.session_state:
                with st.status("🚀전년도 매출 기준으로 심사를 진행 중입니다", expanded=True):
                    model = genai.GenerativeModel(get_best_model_name())
                    prompt = f"정책자금 전문가로서 {c_name}의 매출 {s_cur} 및 조건에 맞는 자금을 1~4순위로 추천해줘. HTML 형식으로 답변해줘."
                    response = model.generate_content(prompt)
                    st.session_state["generated_matching"] = clean_html(response.text)
            
            st.markdown(st.session_state["generated_matching"], unsafe_allow_html=True)
            st.download_button("📥 매칭리포트 다운로드", st.session_state["generated_matching"], f"{c_name}_매칭리포트.html", "text/html")
        except Exception as e:
            st.error(f"❌ 매칭 중 오류 발생: {str(e)}")

    # ---------------------------------------------------------
    # [모드 C: 3. 기관별 융자/사업계획서]
    # ---------------------------------------------------------
    elif st.session_state["view_mode"] == "PLAN":
        if st.button("⬅️ 입력 화면으로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items(): st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"; st.rerun()
            
        st.title("📝 기관별 융자/사업계획서 자동 생성")
        tabs = st.tabs(["1. 중소벤처기업진흥공단", "2. 소상공인시장진흥공단"])
        
        with tabs[0]:
            st.markdown("#### 🏢 중진공 융자/사업계획서")
            if st.button("🚀 중진공 서식 생성", use_container_width=True):
                with st.status("🚀 서식 작성 중..."):
                    model = genai.GenerativeModel(get_best_model_name())
                    prompt = f"중진공 융자신청서 양식에 맞춰 {c_name}의 사업계획서를 HTML로 작성해줘."
                    st.session_state["kosme_result_html"] = clean_html(model.generate_content(prompt).text)
            if "kosme_result_html" in st.session_state:
                st.markdown(st.session_state["kosme_result_html"], unsafe_allow_html=True)

        with tabs[1]:
            st.markdown("#### 🏪 소진공 융자/사업계획서")
            semas_fund = st.selectbox("💡 소진공 자금종류 (대분류)", ["혁신성장촉진자금", "상생성장지원자금", "일시적경영애로자금", "재도전특별자금"])
            if st.button("🚀 소진공 서식 생성", use_container_width=True):
                with st.status("🚀 소진공 서식 렌더링 중..."):
                    model = genai.GenerativeModel(get_best_model_name())
                    prompt = f"소진공 {semas_fund} 신청을 위한 사업계획서를 HTML로 작성해줘."
                    st.session_state["semas_result_html"] = clean_html(model.generate_content(prompt).text)
            if "semas_result_html" in st.session_state:
                st.markdown(st.session_state["semas_result_html"], unsafe_allow_html=True)

    elif st.session_state["view_mode"] == "FULL_PLAN":
        if st.button("⬅️ 입력 화면으로 돌아가기"):
            st.session_state["view_mode"] = "INPUT"; st.rerun()
        st.title("📑 AI 사업계획서 (마스터)")
        st.info("준비 중인 메뉴입니다.")

    # ---------------------------------------------------------
    # [입력 화면 (메인 대시보드)]
    # ---------------------------------------------------------
    else:
        st.header("1. 기업현황")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("기업명", key="in_company_name")
            st.text_input("사업자번호", key="in_raw_biz_no", on_change=cb_format_biz_no)
            biz_type = st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
            if biz_type == "법인": st.text_input("법인등록번호", key="in_raw_corp_no", on_change=cb_format_corp_no)
        with c2:
            st.text_input("사업개시일", placeholder="2020.01.01", key="in_start_date")
            st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
            st.number_input("상시근로자수(명)", value=0, step=1, key="in_employee_count")
            ls = st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
            if ls == "임대":
                lc1, lc2 = st.columns(2)
                with lc1: st.number_input("보증금(만원)", value=0, key="in_lease_deposit")
                with lc2: st.number_input("월임대료(만원)", value=0, key="in_lease_rent")
        with c3:
            st.text_input("전화번호", key="in_biz_tel")
            has_add = st.radio("추가사업장현황", ["무", "유"], horizontal=True, key="in_has_additional_biz")
            if has_add == "유": st.text_input("추가 사업장 정보", key="in_additional_biz_addr")
            st.text_input("사업장 주소", key="in_biz_addr")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("2. 대표자 정보")
        r1, r2, r3 = st.columns(3)
        with r1:
            st.text_input("대표자명", key="in_rep_name")
            st.text_input("생년월일", key="in_rep_dob")
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

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("3. 신용 및 연체 정보")
        cr1, cr2 = st.columns(2)
        with cr1:
            cc1, cc2 = st.columns(2)
            with cc1: st.radio("세금체납", ["무", "유"], horizontal=True, key="in_tax_status")
            with cc2: st.radio("금융연체", ["무", "유"], horizontal=True, key="in_fin_status")
            sc1, sc2 = st.columns(2)
            with sc1: kcb = st.number_input("KCB 점수", value=0, key="in_kcb_score")
            with sc2: nice = st.number_input("NICE 점수", value=0, key="in_nice_score")
        with cr2:
            st.info(f"#### 🏆 등급 판정 결과\n\n* **KCB:** {get_credit_grade(kcb, 'KCB')}등급\n* **NICE:** {get_credit_grade(nice, 'NICE')}등급")

        st.header("4. 재무현황")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.number_input("금년 매출(만원)", value=0, key="in_sales_current")
        with m2: st.number_input("25년도 매출합계(만원)", value=0, key="in_sales_2025")
        with m3: st.number_input("24년도 매출합계(만원)", value=0, key="in_sales_2024")
        with m4: st.number_input("23년도 매출합계(만원)", value=0, key="in_sales_2023")

        st.header("5. 기대출현황")
        d1, d2, d3, d4 = st.columns(4)
        with d1: st.number_input("중진공(만원)", value=0, key="in_debt_kosme")
        with d2: st.number_input("소진공(만원)", value=0, key="in_debt_semas")
        with d3: st.number_input("신보재단(만원)", value=0, key="in_debt_koreg")
        with d4: st.number_input("신용보증기금(만원)", value=0, key="in_debt_kodit")

        st.header("6. 필요자금")
        p1, p2, p3 = st.columns([1, 1, 2])
        with p1: st.selectbox("자금구분", ["운전자금", "시설자금"], key="in_fund_type")
        with p2: st.number_input("필요자금액(만원)", value=0, key="in_req_amount")
        with p3: st.text_input("자금사용용도", key="in_fund_purpose")

        st.header("7. 인증현황")
        ac1, ac2, ac3, ac4 = st.columns(4)
        with ac1: st.checkbox("소상공인확인서", key="in_chk_1"); st.checkbox("창업확인서", key="in_chk_2")
        with ac2: st.checkbox("여성기업확인서", key="in_chk_3"); st.checkbox("이노비즈", key="in_chk_4")
        with ac3: st.checkbox("벤처인증", key="in_chk_6"); st.checkbox("뿌리기업확인서", key="in_chk_7")
        with ac4: st.checkbox("ISO인증", key="in_chk_10"); st.checkbox("HACCP인증", key="in_chk_11")

        st.header("8. 특허정보")
        pat_col1, pat_col2 = st.columns(2)
        with pat_col1:
            has_pat = st.radio("특허 보유여부", ["무", "유"], horizontal=True, key="in_has_patent")
            if has_pat == "유":
                st.text_input("특허출원 (건)", key="in_pat_apply")
                st.text_input("특허등록 (건)", key="in_pat_reg")
        with pat_col2:
            buy_pat = st.radio("특허매입예정", ["무", "유"], horizontal=True, key="in_buy_patent")
            if buy_pat == "유":
                st.text_input("희망특허 명칭", key="in_buy_pat_desc")
                st.number_input("예상금액(만원)", value=0, key="in_buy_pat_amount")

        st.header("9. 비즈니스 정보")
        st.text_area("아이템", key="in_item_desc")
        st.text_input("제품생산공정도", placeholder="원물 입고 -> 세척 -> 조리 -> 포장", key="in_process_desc")
        st.text_area("판매루트", key="in_sales_route")
        st.text_area("시장현황", key="in_market_status")
        st.text_area("차별화", key="in_diff_point")
        st.text_area("앞으로의 계획", key="in_future_plan")

        st.success("✅ 세팅 완료! 좌측 사이드바 버튼을 클릭해 리포트를 생성하세요.")
