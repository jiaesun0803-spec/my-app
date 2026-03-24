import streamlit as st
import time
import json
import os
import io
import re
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 0. 기본 설정
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

# ==========================================
# 유틸리티 함수
# ==========================================
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
        if uk > 0 and man > 0: return f"{uk}억 {man:,}만원"
        elif uk > 0: return f"{uk}억원"
        else: return f"{man:,}만원"
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
    else:
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
# 업체 DB
# ==========================================
DB_FILE = "company_db.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_db(db_data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db_data, f, ensure_ascii=False, indent=4)

# ==========================================
# HTML → 텍스트 파싱 (PDF/PPT용)
# ==========================================
def html_to_plain(html_text):
    """HTML 태그 제거, br→줄바꿈, 특수문자 처리"""
    text = html_text
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'&lt;br&gt;', '\n', text)
    text = re.sub(r'&bull;', '•', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def extract_sections(html_text):
    """HTML에서 섹션별로 내용 추출"""
    sections = {}
    # h2 태그 기준으로 섹션 분리
    pattern = r'<h2[^>]*>(.*?)</h2>(.*?)(?=<h2|$)'
    matches = re.findall(pattern, html_text, re.DOTALL)
    for title, content in matches:
        title_clean = re.sub(r'<[^>]+>', '', title).strip()
        content_clean = html_to_plain(content).strip()
        sections[title_clean] = content_clean
    return sections

# ==========================================
# PDF 생성 (내용 반영)
# ==========================================
def generate_pdf(c_name, response_text, d):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether
        from reportlab.pdfbase import pdfmetrics

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=20*mm, leftMargin=20*mm,
            topMargin=20*mm, bottomMargin=20*mm
        )

        BLUE = colors.HexColor('#174EA6')
        LIGHT_BLUE = colors.HexColor('#E8F0FE')
        DARK = colors.HexColor('#333333')
        TEAL = colors.HexColor('#00838F')

        styles = getSampleStyleSheet()

        style_title = ParagraphStyle('mytitle',
            fontSize=20, fontName='Helvetica-Bold',
            textColor=BLUE, spaceAfter=6, alignment=1)

        style_subtitle = ParagraphStyle('mysubtitle',
            fontSize=13, fontName='Helvetica',
            textColor=DARK, spaceAfter=12, alignment=1)

        style_h2 = ParagraphStyle('myh2',
            fontSize=14, fontName='Helvetica-Bold',
            textColor=BLUE, spaceBefore=16, spaceAfter=6)

        style_body = ParagraphStyle('mybody',
            fontSize=10, fontName='Helvetica',
            textColor=DARK, spaceAfter=4, leading=16)

        style_bullet = ParagraphStyle('mybullet',
            fontSize=10, fontName='Helvetica',
            textColor=DARK, spaceAfter=3, leading=15,
            leftIndent=12)

        story = []

        # 표지
        story.append(Spacer(1, 20*mm))
        story.append(Paragraph("AI 기업분석 결과보고서", style_title))
        story.append(Paragraph(c_name, style_subtitle))
        story.append(Spacer(1, 4*mm))
        story.append(HRFlowable(width="100%", thickness=2, color=BLUE))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(f"작성일: {datetime.now().strftime('%Y년 %m월 %d일')}", style_body))
        story.append(Spacer(1, 10*mm))

        # 기업 기본정보 요약
        info_lines = [
            f"기업명: {d.get('in_company_name','미입력')}  |  대표자: {d.get('in_rep_name','미입력')}",
            f"업종: {d.get('in_industry','미입력')}  |  사업자번호: {format_biz_no(d.get('in_raw_biz_no','미입력'))}",
            f"사업장 주소: {d.get('in_biz_addr','미입력')}",
            f"필요자금: {format_kr_currency(d.get('in_req_amount',0))}  |  자금구분: {d.get('in_fund_type','운전자금')}",
        ]
        for line in info_lines:
            story.append(Paragraph(line, style_body))
        story.append(Spacer(1, 6*mm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CCCCCC')))
        story.append(Spacer(1, 6*mm))

        # 섹션별 내용 파싱
        sections = extract_sections(response_text)

        for sec_title, sec_content in sections.items():
            if not sec_content.strip():
                continue

            story.append(Paragraph(sec_title, style_h2))
            story.append(HRFlowable(width="100%", thickness=1, color=BLUE))
            story.append(Spacer(1, 3*mm))

            # 내용을 줄 단위로 처리
            lines = sec_content.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 2*mm))
                    continue
                # 줄바꿈 (마침표 기준)
                sentences = re.split(r'(?<=\.)\s+', line)
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    if sent.startswith('•'):
                        story.append(Paragraph(sent, style_bullet))
                    else:
                        story.append(Paragraph(sent, style_body))

            story.append(Spacer(1, 4*mm))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        st.error(f"PDF 생성 오류: {e}")
        return None

# ==========================================
# PPTX 생성 (내용 반영)
# ==========================================
def generate_pptx(c_name, response_text, d):
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN

        prs = Presentation()
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)

        BLUE = RGBColor(0x17, 0x4E, 0xA6)
        WHITE = RGBColor(0xFF, 0xFF, 0xFF)
        DARK = RGBColor(0x33, 0x33, 0x33)
        LIGHT = RGBColor(0xF0, 0xF4, 0xFF)
        TEAL = RGBColor(0x00, 0x83, 0x8F)
        RED = RGBColor(0xD3, 0x2F, 0x2F)

        def blank_slide():
            return prs.slides.add_slide(prs.slide_layouts[6])

        def set_bg(slide, r, g, b):
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = RGBColor(r, g, b)

        def add_rect(slide, l, t, w, h, r, g, b, alpha=None):
            from pptx.util import Emu
            shape = slide.shapes.add_shape(
                1, Inches(l), Inches(t), Inches(w), Inches(h))
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(r, g, b)
            shape.line.fill.background()
            return shape

        def add_text(slide, text, l, t, w, h, size=12, bold=False,
                     color=None, align=PP_ALIGN.LEFT, wrap=True):
            if color is None:
                color = DARK
            txBox = slide.shapes.add_textbox(
                Inches(l), Inches(t), Inches(w), Inches(h))
            tf = txBox.text_frame
            tf.word_wrap = wrap

            # 줄바꿈 처리: 마침표 뒤 줄바꿈
            lines = text.split('\n')
            first = True
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # 마침표 기준 분리
                sentences = re.split(r'(?<=\.)\s+', line)
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    if first:
                        p = tf.paragraphs[0]
                        first = False
                    else:
                        p = tf.add_paragraph()
                    p.alignment = align
                    run = p.add_run()
                    run.text = sent
                    run.font.size = Pt(size)
                    run.font.bold = bold
                    run.font.color.rgb = color
            return txBox

        # 섹션 파싱
        sections = extract_sections(response_text)
        sec_list = list(sections.items())

        # ===== 슬라이드 1: 표지 =====
        s1 = blank_slide()
        set_bg(s1, 0x17, 0x4E, 0xA6)
        add_rect(s1, 0, 5.8, 13.33, 1.7, 0x0D, 0x3A, 0x7A)
        add_text(s1, "AI 기업분석 결과보고서", 1, 1.5, 11.33, 1.2,
                 size=36, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(s1, c_name, 1, 2.9, 11.33, 0.9,
                 size=28, bold=True, color=RGBColor(0xAD,0xD8,0xFF), align=PP_ALIGN.CENTER)
        add_text(s1, f"작성일: {datetime.now().strftime('%Y년 %m월 %d일')}",
                 1, 3.9, 11.33, 0.5,
                 size=14, color=RGBColor(0xCC,0xDD,0xFF), align=PP_ALIGN.CENTER)
        add_text(s1, "본 보고서는 AI 컨설팅 시스템에 의해 자동 생성되었습니다.",
                 1, 6.1, 11.33, 0.5,
                 size=11, color=RGBColor(0xAA,0xBB,0xDD), align=PP_ALIGN.CENTER)

        # ===== 슬라이드 2: 기업현황 =====
        s2 = blank_slide()
        set_bg(s2, 0xFF, 0xFF, 0xFF)
        add_rect(s2, 0, 0, 13.33, 1.1, 0x17, 0x4E, 0xA6)
        add_text(s2, "기업현황", 0.3, 0.15, 12, 0.8,
                 size=22, bold=True, color=WHITE)

        info_pairs = [
            ("기업명", d.get('in_company_name','미입력')),
            ("대표자명", d.get('in_rep_name','미입력')),
            ("업종", d.get('in_industry','미입력')),
            ("사업개시일", d.get('in_start_date','미입력')),
            ("사업자번호", format_biz_no(d.get('in_raw_biz_no','미입력'))),
            ("필요자금", format_kr_currency(d.get('in_req_amount',0))),
        ]
        for i, (label, val) in enumerate(info_pairs):
            col = i % 2
            row = i // 2
            x = 0.3 + col * 6.55
            y = 1.25 + row * 1.9
            add_rect(s2, x, y, 6.3, 1.6, 0xF0, 0xF4, 0xFF)
            add_text(s2, label, x+0.15, y+0.1, 2.5, 0.4,
                     size=10, bold=True, color=BLUE)
            add_text(s2, str(val), x+0.15, y+0.5, 5.9, 0.9,
                     size=12, color=DARK)

        # ===== 이후 슬라이드: 각 섹션 =====
        SECTION_COLORS = [
            (0xE3, 0xF2, 0xFD), (0xFF, 0xEB, 0xEE),
            (0xE8, 0xF5, 0xE9), (0xFF, 0xF3, 0xE0),
            (0xF3, 0xE5, 0xF5), (0xE0, 0xF7, 0xFA),
            (0xE8, 0xEA, 0xF6),
        ]
        LEFT_COLORS = [
            (0x17, 0x4E, 0xA6), (0xC6, 0x28, 0x28),
            (0x2E, 0x7D, 0x32), (0xE6, 0x5C, 0x00),
            (0x6A, 0x1B, 0x9A), (0x00, 0x83, 0x8F),
            (0x39, 0x49, 0xAB),
        ]

        for idx, (sec_title, sec_content) in enumerate(sec_list):
            if not sec_content.strip():
                continue

            bg_r, bg_g, bg_b = SECTION_COLORS[idx % len(SECTION_COLORS)]
            lc_r, lc_g, lc_b = LEFT_COLORS[idx % len(LEFT_COLORS)]

            slide = blank_slide()
            set_bg(slide, 0xFF, 0xFF, 0xFF)

            # 헤더
            add_rect(slide, 0, 0, 13.33, 1.1, 0x17, 0x4E, 0xA6)
            add_text(slide, sec_title, 0.3, 0.15, 12, 0.8,
                     size=20, bold=True, color=WHITE)

            # 내용을 줄 단위로 분리
            lines = [l.strip() for l in sec_content.split('\n') if l.strip()]

            # 최대 표시 줄 수
            max_lines = 20
            display_lines = lines[:max_lines]

            # 내용 박스 배경
            add_rect(slide, 0.3, 1.2, 12.7, 6.0, bg_r, bg_g, bg_b)
            # 왼쪽 컬러 바
            add_rect(slide, 0.3, 1.2, 0.12, 6.0, lc_r, lc_g, lc_b)

            # 텍스트 내용
            content_text = '\n'.join(display_lines)
            add_text(slide, content_text, 0.55, 1.35, 12.5, 5.7,
                     size=11, color=DARK)

        pptx_buffer = io.BytesIO()
        prs.save(pptx_buffer)
        pptx_buffer.seek(0)
        return pptx_buffer.getvalue()

    except Exception as e:
        st.error(f"PPT 생성 오류: {e}")
        return None

# ==========================================
# 메인 앱
# ==========================================
def show_main_app():

    # ===== 사이드바 =====
    with st.sidebar:
        st.markdown("### 🤖 AI 컨설팅 시스템")
        st.markdown("---")

        st.header("⚙️ AI 엔진 설정")

        # API KEY: 한 번 저장하면 재입력 불필요
        if "api_key" not in st.session_state:
            st.session_state["api_key"] = st.secrets.get("GEMINI_API_KEY", "")

        if st.session_state["api_key"]:
            st.success("✅ API KEY 저장됨")
            genai.configure(api_key=st.session_state["api_key"])
            if st.button("🔄 API KEY 변경", use_container_width=True):
                st.session_state["api_key"] = ""
                st.rerun()
        else:
            api_key_input = st.text_input("Gemini API Key", type="password", placeholder="API 키를 입력하세요")
            if st.button("💾 API KEY 저장", use_container_width=True):
                if api_key_input:
                    st.session_state["api_key"] = api_key_input
                    genai.configure(api_key=api_key_input)
                    st.success("✅ 저장됨!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("API 키를 입력해주세요.")

        st.markdown("---")

        # 업체 관리
        st.header("📂 업체 관리")
        db = load_db()

        if st.button("💾 현재 정보 저장", use_container_width=True):
            c_name = st.session_state.get("in_company_name", "").strip()
            if c_name:
                current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                db[c_name] = current_data
                save_db(db)
                st.success(f"✅ '{c_name}' 저장 완료!")
            else:
                st.warning("기업명을 먼저 입력해주세요.")

        selected_company = st.selectbox("저장된 업체 목록", ["선택 안 함"] + list(db.keys()))
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("📂 불러오기", use_container_width=True):
                if selected_company != "선택 안 함":
                    for k, v in db[selected_company].items():
                        st.session_state[k] = v
                    st.rerun()
        with col_s2:
            if st.button("🔄 초기화", use_container_width=True):
                for k in list(st.session_state.keys()):
                    if k.startswith("in_"): del st.session_state[k]
                st.rerun()

        st.markdown("---")
        st.header("🚀 빠른 리포트 생성")
        if st.button("📊 1. 기업분석리포트 생성", use_container_width=True):
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "REPORT"
            st.rerun()
        if st.button("💡 2. 정책자금 매칭 리포트", use_container_width=True):
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "MATCHING"
            st.rerun()
        if st.button("📝 3. 사업계획서 생성", use_container_width=True):
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "PLAN"
            st.rerun()

    if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
    if "permanent_data" not in st.session_state: st.session_state["permanent_data"] = {}

    # ---------------------------------------------------------
    # [모드 A: 기업분석리포트]
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

        if not st.session_state.get("api_key", ""):
            st.error("⚠️ 좌측 사이드바에 API 키를 입력해주세요.")
        else:
            # 이미 생성된 리포트가 있으면 재사용
            if "report_response_text" in st.session_state and "report_fig" in st.session_state:
                response_text = st.session_state["report_response_text"]
                fig = st.session_state["report_fig"]
                monthly_vals = st.session_state.get("report_monthly_vals", [])

                if "[GRAPH_INSERT_POINT]" in response_text:
                    parts = response_text.partition("[GRAPH_INSERT_POINT]")
                    st.markdown(parts[0], unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown(parts[2], unsafe_allow_html=True)
                else:
                    st.markdown(response_text, unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                try:
                    with st.status("🚀 AI가 리포트를 생성 중입니다...", expanded=True) as status:
                        try:
                            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        except Exception as e:
                            raise Exception(f"API 키 권한 오류: {e}")

                        if 'models/gemini-1.5-flash' in available_models: target_model = 'gemini-1.5-flash'
                        elif 'models/gemini-1.5-pro' in available_models: target_model = 'gemini-1.5-pro'
                        elif 'models/gemini-pro' in available_models: target_model = 'gemini-pro'
                        elif len(available_models) > 0: target_model = available_models[0].replace('models/', '')
                        else: raise Exception("사용 가능한 생성형 모델이 없습니다.")

                        model = genai.GenerativeModel(target_model)

                        c_ind = d.get('in_industry', '미입력')
                        rep_name = d.get('in_rep_name', '미입력')
                        biz_no = format_biz_no(d.get('in_raw_biz_no', '미입력'))
                        corp_no = format_corp_no(d.get('in_raw_corp_no', ''))
                        corp_text = f" (법인: {corp_no})" if corp_no else ""
                        address = d.get('in_biz_addr', '미입력')
                        add_biz_status = d.get('in_has_additional_biz', '무')
                        add_biz_addr = d.get('in_additional_biz_addr', '').strip()
                        if add_biz_status == '유' and add_biz_addr:
                            address += f" / 추가사업장: {add_biz_addr}"
                        fund_type = d.get('in_fund_type', '운전자금')
                        req_fund = format_kr_currency(d.get('in_req_amount', 0))
                        item = d.get('in_item_desc', '미입력')

                        val_cur = safe_int(d.get('in_sales_current', 0))
                        if val_cur <= 0: val_cur = 1000
                        start_val = val_cur / 12
                        end_val = start_val * 1.5
                        monthly_vals = []
                        for i in range(12):
                            progress = i / 11.0
                            linear_part = start_val + (end_val - start_val) * progress
                            wave_part = (end_val - start_val) * 0.15 * np.sin(progress * np.pi * 3.5)
                            monthly_vals.append(int(linear_part + wave_part))
                        monthly_labels = [f"{i}월" for i in range(1, 13)]

                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=monthly_labels, y=monthly_vals, mode='lines+markers+text',
                            text=[format_kr_currency(v) for v in monthly_vals],
                            textposition="top center", textfont=dict(size=11),
                            line=dict(color='#1E88E5', width=4, shape='spline'),
                            marker=dict(size=10, color='#FF5252', line=dict(width=2, color='white'))
                        ))
                        fig.update_layout(
                            title="📈 향후 1년간 월별 예상 매출 상승 곡선",
                            xaxis_title="진행 월", yaxis_title="예상 매출액",
                            xaxis=dict(tickangle=0, showgrid=False),
                            yaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
                            template="plotly_white", margin=dict(l=20, r=20, t=40, b=20),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                        )

                        # ★ 프롬프트: 문체 간결 + 마침표 줄바꿈 + br 없음 + 세로형 레이아웃
                        prompt = f"""
당신은 20년 경력의 중소기업 경영컨설턴트입니다.
아래 규칙을 반드시 지키세요:
1. 문체: '~있음', '~예상됨', '~확인됨' 등 간결체 사용. '~습니다' 금지.
2. 줄바꿈: 문장 끝 마침표(.) 이후 반드시 줄바꿈.
3. <br> 태그 절대 사용 금지.
4. 마크다운(##, **) 절대 금지.
5. 각 항목 3~4문장 이상 상세하게 작성.

[기업 정보]
- 기업명: {c_name} / 대표자: {rep_name} / 업종: {c_ind} / 아이템: {item} / 신청자금: {req_fund}

[출력 양식 - 반드시 아래 HTML 구조 그대로 출력]

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업현황분석</h2>
<table style="width:100%; border-collapse:collapse; font-size:1.1em; background-color:#f8f9fa; border-radius:15px; overflow:hidden; margin-bottom:15px;">
  <tr><td style="padding:15px; border-bottom:1px solid #e0e0e0; width:15%;"><b>기업명</b></td><td style="padding:15px; border-bottom:1px solid #e0e0e0; width:35%;">{c_name}</td><td style="padding:15px; border-bottom:1px solid #e0e0e0; width:15%;"><b>대표자명</b></td><td style="padding:15px; border-bottom:1px solid #e0e0e0; width:35%;">{rep_name}</td></tr>
  <tr><td style="padding:15px; border-bottom:1px solid #e0e0e0;"><b>업종</b></td><td style="padding:15px; border-bottom:1px solid #e0e0e0;">{c_ind}</td><td style="padding:15px; border-bottom:1px solid #e0e0e0;"><b>사업/법인번호</b></td><td style="padding:15px; border-bottom:1px solid #e0e0e0;">{biz_no}{corp_text}</td></tr>
  <tr><td style="padding:15px;"><b>사업장 주소</b></td><td colspan="3" style="padding:15px;">{address}</td></tr>
</table>
<div style="background-color:#EEF2FF; padding:15px; border-radius:10px; margin-bottom:15px; line-height:2.0;">(기업 잠재력 3~4문장. 각 문장 끝에 줄바꿈.)</div>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. SWOT 분석</h2>
<table style="width:100%; table-layout:fixed; border-collapse:separate; border-spacing:15px; margin-bottom:15px;">
  <tr>
    <td style="background-color:#e3f2fd; padding:20px; border-radius:15px; vertical-align:top;"><b style="color:#1565C0;">S (강점)</b><div style="margin-top:10px; line-height:2.0;">(강점 3~4문장. 각 문장 끝 줄바꿈.)</div></td>
    <td style="background-color:#ffebee; padding:20px; border-radius:15px; vertical-align:top;"><b style="color:#C62828;">W (약점)</b><div style="margin-top:10px; line-height:2.0;">(약점 3~4문장. 각 문장 끝 줄바꿈.)</div></td>
  </tr>
  <tr>
    <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; vertical-align:top;"><b style="color:#2E7D32;">O (기회)</b><div style="margin-top:10px; line-height:2.0;">(기회 3~4문장. 각 문장 끝 줄바꿈.)</div></td>
    <td style="background-color:#fff3e0; padding:20px; border-radius:15px; vertical-align:top;"><b style="color:#E65C00;">T (위협)</b><div style="margin-top:10px; line-height:2.0;">(위협 3~4문장. 각 문장 끝 줄바꿈.)</div></td>
  </tr>
</table>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 시장현황 및 경쟁력 비교</h2>
<div style="background-color:#f3e5f5; padding:20px; border-radius:15px; margin-bottom:15px; line-height:2.0;"><b>📊 시장 현황 분석</b><br>(시장 트렌드 3~4문장. 각 문장 끝 줄바꿈.)</div>
<div style="padding:15px; background-color:#fff; border-radius:15px; border:1px solid #e0e0e0;">
  <b>⚔️ 주요 경쟁사 비교 분석표</b>
  <table style="width:100%; border-collapse:collapse; text-align:center; font-size:0.95em; margin-top:10px;">
    <tr style="background-color:#eceff1;"><th style="padding:12px; border:1px solid #ccc;">비교 항목</th><th style="padding:12px; border:1px solid #ccc;">{c_name} (자사)</th><th style="padding:12px; border:1px solid #ccc;">경쟁사 A</th><th style="padding:12px; border:1px solid #ccc;">경쟁사 B</th></tr>
    <tr><td style="padding:12px; border:1px solid #ccc; font-weight:bold;">핵심 타겟</td><td style="padding:12px; border:1px solid #ccc;">(자사 내용)</td><td style="padding:12px; border:1px solid #ccc;">(A 내용)</td><td style="padding:12px; border:1px solid #ccc;">(B 내용)</td></tr>
    <tr><td style="padding:12px; border:1px solid #ccc; font-weight:bold;">차별화 요소</td><td style="padding:12px; border:1px solid #ccc;">(자사 내용)</td><td style="padding:12px; border:1px solid #ccc;">(A 내용)</td><td style="padding:12px; border:1px solid #ccc;">(B 내용)</td></tr>
    <tr><td style="padding:12px; border:1px solid #ccc; font-weight:bold;">예상 점유율</td><td style="padding:12px; border:1px solid #ccc;">(자사 내용)</td><td style="padding:12px; border:1px solid #ccc;">(A 내용)</td><td style="padding:12px; border:1px solid #ccc;">(B 내용)</td></tr>
  </table>
</div>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 핵심경쟁력분석</h2>
<div style="display:flex; flex-direction:column; gap:12px; margin-bottom:15px;">
  <div style="border-left:5px solid #00ACC1; border-radius:10px; background-color:#E0F7FA; padding:20px;">
    <div style="font-weight:bold; color:#00838F; margin-bottom:8px;">포인트 1: (핵심 키워드)</div>
    <div style="line-height:2.0;">(분석 3~4문장. 각 문장 끝 줄바꿈.)</div>
  </div>
  <div style="border-left:5px solid #00ACC1; border-radius:10px; background-color:#E0F7FA; padding:20px;">
    <div style="font-weight:bold; color:#00838F; margin-bottom:8px;">포인트 2: (핵심 키워드)</div>
    <div style="line-height:2.0;">(분석 3~4문장. 각 문장 끝 줄바꿈.)</div>
  </div>
  <div style="border-left:5px solid #00ACC1; border-radius:10px; background-color:#E0F7FA; padding:20px;">
    <div style="font-weight:bold; color:#00838F; margin-bottom:8px;">포인트 3: (핵심 키워드)</div>
    <div style="line-height:2.0;">(분석 3~4문장. 각 문장 끝 줄바꿈.)</div>
  </div>
</div>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">5. 자금 사용계획 (총 신청자금: {req_fund})</h2>
<table style="width:100%; border-collapse:collapse; text-align:left; margin-bottom:15px;">
  <tr style="background-color:#eceff1;"><th style="padding:15px; border:1px solid #ccc; width:20%;">구분 ({fund_type})</th><th style="padding:15px; border:1px solid #ccc; width:60%;">상세 사용계획</th><th style="padding:15px; border:1px solid #ccc; width:20%;">사용예정금액</th></tr>
  <tr><td style="padding:15px; border:1px solid #ccc; font-weight:bold;">(세부항목 1)</td><td style="padding:15px; border:1px solid #ccc; line-height:2.0;">(사용처 2~3문장. 각 문장 끝 줄바꿈.)</td><td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0;">(금액)</td></tr>
  <tr><td style="padding:15px; border:1px solid #ccc; font-weight:bold;">(세부항목 2)</td><td style="padding:15px; border:1px solid #ccc; line-height:2.0;">(사용처 2~3문장. 각 문장 끝 줄바꿈.)</td><td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0;">(금액)</td></tr>
</table>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">6. 매출 1년 전망</h2>
<div style="display:flex; flex-direction:column; gap:12px; margin-bottom:15px;">
  <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; border-left:5px solid #3949AB;">
    <div style="font-size:1.05em; font-weight:bold; color:#1565c0; margin-bottom:8px;">1단계 (도입)</div>
    <div style="line-height:2.0;">(전략 3~4문장. 각 문장 끝 줄바꿈.)</div>
    <div style="color:#d32f2f; font-weight:bold; margin-top:8px;">목표: OOO만원</div>
  </div>
  <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; border-left:5px solid #3949AB;">
    <div style="font-size:1.05em; font-weight:bold; color:#1565c0; margin-bottom:8px;">2단계 (성장)</div>
    <div style="line-height:2.0;">(전략 3~4문장. 각 문장 끝 줄바꿈.)</div>
    <div style="color:#d32f2f; font-weight:bold; margin-top:8px;">목표: OOO만원</div>
  </div>
  <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; border-left:5px solid #3949AB;">
    <div style="font-size:1.05em; font-weight:bold; color:#1565c0; margin-bottom:8px;">3단계 (확장)</div>
    <div style="line-height:2.0;">(전략 3~4문장. 각 문장 끝 줄바꿈.)</div>
    <div style="color:#d32f2f; font-weight:bold; margin-top:8px;">목표: OOO만원</div>
  </div>
  <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; border-left:5px solid #3949AB;">
    <div style="font-size:1.05em; font-weight:bold; color:#1565c0; margin-bottom:8px;">4단계 (안착)</div>
    <div style="line-height:2.0;">(전략 3~4문장. 각 문장 끝 줄바꿈.)</div>
    <div style="color:#d32f2f; font-weight:bold; margin-top:8px;">최종목표: OOO만원</div>
  </div>
</div>

[GRAPH_INSERT_POINT]

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">7. 성장비전 및 AI 컨설턴트 코멘트</h2>
<div style="display:flex; flex-direction:column; gap:12px; margin-bottom:20px;">
  <div style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #388E3C;">
    <b>🌱 단기 비전</b>
    <div style="margin-top:10px; line-height:2.0;">(핵심 비전 3~4문장. 각 문장 끝 줄바꿈.)</div>
  </div>
  <div style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #F57C00;">
    <b>🚀 중기 비전</b>
    <div style="margin-top:10px; line-height:2.0;">(핵심 비전 3~4문장. 각 문장 끝 줄바꿈.)</div>
  </div>
  <div style="background-color:#ffebee; padding:20px; border-radius:15px; border-left:5px solid #C62828;">
    <b>👑 장기 비전</b>
    <div style="margin-top:10px; line-height:2.0;">(핵심 비전 3~4문장. 각 문장 끝 줄바꿈.)</div>
  </div>
</div>
<div style="background-color:#eeeeee; border-left:5px solid #1565c0; padding:25px; border-radius:15px; line-height:2.0;">
  <b>💡 필수 인증 및 특허 확보 조언</b>
  <div style="margin-top:10px;">(인증 조언 3~4문장. 각 문장 끝 줄바꿈.)</div>
  <div style="margin-top:8px;">(지식재산권 전략 3~4문장. 각 문장 끝 줄바꿈.)</div>
</div>
"""
                        response = model.generate_content(prompt)
                        status.update(label="✅ 기업분석리포트 생성 완료!", state="complete")

                    try:
                        response_text = response.text
                    except:
                        response_text = ""

                    # 리포트 내용 세션에 저장 (재사용)
                    st.session_state["report_response_text"] = response_text
                    st.session_state["report_fig"] = fig
                    st.session_state["report_monthly_vals"] = monthly_vals
                    st.session_state["report_d"] = d

                    if "[GRAPH_INSERT_POINT]" in response_text:
                        parts = response_text.partition("[GRAPH_INSERT_POINT]")
                        st.markdown(parts[0], unsafe_allow_html=True)
                        st.plotly_chart(fig, use_container_width=True)
                        st.markdown(parts[2], unsafe_allow_html=True)
                    else:
                        st.markdown(response_text, unsafe_allow_html=True)
                        st.plotly_chart(fig, use_container_width=True)

                    st.balloons()

                except Exception as e:
                    st.error(f"❌ 분석 중 오류 발생: {str(e)}")
                    return

            # ===== 다운로드 섹션 =====
            st.divider()
            st.subheader("💾 리포트 다운로드")
            response_text = st.session_state.get("report_response_text", "")
            report_d = st.session_state.get("report_d", d)
            safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
            if not safe_file_name: safe_file_name = "업체"

            dl1, dl2 = st.columns(2)
            with dl1:
                st.markdown("**📄 PDF 다운로드**")
                if st.button("PDF 생성", use_container_width=True):
                    with st.spinner("PDF 생성 중..."):
                        pdf_data = generate_pdf(c_name, response_text, report_d)
                    if pdf_data:
                        st.download_button(
                            label="📥 PDF 다운로드",
                            data=pdf_data,
                            file_name=f"{safe_file_name}_기업분석.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
            with dl2:
                st.markdown("**📊 PPT 다운로드**")
                if st.button("PPT 생성", use_container_width=True):
                    with st.spinner("PPT 생성 중..."):
                        pptx_data = generate_pptx(c_name, response_text, report_d)
                    if pptx_data:
                        st.download_button(
                            label="📥 PPT 다운로드",
                            data=pptx_data,
                            file_name=f"{safe_file_name}_기업분석.pptx",
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            type="primary",
                            use_container_width=True
                        )

    # ---------------------------------------------------------
    # [모드 B: 정책자금 매칭 리포트]
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

        if not st.session_state.get("api_key", ""):
            st.error("⚠️ 좌측 사이드바에 API 키를 입력해주세요.")
        else:
            try:
                with st.status("🚀 AI가 심사를 진행 중입니다...", expanded=True) as status:
                    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    if 'models/gemini-1.5-flash' in available_models: target_model = 'gemini-1.5-flash'
                    else: target_model = 'gemini-pro'
                    model = genai.GenerativeModel(target_model)

                    total_debt_val = sum([safe_int(d.get(k, 0)) for k in ['in_debt_kosme','in_debt_semas','in_debt_koreg','in_debt_kodit','in_debt_kibo','in_debt_etc','in_debt_credit','in_debt_coll']])
                    total_debt = format_kr_currency(total_debt_val)
                    s_25 = format_kr_currency(safe_int(d.get('in_sales_2025', 0)))
                    c_ind = d.get('in_industry', '미입력')
                    biz_type = d.get('in_biz_type', '개인')
                    nice_score = safe_int(d.get('in_nice_score', 0))
                    req_fund = format_kr_currency(safe_int(d.get('in_req_amount', 0)))
                    cert_status = "보유" if d.get('in_chk_6', False) or d.get('in_chk_4', False) or d.get('in_chk_10', False) else "미보유"
                    biz_years = 0
                    if d.get('in_start_date', '').strip():
                        try: biz_years = max(0, 2026 - int(d.get('in_start_date', '')[:4]))
                        except: pass

                    prompt = f"""당신은 전문 경영컨설턴트입니다.
규칙: 마크다운 금지. 문체는 '~있음','~예상됨' 등 간결체. '~습니다' 금지. 마침표 뒤 줄바꿈. <br> 태그 금지.

[입력] 기업명:{c_name} / 업종:{c_ind} / 전년도매출:{s_25} / 총기대출:{total_debt} / 필요자금:{req_fund}

[출력 양식]
<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업 스펙 진단 요약</h2>
<div style="background-color:#f8f9fa; padding:20px; border-radius:15px; border:1px solid #e0e0e0; margin-bottom:15px;">
  <b>기업명:</b> {c_name} | <b>업종:</b> {c_ind} ({biz_type}) | <b>업력:</b> 약 {biz_years}년
  <b>NICE 점수:</b> {nice_score}점 | <b>인증:</b> {cert_status}
  <b>전년도매출:</b> <span style="color:#1565c0; font-weight:bold;">{s_25}</span> | <b>총 기대출:</b> <span style="color:red;">{total_debt}</span> | <b>필요자금: {req_fund}</b>
</div>
<div style="background-color:#EEF2FF; padding:15px; border-radius:10px; margin-bottom:20px; line-height:2.0;">(2~3문장 진단 요약. 마침표 뒤 줄바꿈.)</div>

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. 우선순위 추천 정책자금</h2>
<table style="width:100%; table-layout:fixed; border-collapse:separate; border-spacing:15px; margin-bottom:15px;">
  <tr>
    <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32; vertical-align:top;"><b style="color:#2e7d32;">🥇 1순위: [기관명] / [자금명] / 예상한도</b><div style="margin-top:10px; line-height:2.0;">(사유 2~3문장. 마침표 뒤 줄바꿈.)</div></td>
    <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32; vertical-align:top;"><b style="color:#2e7d32;">🥈 2순위: [기관명] / [자금명] / 예상한도</b><div style="margin-top:10px; line-height:2.0;">(사유 2~3문장. 마침표 뒤 줄바꿈.)</div></td>
  </tr>
</table>

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 후순위 추천</h2>
<table style="width:100%; table-layout:fixed; border-collapse:separate; border-spacing:15px; margin-bottom:15px;">
  <tr>
    <td style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00; vertical-align:top;"><b style="color:#ef6c00;">🥉 3순위: [기관명] / [자금명] / 예상한도</b><div style="margin-top:10px; line-height:2.0;">(사유 2~3문장. 마침표 뒤 줄바꿈.)</div></td>
    <td style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00; vertical-align:top;"><b style="color:#ef6c00;">🏅 4순위: [기관명] / [자금명] / 예상한도</b><div style="margin-top:10px; line-height:2.0;">(사유 2~3문장. 마침표 뒤 줄바꿈.)</div></td>
  </tr>
</table>

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 보완 가이드</h2>
<div style="background-color:#ffebee; border-left:5px solid #d32f2f; padding:20px; border-radius:15px; line-height:2.0;">
  <b style="color:#c62828;">🚨 보완 조언</b>
  <div style="margin-top:10px;">(전략 2~3문장. 마침표 뒤 줄바꿈.)</div>
</div>"""
                    response = model.generate_content(prompt)
                    status.update(label="✅ 매칭 리포트 생성 완료!", state="complete")

                st.markdown(response.text, unsafe_allow_html=True)
                st.balloons()
                st.divider()
                safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
                if not safe_file_name: safe_file_name = "업체"
                html_export = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{c_name} 매칭리포트</title>
<style>* {{box-sizing:border-box; -webkit-print-color-adjust:exact !important; print-color-adjust:exact !important;}}
body {{font-family:'Malgun Gothic',sans-serif; padding:30px; line-height:1.8; color:#333; max-width:1000px; margin:0 auto; background-color:#fff;}}
.print-btn {{display:block; width:100%; padding:15px; background-color:#174EA6; color:white; font-size:18px; font-weight:bold; border:none; border-radius:10px; cursor:pointer; margin-bottom:30px; text-align:center;}}
@media print {{.print-btn {{display:none;}} @page {{size:A4; margin:10mm;}} body {{padding:0 !important; font-size:13px !important;}}}}</style>
</head><body>
<button class="print-btn" onclick="window.print()">🖨️ 클릭하여 PDF로 저장하기</button>
<h1>🎯 AI 정책자금 매칭 리포트: {c_name}</h1>
{response.text}</body></html>"""
                st.download_button(label="📥 매칭 리포트 다운로드 (HTML)", data=html_export,
                                   file_name=f"{safe_file_name}_매칭리포트.html", mime="text/html", type="primary")

            except Exception as e:
                st.error(f"❌ 분석 중 오류 발생: {str(e)}")

    # ---------------------------------------------------------
    # [모드 C: 사업계획서]
    # ---------------------------------------------------------
    elif st.session_state["view_mode"] == "PLAN":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()

        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name', '미입력').strip()
        rep_name = d.get('in_rep_name', '미입력')
        c_ind = d.get('in_industry', '미입력')
        career = d.get('in_career', '미입력')
        s_25 = format_kr_currency(d.get('in_sales_2025', 0))
        total_debt = format_kr_currency(sum([safe_int(d.get(k, 0)) for k in ['in_debt_kosme','in_debt_semas','in_debt_koreg','in_debt_kodit','in_debt_kibo','in_debt_etc','in_debt_credit','in_debt_coll']]))
        nice_score = d.get('in_nice_score', 0)
        item = d.get('in_item_desc', '미입력')
        market = d.get('in_market_status', '미입력')
        diff = d.get('in_diff_point', '미입력')
        cert_status = "보유" if d.get('in_chk_6', False) or d.get('in_chk_4', False) or d.get('in_chk_10', False) else "미보유"
        req_fund = format_kr_currency(d.get('in_req_amount', 0))
        fund_type = d.get('in_fund_type', '운전자금')
        fund_purpose = d.get('in_fund_purpose', '미입력')
        biz_years = 0
        if d.get('in_start_date', '').strip():
            try: biz_years = max(0, 2026 - int(d.get('in_start_date', '')[:4]))
            except: pass

        data_summary = f"""[기업] {c_name} / {rep_name} / {c_ind} / 업력{biz_years}년 / {career}
[재무] 전년매출:{s_25} / 기대출:{total_debt} / NICE:{nice_score}점
[비즈니스] {item} / {market} / {diff} / 인증:{cert_status}
[자금] {req_fund} ({fund_type} / {fund_purpose})"""

        prompts = {
            "kosme_plan": f"중진공 심사역. '사업계획서' 초안. 포커스: 고용창출, 기술성, 미래성장성.\n{data_summary}",
            "kosme_loan": f"중진공 심사역. '융자신청서' 초안. 포커스: 재무분석, 자금조달 및 상환계획.\n{data_summary}",
            "semas_plan": f"소진공 심사역. '사업계획서' 초안. 포커스: 사업생존가능성, 지역상권 영업전략.\n{data_summary}",
            "semas_loan": f"소진공 심사역. '융자신청서' 초안. 포커스: 매출대비 고정비 및 상환능력 증빙.\n{data_summary}",
            "kodit_plan": f"신보 심사역. '사업계획서' 초안. 포커스: 매출 J커브 성장세, 차별성→매출확대 논리.\n{data_summary}",
            "kodit_loan": f"신보 심사역. '보증신청서' 초안. 포커스: 기대출 대비 유동성 해결 및 상환능력.\n{data_summary}",
            "kibo_plan":  f"기보 심사역. '기술사업계획서' 초안. 포커스: 기술혁신성, 특허현황, R&D역량.\n{data_summary}",
            "kibo_loan":  f"기보 심사역. '기술평가 보증신청서' 초안. 포커스: 기술개발자금 사용처, 상용화 후 재무성과.\n{data_summary}",
            "ir_plan":    f"VC 심사역. 'PSST 사업계획서' 초안. 포커스: Problem, Solution, Scale-up, Team.\n{data_summary}",
            "ir_loan":    f"VC 심사역. '투자제안 1-Pager' 초안. 포커스: 핵심가치, 자금필요성, Exit시나리오.\n{data_summary}",
        }

        st.title("📝 기관별 맞춤형 Gems 프롬프트 팩")
        st.info("아래 프롬프트를 복사하여 각 기관별 Gems 주소로 들어가 붙여넣기 하세요.")
        gem_url = "https://gemini.google.com/app/"
        tabs = st.tabs(["1. 중진공", "2. 소진공", "3. 신보/재단", "4. 기술보증기금", "5. 제안용(IR)"])
        with tabs[0]:
            st.subheader("🏢 중소벤처기업진흥공단")
            c1, c2 = st.columns(2)
            with c1: st.link_button("🚀 중진공 사업계획서 Gems", gem_url, use_container_width=True); st.code(prompts["kosme_plan"], language="markdown")
            with c2: st.link_button("📝 중진공 융자신청서 Gems", gem_url, use_container_width=True); st.code(prompts["kosme_loan"], language="markdown")
        with tabs[1]:
            st.subheader("🏪 소상공인시장진흥공단")
            c1, c2 = st.columns(2)
            with c1: st.link_button("🚀 소진공 사업계획서 Gems", gem_url, use_container_width=True); st.code(prompts["semas_plan"], language="markdown")
            with c2: st.link_button("📝 소진공 융자신청서 Gems", gem_url, use_container_width=True); st.code(prompts["semas_loan"], language="markdown")
        with tabs[2]:
            st.subheader("🏦 신용보증기금 / 지역신보")
            c1, c2 = st.columns(2)
            with c1: st.link_button("🚀 신보 사업계획서 Gems", gem_url, use_container_width=True); st.code(prompts["kodit_plan"], language="markdown")
            with c2: st.link_button("📝 신보 보증신청서 Gems", gem_url, use_container_width=True); st.code(prompts["kodit_loan"], language="markdown")
        with tabs[3]:
            st.subheader("🔬 기술보증기금")
            c1, c2 = st.columns(2)
            with c1: st.link_button("🚀 기보 사업계획서 Gems", gem_url, use_container_width=True); st.code(prompts["kibo_plan"], language="markdown")
            with c2: st.link_button("📝 기보 보증신청서 Gems", gem_url, use_container_width=True); st.code(prompts["kibo_loan"], language="markdown")
        with tabs[4]:
            st.subheader("📈 제안용 (IR / PSST)")
            c1, c2 = st.columns(2)
            with c1: st.link_button("🚀 PSST 사업계획서 Gems", gem_url, use_container_width=True); st.code(prompts["ir_plan"], language="markdown")
            with c2: st.link_button("📝 1-Pager 요약서 Gems", gem_url, use_container_width=True); st.code(prompts["ir_loan"], language="markdown")

    # ---------------------------------------------------------
    # [입력 화면 - 대시보드]
    # ---------------------------------------------------------
    else:
        # 새 리포트 생성 시 이전 캐시 삭제
        for key in ["report_response_text", "report_fig", "report_monthly_vals", "report_d"]:
            if key in st.session_state:
                del st.session_state[key]

        st.title("📊 AI 컨설팅 대시보드")
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            if st.button("📊 1. 기업분석리포트 생성", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "REPORT"; st.rerun()
        with col_t2:
            if st.button("💡 2. 정책자금 매칭 리포트", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "MATCHING"; st.rerun()
        with col_t3:
            if st.button("📝 3. 사업계획서 생성", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "PLAN"; st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
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
            st.text_input("사업장 주소", key="in_biz_addr")
            has_add = st.radio("추가사업장현황", ["무", "유"], horizontal=True, key="in_has_additional_biz")
            if has_add == "유":
                st.text_input("추가 사업장 정보", key="in_additional_biz_addr")

        st.markdown("<br>", unsafe_allow_html=True)
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

        st.markdown("<br>", unsafe_allow_html=True)
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
            st.info(f"#### 🏆 등급 판정 결과\n\n* **KCB:** {get_credit_grade(kcb, 'KCB')}등급\n* **NICE:** {get_credit_grade(nice, 'NICE')}등급")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("4. 재무현황")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.number_input("금년 매출(만원)", value=0, step=1, key="in_sales_current")
        with m2: st.number_input("25년도 매출합계(만원)", value=0, step=1, key="in_sales_2025")
        with m3: st.number_input("24년도 매출합계(만원)", value=0, step=1, key="in_sales_2024")
        with m4: st.number_input("23년도 매출합계(만원)", value=0, step=1, key="in_sales_2023")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("5. 기대출현황")
        d1, d2, d3, d4 = st.columns(4)
        with d1: st.number_input("중진공(만원)", value=0, step=1, key="in_debt_kosme")
        with d2: st.number_input("소진공(만원)", value=0, step=1, key="in_debt_semas")
        with d3: st.number_input("신용보증재단(만원)", value=0, step=1, key="in_debt_koreg")
        with d4: st.number_input("신용보증기금(만원)", value=0, step=1, key="in_debt_kodit")
        d5, d6, d7, d8 = st.columns(4)
        with d5: st.number_input("기술보증기금(만원)", value=0, step=1, key="in_debt_kibo")
        with d6: st.number_input("신용대출(만원)", value=0, step=1, key="in_debt_credit")
        with d7: st.number_input("담보대출(만원)", value=0, step=1, key="in_debt_coll")
        with d8: st.number_input("기타(만원)", value=0, step=1, key="in_debt_etc")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("6. 필요자금")
        p1, p2, p3 = st.columns([1, 1, 2])
        with p1: st.selectbox("자금구분", ["운전자금", "시설자금"], key="in_fund_type")
        with p2: st.number_input("필요자금액(만원)", value=0, step=1, key="in_req_amount")
        with p3: st.text_input("자금사용용도", key="in_fund_purpose")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("7. 인증현황")
        ac1, ac2, ac3, ac4 = st.columns(4)
        with ac1: st.checkbox("소상공인확인서", key="in_chk_1"); st.checkbox("창업확인서", key="in_chk_2")
        with ac2: st.checkbox("여성기업확인서", key="in_chk_3"); st.checkbox("이노비즈", key="in_chk_4")
        with ac3: st.checkbox("벤처인증", key="in_chk_6"); st.checkbox("뿌리기업확인서", key="in_chk_7")
        with ac4: st.checkbox("ISO인증", key="in_chk_10")

        st.markdown("<br>", unsafe_allow_html=True)
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
        st.success("✅ 세팅 완료! 좌측에 API 키 저장하시고 상단 버튼을 클릭해 주십시오.")

# ==========================================
# 메인 실행
# ==========================================
show_main_app()
