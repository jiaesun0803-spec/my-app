import streamlit as st
import json
import os
import time
import pandas as pd
import numpy as np
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

if check_password():
    # --- 파일 관리 (업체 DB) ---
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
    # 1. 사이드바 (API 설정, 업체관리)
    # ==========================================
    st.sidebar.header("⚙️ AI 엔진 설정")
    if "api_key" not in st.session_state: 
        st.session_state["api_key"] = st.secrets.get("GEMINI_API_KEY", "")
        
    api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
    if st.sidebar.button("💾 임시 적용 (클라우드 설정 권장)"):
        st.session_state["api_key"] = api_key_input
        st.sidebar.success("✅ 이번 접속 동안 API 키가 유지됩니다.")
        time.sleep(1)
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
                st.rerun()
    with col_s2:
        if st.button("🔄 초기화", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("in_"): del st.session_state[k]
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🚀 빠른 리포트 생성")
    if st.sidebar.button("📊 1. 기업분석리포트 생성", use_container_width=True):
        st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = "REPORT"
        st.rerun()
    if st.sidebar.button("💡 2. 정책자금 매칭 리포트", use_container_width=True):
        st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = "MATCHING"
        st.rerun()
    if st.sidebar.button("📝 3. 사업계획서 생성", use_container_width=True):
        st.sidebar.info("개발 중인 기능입니다.")

    # ==========================================
    # 2. 화면 모드 제어 (리포트 vs 대시보드)
    # ==========================================
    if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
    if "permanent_data" not in st.session_state: st.session_state["permanent_data"] = {}

    # ---------------------------------------------------------
    # [모드 A: 기존 1. 기업분석리포트]
    # ---------------------------------------------------------
    if st.session_state["view_mode"] == "REPORT":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력').strip()
        
        st.title("📋 시각화 기반 AI 기업분석 리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")
        
        if not st.session_state["api_key"]:
            st.error("⚠️ 좌측 사이드바에 API 키를 입력하거나, 서버 설정에 키를 등록해주세요.")
        else:
            try:
                with st.status("🚀 잼(Jam)이 시각화 리포트를 생성 중입니다...", expanded=True) as status:
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
                    
                    c_ind = d.get('in_industry', '미입력')
                    rep_name = d.get('in_rep_name', '미입력')
                    biz_no = d.get('in_raw_biz_no', '미입력')
                    corp_no = d.get('in_raw_corp_no', '')
                    corp_text = f" ({corp_no})" if corp_no else ""
                    address = d.get('in_biz_addr', '미입력')
                    
                    lease_status = d.get('in_lease_status', '자가')
                    lease_text = "[임대]" if lease_status == '임대' else "[자가]"
                    
                    s_cur = format_kr_currency(d.get('in_sales_current', 0))
                    s_25 = format_kr_currency(d.get('in_sales_2025', 0))
                    s_24 = format_kr_currency(d.get('in_sales_2024', 0))
                    s_23 = format_kr_currency(d.get('in_sales_2023', 0))
                    
                    fund_type = d.get('in_fund_type', '운전자금')
                    req_fund = format_kr_currency(d.get('in_req_amount', 0))
                    
                    item = d.get('in_item_desc', '미입력')
                    market = d.get('in_market_status', '미입력')
                    diff = d.get('in_diff_point', '미입력')
                    
                    val_cur = safe_int(d.get('in_sales_current', 0))
                    if val_cur <= 0: val_cur = 1000
                    start_val = val_cur / 12
                    end_val = start_val * 1.5
                    step = (end_val - start_val) / 11
                    monthly_vals = [int(start_val + step * i) for i in range(12)]
                    monthly_labels = [f"{i}월" for i in range(1, 13)]

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=monthly_labels, y=monthly_vals, mode='lines+markers+text',
                        text=[format_kr_currency(v) for v in monthly_vals], textposition="top center",
                        textfont=dict(size=11), line=dict(color='#1E88E5', width=4, shape='spline'),
                        marker=dict(size=10, color='#FF5252', line=dict(width=2, color='white'))
                    ))
                    fig.update_layout(
                        title="📈 향후 1년간 월별 예상 매출 상승 곡선", xaxis_title="진행 월", yaxis_title="예상 매출액",
                        xaxis=dict(tickangle=0, showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
                        template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                    )

                    prompt = f"""
                    당신은 20년 경력의 중소기업 경영컨설턴트입니다. 
                    마크다운과 HTML 태그를 사용하여 아래 양식과 서식 규칙을 **반드시 100% 똑같이** 지켜서 출력하세요.

                    [데이터 및 시간 인지 규칙]
                    - 현재 시점은 2026년 시작 단계입니다. 23년({s_23}), 24년({s_24}), 25년({s_25}) 매출은 과거 실적입니다. 과거의 부진은 언급하지 마세요.

                    [작성 규칙]
                    1. 어투/문체: 모든 문장 끝은 '~있음', '~가능', '~함' 등 명사형(음/슴체)으로 마무리하세요.
                    2. 제목 크기: 모든 카테고리 제목은 '##' (Heading 2)를 사용하세요.
                    3. 마침표 줄바꿈: 문장이 마침표('.')로 끝날 때마다 반드시 줄바꿈 문자(<br>)를 추가하세요.
                    4. 3, 4, 5, 6, 9번 항목은 반드시 문장 앞에 '-' 기호를 붙여 개조식으로 요약하세요.

                    [기업 정보]
                    - 기업명: {c_name} / 대표자: {rep_name} / 업종: {c_ind}
                    - 사업자번호: {biz_no}{corp_text} / 주소: {address}
                    - 아이템: {item} / 시장현황: {market} / 차별화: {diff}
                    - 신청자금: {req_fund} ({fund_type})

                    [출력 양식]
                    
                    ## 1. 기업현황분석
                    <table style="width:100%; border-collapse: collapse; font-size: 1.1em; background-color:#f8f9fa; border-radius:15px; overflow:hidden; margin-bottom:15px;">
                      <tr>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0; width:15%;"><b>기업명</b></td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0; width:35%;">{c_name}</td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0; width:15%;"><b>대표자명</b></td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0; width:35%;">{rep_name}</td>
                      </tr>
                      <tr>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0;"><b>업종</b></td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0;">{c_ind}</td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0;"><b>사업자번호</b></td>
                        <td style="padding:15px; border-bottom:1px solid #e0e0e0;">{biz_no}{corp_text}</td>
                      </tr>
                      <tr>
                        <td style="padding:15px;"><b>사업장 주소</b></td>
                        <td colspan="3" style="padding:15px;">{address} <span style="color:#1565c0; font-weight:bold;">{lease_text}</span></td>
                      </tr>
                    </table>
                    (매출 숫자는 기재하지 말고 향후 긍정적인 기대감을 심어주는 코멘트 명사형 작성, 마침표 뒤 줄바꿈)

                    ## 2. SWOT 분석
                    <table style="width:100%; text-align:center; border-collapse: separate; border-spacing: 10px;">
                      <tr>
                        <td style="background-color:#e3f2fd; padding:20px; border-radius:15px; width:50%;"><b>S (강점)</b><br>내용작성(음/슴체)</td>
                        <td style="background-color:#ffebee; padding:20px; border-radius:15px; width:50%;"><b>W (약점)</b><br>내용작성(음/슴체)</td>
                      </tr>
                      <tr>
                        <td style="background-color:#e8f5e9; padding:20px; border-radius:15px;"><b>O (기회)</b><br>내용작성(음/슴체)</td>
                        <td style="background-color:#fff3e0; padding:20px; border-radius:15px;"><b>T (위협)</b><br>내용작성(음/슴체)</td>
                      </tr>
                    </table>

                    ## 3. 시장현황 및 경쟁력
                    <div style="display:flex; gap:15px; margin-bottom:10px;">
                      <div style="flex:1; background-color:#f3e5f5; padding:20px; border-radius:15px;"><b>📊 시장 현황</b><br><br>(- 기호 시작, 명사형 종결, 마침표 뒤 줄바꿈)</div>
                      <div style="flex:1; background-color:#e8eaf6; padding:20px; border-radius:15px;"><b>⚔️ 경쟁 상황</b><br><br>(- 기호 시작, 명사형 종결, 마침표 뒤 줄바꿈)</div>
                    </div>

                    ## 4. 핵심경쟁력분석
                    <div style="display:flex; gap:15px; margin-bottom:10px; text-align:center;">
                      <div style="flex:1; border:1px solid #e0e0e0; border-radius:15px; overflow:hidden;">
                        <div style="background-color:#e0f7fa; padding:15px; font-weight:bold;">포인트 1 (키워드)</div>
                        <div style="padding:15px; font-size:0.9em; text-align:left;">(- 기호 시작, 명사형 종결, 마침표 줄바꿈)</div>
                      </div>
                      <div style="flex:1; border:1px solid #e0e0e0; border-radius:15px; overflow:hidden;">
                        <div style="background-color:#e0f7fa; padding:15px; font-weight:bold;">포인트 2 (키워드)</div>
                        <div style="padding:15px; font-size:0.9em; text-align:left;">(- 기호 시작, 명사형 종결, 마침표 줄바꿈)</div>
                      </div>
                      <div style="flex:1; border:1px solid #e0e0e0; border-radius:15px; overflow:hidden;">
                        <div style="background-color:#e0f7fa; padding:15px; font-weight:bold;">포인트 3 (키워드)</div>
                        <div style="padding:15px; font-size:0.9em; text-align:left;">(- 기호 시작, 명사형 종결, 마침표 줄바꿈)</div>
                      </div>
                    </div>

                    ## 5. 정책자금 추천
                    1. <b style="font-size:1.2em; color:#1565c0;">[기관명] / {req_fund}</b>
                       <div style="margin-top:5px; margin-bottom:15px; color:#555;">- (추천사유 개조식 명사형 종결)</div>
                    (2번, 3번도 동일 양식)

                    ## 6. 추천 인증 및 교육
                    <div style="background-color:#fff8e1; padding:20px; border-radius:15px; margin-bottom:10px;">
                      (- 기호 시작, 전략 명사형 작성, 마침표 뒤 줄바꿈)
                    </div>

                    ## 7. 자금 사용계획 (총 신청자금: {req_fund})
                    <table style="width:100%; border-collapse: collapse; text-align:left;">
                     <tr style="background-color:#eceff1;">
                       <th style="padding:15px; border:1px solid #ccc; border-radius:10px 0 0 0;">구분 ({fund_type})</th>
                       <th style="padding:15px; border:1px solid #ccc;">상세 사용계획</th>
                       <th style="padding:15px; border:1px solid #ccc; border-radius:0 10px 0 0;">배정 금액</th>
                     </tr>
                     <tr>
                       <td style="padding:15px; border:1px solid #ccc; font-weight:bold;">(세부항목 1)</td>
                       <td style="padding:15px; border:1px solid #ccc; font-size:0.85em;">- (명사형 작성)</td>
                       <td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0;">(금액)</td>
                     </tr>
                     <tr>
                       <td style="padding:15px; border:1px solid #ccc; font-weight:bold;">(세부항목 2)</td>
                       <td style="padding:15px; border:1px solid #ccc; font-size:0.85em;">- (명사형 작성)</td>
                       <td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0;">(금액)</td>
                     </tr>
                    </table>

                    ## 8. 매출 1년 전망
                    <div style="display:flex; justify-content:space-between; align-items:stretch; text-align:center; flex-wrap:wrap; gap:10px;">
                      <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; flex:1;">
                        <div style="font-size:1.4em; font-weight:bold; color:#1565c0;">1단계 (1~3개월)</div>
                        <div style="margin:15px 0; font-size:0.95em; text-align:left;">(상세하고 풍성한 진행 내용, 명사형)</div>
                        <div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">목표: OOO만원</div>
                      </div>
                      <div style="font-size:2em; align-self:center;">➡️</div>
                      <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; flex:1;">
                        <div style="font-size:1.4em; font-weight:bold; color:#1565c0;">2단계 (4~6개월)</div>
                        <div style="margin:15px 0; font-size:0.95em; text-align:left;">(상세하고 풍성한 진행 내용, 명사형)</div>
                        <div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">목표: OOO만원</div>
                      </div>
                      <div style="font-size:2em; align-self:center;">➡️</div>
                      <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; flex:1;">
                        <div style="font-size:1.4em; font-weight:bold; color:#1565c0;">3단계 (7~9개월)</div>
                        <div style="margin:15px 0; font-size:0.95em; text-align:left;">(상세하고 풍성한 진행 내용, 명사형)</div>
                        <div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">목표: OOO만원</div>
                      </div>
                      <div style="font-size:2em; align-self:center;">➡️</div>
                      <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; flex:1;">
                        <div style="font-size:1.4em; font-weight:bold; color:#1565c0;">4단계 (10~12개월)</div>
                        <div style="margin:15px 0; font-size:0.95em; text-align:left;">(상세하고 풍성한 진행 내용, 명사형)</div>
                        <div style="color:#d32f2f; font-weight:bold; font-size:1.1em;">최종목표: OOO만원</div>
                      </div>
                    </div>
                    
                    [GRAPH_INSERT_POINT]

                    ## 9. 성장비전 및 AI 컨설턴트 코멘트
                    <div style="display:flex; gap:15px; text-align:center; margin-bottom:20px;">
                       <div style="flex:1; padding:20px; background-color:#e8f5e9; border-radius:15px;"><b>🌱 단기 비전</b><br><br><div style="text-align:left;">- (명사형 요약)<br>- (명사형 요약)</div></div>
                       <div style="flex:1; padding:20px; background-color:#fff3e0; border-radius:15px;"><b>🚀 중기 비전</b><br><br><div style="text-align:left;">- (명사형 요약)<br>- (명사형 요약)</div></div>
                       <div style="flex:1; padding:20px; background-color:#ffebee; border-radius:15px;"><b>👑 장기 비전</b><br><br><div style="text-align:left;">- (명사형 요약)<br>- (명사형 요약)</div></div>
                    </div>
                    
                    <div style="background-color:#eeeeee; border-left:5px solid #1565c0; padding:20px; border-radius:15px; margin-top:15px;">
                      <b>💡 AI 컨설턴트 최종 코멘트:</b><br>
                      (마침표 뒤 줄바꿈, 명사형 종결)
                    </div>
                    """
                    
                    response = model.generate_content(prompt)
                    status.update(label="✅ 기업분석리포트 생성 완료!", state="complete")
                
                try:
                    response_text = response.text
                except:
                    response_text = ""

                if "[GRAPH_INSERT_POINT]" in response_text:
                    parts = response_text.partition("[GRAPH_INSERT_POINT]")
                    st.markdown(parts[0], unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown("<br><br>", unsafe_allow_html=True) 
                    st.markdown(parts[2], unsafe_allow_html=True)
                else:
                    st.markdown(response_text, unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)

                st.balloons()
                
                st.divider()
                st.subheader("💾 리포트 저장 (PDF 권장)")
                safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
                if not safe_file_name: safe_file_name = "업체"
                
                html_export = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>{c_name} 기업분석리포트</title>
                    <style>
                        * {{ box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                        body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; padding: 40px; line-height: 1.6; color: #333; max-width: 1000px; margin: 0 auto; font-size: 16px; }}
                        h1 {{ color: #111; text-align: center; margin-bottom: 40px; font-size: 32px; }}
                        h2 {{ color: #174EA6; border-bottom: 2px solid #174EA6; padding-bottom: 8px; margin-top: 40px; font-size: 26px; font-weight: bold; }}
                        .print-btn {{ display: block; width: 100%; padding: 15px; background-color: #174EA6; color: white; font-size: 18px; font-weight: bold; border: none; border-radius: 10px; cursor: pointer; margin-bottom: 30px; text-align: center; }}
                        .print-btn:hover {{ background-color: #123C85; }}
                        
                        @media print {{ 
                            .print-btn {{ display: none; }} 
                            @page {{ size: A4; margin: 10mm; }}
                            /* 글자 크기 강제 축소 제거. 화면 비율 그대로 유지하면서 A4에 맞게 전체 zoom만 조절 */
                            body {{ padding: 0; zoom: 0.8; }} 
                            div {{ page-break-inside: avoid; }}
                        }}
                    </style>
                </head>
                <body>
                    <button class="print-btn" onclick="window.print()">🖨️ 클릭하여 PDF로 저장하기</button>
                    <h1>📋 AI 기업분석 결과보고서: {c_name}</h1>
                    <hr style="margin-bottom: 30px;">
                    {response_text.replace('[GRAPH_INSERT_POINT]', '<div style="padding:15px; margin: 15px 0; background:#e3f2fd; text-align:center; border-radius:10px; font-weight:bold; color:#1565c0; border: 1px dashed #1565c0;">[📈 1년 매출 상승 곡선 차트는 웹 대시보드 시스템에서 확인 가능합니다]</div>')}
                </body>
                </html>
                """
                st.download_button(label="📥 기업분석리포트 다운로드", data=html_export, file_name=f"{safe_file_name}_기업분석리포트.html", mime="text/html", type="primary")

            except Exception as e:
                st.error(f"❌ 분석 중 오류 발생: {str(e)}")

    # ---------------------------------------------------------
    # [모드 B: 신규 2. 정책자금 매칭 리포트]
    # ---------------------------------------------------------
    elif st.session_state["view_mode"] == "MATCHING":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력').strip()
        
        st.title("🎯 AI 정책자금 최적화 매칭 리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")
        
        if not st.session_state["api_key"]:
            st.error("⚠️ 좌측 사이드바에 API 키를 입력하거나, 서버 설정에 키를 등록해주세요.")
        else:
            try:
                with st.status("🚀 잼(Jam)이 기관별 컷오프 및 한도 구간을 심사 중입니다...", expanded=True) as status:
                    try:
                        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    except Exception as e:
                        raise Exception(f"API 키 권한 오류입니다. (상세: {e})")

                    if 'models/gemini-1.5-flash' in available_models: target_model = 'gemini-1.5-flash'
                    elif 'models/gemini-1.5-pro' in available_models: target_model = 'gemini-1.5-pro'
                    elif 'models/gemini-pro' in available_models: target_model = 'gemini-pro'
                    elif len(available_models) > 0: target_model = available_models[0].replace('models/', '')
                    else: raise Exception("사용 가능한 생성형 모델이 없습니다.")

                    model = genai.GenerativeModel(target_model)
                    
                    # 1. 컷오프 및 계산용 데이터 추출
                    tax_status = d.get('in_tax_status', '무')
                    fin_status = d.get('in_fin_status', '무')
                    
                    kibo_debt = safe_int(d.get('in_debt_kibo', 0))
                    kodit_debt = safe_int(d.get('in_debt_kodit', 0))
                    
                    # 기대출 합계 로직
                    total_debt_val = sum([
                        safe_int(d.get('in_debt_kosme', 0)),
                        safe_int(d.get('in_debt_semas', 0)),
                        safe_int(d.get('in_debt_koreg', 0)),
                        safe_int(d.get('in_debt_kodit', 0)),
                        safe_int(d.get('in_debt_kibo', 0)),
                        safe_int(d.get('in_debt_etc', 0)),
                        safe_int(d.get('in_debt_credit', 0)),
                        safe_int(d.get('in_debt_coll', 0))
                    ])
                    total_debt = format_kr_currency(total_debt_val)
                    s_cur = format_kr_currency(d.get('in_sales_current', 0))
                    
                    c_ind = d.get('in_industry', '미입력')
                    item = d.get('in_item_desc', '미입력')
                    nice_score = safe_int(d.get('in_nice_score', 0))
                    fund_type = d.get('in_fund_type', '운전자금')
                    fund_req = format_kr_currency(d.get('in_req_amount', 0))
                    
                    has_cert = d.get('in_chk_6', False) or d.get('in_chk_4', False) or d.get('in_chk_10', False)
                    cert_status = "보유 (벤처/이노비즈 등)" if has_cert else "미보유"
                    
                    # 2. 한도 산출 공식 및 기관별 규칙 탑재 프롬프트 + [필요자금 추가 반영]
                    prompt = f"""
                    당신은 20년 경력의 중소기업 정책자금 전문 경영컨설턴트입니다. 
                    아래 [입력 데이터]와 대표님이 직접 작성하신 [절대 매칭 비법 DB]를 100% 반영하여, 마크다운과 HTML 태그를 활용해 매칭 리포트를 출력하세요.

                    [작성 규칙]
                    1. 어투: 모든 문장은 '~있음', '~가능', '~함', '~불가함' 등 명사형(음/슴체)으로 간결하게 작성하세요. (서술형 절대 금지)
                    2. 마침표 줄바꿈: 문장이 마침표('.')로 끝날 때마다 반드시 줄바꿈 문자(<br>)를 추가하세요.
                    3. 추천 확대: 총 4개의 맞춤 정책자금을 선별하여, 1~2순위는 '우선순위', 3~4순위는 '후순위(플랜 B)'로 제시하세요.

                    [절대 매칭 비법 DB - 이 기준을 바탕으로 분석할 것!]
                    1. 💎 최우선 고려: 금리가 저렴한 "직접대출 (중진공, 소진공)"을 우선 검토할 것!
                    - [중진공(직접대출)]: 기술력 있는 중소기업. **최소 신청 금액은 5,000만 원 이상**부터 시작.
                    - [소진공(직접대출)]: 5인 미만 소상공인. 상품에 따라 최대한도가 3천만, 7천만, 1억, 2억으로 설정되어 있음. ('신용취약소상공인자금'은 반드시 NICE 839점 이하일 때만 추천할 것!)
                    2. 🛡️ 보증서 발급 기관 (기보, 신보, 지역신보)
                    - [보증기관 우선순위 룰 - 매우 중요!]: '기보' 또는 '신보'를 '지역신보'보다 우선(1~2순위) 배치하고, 지역신보는 후순위(3~4순위)로 미루세요. (지역신보 선사용 시 기보/신보 막힘 방지)
                    - [신보/기보 한도 룰]: 기보와 신보는 **최소 1억 원 이상부터** 지원 가능. (희망자금이나 남은 한도가 1억 미만이면 추천 불가). 신보(KODIT) 예상 한도는 '제조업=금년 매출의 1/4', '기타=매출의 1/6~1/10' 계산 후 **총 기대출({total_debt}) 차감**하여 제시.
                    - [지역신보 한도 룰]: 지역신용보증재단은 **최대 2억 원까지만** 지원 가능.
                    3. 🚫 컷오프 (절대 불가) 기준 적용
                    - 세금 체납, 금융 연체가 있으면 1~4순위 추천 대신 연체 해결 전략만 강하게 제시할 것.
                    - 기보 대출 잔액이 있으면 신보 추천 금지. 신보 대출 잔액이 있으면 기보 추천 금지.

                    [입력 데이터]
                    - 기업명: {c_name} / 업종: {c_ind} / 아이템: {item}
                    - 세금체납: {tax_status} / 금융연체: {fin_status} / NICE 점수: {nice_score}점
                    - 기술/벤처 인증: {cert_status} 
                    - 금년 매출: {s_cur} / 총 기대출 합계: {total_debt} / 희망자금: {fund_req}

                    [출력 양식]
                    ## 1. 기업 스펙 진단 요약
                    <div style="background-color:#f8f9fa; padding:15px; border-radius:15px; border:1px solid #e0e0e0; margin-bottom:15px;">
                      <b>기업명:</b> {c_name} &nbsp;|&nbsp; <b>업종:</b> {c_ind} <br>
                      <b>NICE 점수:</b> {nice_score}점 &nbsp;|&nbsp; <b>기술/벤처 인증:</b> {cert_status} <br>
                      <b>금년매출:</b> {s_cur} &nbsp;|&nbsp; <b>총 기대출:</b> <span style="color:red;">{total_debt}</span> &nbsp;|&nbsp; <b style="font-size:1.15em;">필요자금: {fund_req}</b>
                    </div>
                    (데이터를 바탕으로 정책자금 합격 가능성에 대한 팩트폭격 및 스펙 평가 3~4줄 명사형 작성, 마침표 뒤 줄바꿈)

                    ## 2. 우선순위 추천 정책자금 (1~2순위)
                    <div style="background-color:#e8f5e9; padding:15px; border-radius:15px; border-left:5px solid #2e7d32; margin-bottom:10px;">
                      <b style="font-size:1.1em; color:#2e7d32;">🥇 1순위: [추천 기관명] / [세부 자금명] / 예상 한도 (매출 및 기대출 팩트 반영)</b><br><br>
                      - (추천 사유 및 합격 꿀팁 명사형 종결, 마침표 뒤 줄바꿈)
                    </div>
                    <div style="background-color:#e8f5e9; padding:15px; border-radius:15px; border-left:5px solid #2e7d32; margin-bottom:15px;">
                      <b style="font-size:1.1em; color:#2e7d32;">🥈 2순위: [추천 기관명] / [세부 자금명] / 예상 한도</b><br><br>
                      - (추천 사유 및 합격 꿀팁 명사형 종결, 마침표 뒤 줄바꿈)
                    </div>

                    ## 3. 후순위 추천 (플랜 B - 3~4순위)
                    <div style="background-color:#fff3e0; padding:15px; border-radius:15px; border-left:5px solid #ef6c00; margin-bottom:10px;">
                      <b style="font-size:1.1em; color:#ef6c00;">🥉 3순위: [추천 기관명] / [세부 자금명] / 예상 한도</b><br><br>
                      - (추천 사유 및 접근 전략 명사형 종결, 마침표 뒤 줄바꿈)
                    </div>
                    <div style="background-color:#fff3e0; padding:15px; border-radius:15px; border-left:5px solid #ef6c00; margin-bottom:15px;">
                      <b style="font-size:1.1em; color:#ef6c00;">🏅 4순위: [추천 기관명] / [세부 자금명] / 예상 한도</b><br><br>
                      - (추천 사유 및 접근 전략 명사형 종결, 마침표 뒤 줄바꿈)
                    </div>

                    ## 4. 심사 전 필수 체크리스트 및 보완 가이드
                    <div style="background-color:#ffebee; border-left:5px solid #d32f2f; padding:15px; border-radius:15px; margin-top:10px;">
                      <b style="font-size:1.1em; color:#c62828;">🚨 AI 컨설턴트 보완 조언:</b><br><br>
                      - (세금 완납, 신용 관리, 기대출 한도 등 기업 상황 조언. 명사형 종결, 마침표 뒤 줄바꿈)
                    </div>
                    """
                    
                    response = model.generate_content(prompt)
                    status.update(label="✅ 잼(Jam)의 최적화 매칭 리포트 생성 완료!", state="complete")
                
                st.markdown(response.text, unsafe_allow_html=True)
                st.balloons()
                
                # --- [다운로드 버튼 기능] ---
                st.divider()
                st.subheader("💾 매칭 리포트 저장 (PDF 권장)")
                
                safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
                if not safe_file_name: safe_file_name = "업체"
                
                # [수정] 폰트 축소를 해제하여 화면에서 보던 글자 크기 그대로 인쇄되게 유지
                html_export = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>{c_name} 정책자금 매칭 리포트</title>
                    <style>
                        * {{ box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                        body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; padding: 40px; line-height: 1.6; color: #333; max-width: 1000px; margin: 0 auto; font-size: 16px; }}
                        h1 {{ color: #111; text-align: center; margin-bottom: 40px; font-size: 32px; }}
                        h2 {{ color: #174EA6; border-bottom: 2px solid #174EA6; padding-bottom: 8px; margin-top: 40px; font-size: 26px; font-weight: bold; }}
                        .print-btn {{ display: block; width: 100%; padding: 15px; background-color: #174EA6; color: white; font-size: 18px; font-weight: bold; border: none; border-radius: 10px; cursor: pointer; margin-bottom: 30px; text-align: center; }}
                        .print-btn:hover {{ background-color: #123C85; }}
                        
                        @media print {{ 
                            .print-btn {{ display: none; }} 
                            @page {{ size: A4; margin: 10mm; }}
                            /* 글자 크기 강제 축소 제거. 화면 비율 그대로 유지하면서 A4에 맞게 전체 zoom만 조절 */
                            body {{ padding: 0; zoom: 0.8; }} 
                            div {{ page-break-inside: avoid; }}
                        }}
                    </style>
                </head>
                <body>
                    <button class="print-btn" onclick="window.print()">🖨️ 클릭하여 PDF로 저장하기</button>
                    <h1>🎯 AI 정책자금 최적화 매칭 리포트: {c_name}</h1>
                    <hr style="margin-bottom: 20px;">
                    {response.text}
                </body>
                </html>
                """
                st.download_button(label="📥 매칭 리포트 다운로드", data=html_export, file_name=f"{safe_file_name}_매칭리포트.html", mime="text/html", type="primary")

            except Exception as e:
                st.error(f"❌ 분석 중 오류 발생: {str(e)}")

    # --- [입력 화면 (대시보드)] ---
    else:
        st.title("📊 AI 컨설팅 대시보드")
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            if st.button("📊 1. 기업분석리포트 생성", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "REPORT"
                st.rerun()
        with col_t2: 
            if st.button("💡 2. 정책자금 매칭 리포트", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "MATCHING"
                st.rerun()
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
            
            lease_status = st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
            if lease_status == "임대":
                lc1, lc2 = st.columns(2)
                with lc1: st.number_input("보증금(만원)", value=0, step=1, key="in_lease_deposit")
                with lc2: st.number_input("월임대료(만원)", value=0, step=1, key="in_lease_rent")
                
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
            with sc1: kcb = st.number_input("KCB 점수", value=0, step=1, key="in_kcb_score")
            with sc2: nice = st.number_input("NICE 점수", value=0, step=1, key="in_nice_score")
        with cr2:
            st.info(f"#### 🏆 등급 판정 결과\n\n* **KCB (올크레딧):** {get_credit_grade(kcb, 'KCB')}등급\n* **NICE (나이스):** {get_credit_grade(nice, 'NICE')}등급")

        st.markdown("<br>", unsafe_allow_html=True)

        # 4. 재무 현황
        st.header("4. 재무현황")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.number_input("금년 매출(만원)", value=0, step=1, key="in_sales_current")
        with m2: st.number_input("25년도 매출합계(만원)", value=0, step=1, key="in_sales_2025")
        with m3: st.number_input("24년도 매출합계(만원)", value=0, step=1, key="in_sales_2024")
        with m4: st.number_input("23년도 매출합계(만원)", value=0, step=1, key="in_sales_2023")

        st.markdown("<br>", unsafe_allow_html=True)

        # 5. 기대출현황
        st.header("5. 기대출현황")
        d1, d2, d3, d4 = st.columns(4)
        with d1: st.number_input("중진공(만원)", value=0, step=1, key="in_debt_kosme")
        with d2: st.number_input("소진공(만원)", value=0, step=1, key="in_debt_semas")
        with d3: st.number_input("신용보증재단(만원)", value=0, step=1, key="in_debt_koreg")
        with d4: st.number_input("신용보증기금(만원)", value=0, step=1, key="in_debt_kodit")
        d5, d6, d7, d8 = st.columns(4)
        with d5: st.number_input("기술보증기금(만원)", value=0, step=1, key="in_debt_kibo")
        with d6: st.number_input("기타(만원)", value=0, step=1, key="in_debt_etc")
        with d7: st.number_input("신용대출(만원)", value=0, step=1, key="in_debt_credit")
        with d8: st.number_input("담보대출(만원)", value=0, step=1, key="in_debt_coll")

        st.markdown("<br>", unsafe_allow_html=True)

        # 6. 필요자금
        st.header("6. 필요자금")
        p1, p2, p3 = st.columns([1, 1, 2])
        with p1: st.selectbox("자금구분", ["운전자금", "시설자금"], key="in_fund_type")
        with p2: st.number_input("필요자금액(만원)", value=0, step=1, key="in_req_amount")
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
        st.success("✅ 세팅 완료! 좌측에 API 키 저장하시고 상단의 [1/2 리포트 생성] 버튼을 클릭해 주십시오.")
