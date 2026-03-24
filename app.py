import streamlit as st
import time
import json
import os
import io
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
# 업체 DB (파일 기반)
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
# PDF 생성 함수
# ==========================================
def generate_pdf(c_name, response_text):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import re

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=20*mm, leftMargin=20*mm,
                                topMargin=20*mm, bottomMargin=20*mm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('title', parent=styles['Normal'],
                                     fontSize=18, fontName='Helvetica-Bold',
                                     textColor=colors.HexColor('#174EA6'),
                                     spaceAfter=10)
        heading_style = ParagraphStyle('heading', parent=styles['Normal'],
                                       fontSize=13, fontName='Helvetica-Bold',
                                       textColor=colors.HexColor('#174EA6'),
                                       spaceAfter=6, spaceBefore=12)
        body_style = ParagraphStyle('body', parent=styles['Normal'],
                                    fontSize=10, fontName='Helvetica',
                                    spaceAfter=4, leading=16)

        story = []
        story.append(Paragraph(f"AI 기업분석 결과보고서: {c_name}", title_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#174EA6')))
        story.append(Spacer(1, 10))

        # HTML 태그 제거 후 텍스트 추출
        clean_text = re.sub(r'<[^>]+>', ' ', response_text)
        clean_text = clean_text.replace('&bull;', '•').replace('&lt;br&gt;', '\n').replace('&amp;', '&')
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        # 섹션별로 분리
        sections = re.split(r'(\d+\.\s+[^\n]+)', clean_text)
        for section in sections:
            if section.strip():
                if re.match(r'^\d+\.', section.strip()):
                    story.append(Paragraph(section.strip(), heading_style))
                else:
                    # 긴 텍스트는 분할
                    for line in section.split('\n'):
                        if line.strip():
                            story.append(Paragraph(line.strip(), body_style))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"PDF 생성 오류: {e}")
        return None

# ==========================================
# PPTX 생성 함수
# ==========================================
def generate_pptx(c_name, response_text, d):
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        import re

        prs = Presentation()
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)

        # 색상 정의
        BLUE = RGBColor(0x17, 0x4E, 0xA6)
        WHITE = RGBColor(0xFF, 0xFF, 0xFF)
        DARK = RGBColor(0x33, 0x33, 0x33)
        LIGHT_BG = RGBColor(0xF0, 0xF4, 0xFF)

        def add_slide(layout_idx=6):
            slide_layout = prs.slide_layouts[layout_idx]
            return prs.slides.add_slide(slide_layout)

        def set_bg(slide, color):
            from pptx.oxml.ns import qn
            from lxml import etree
            bg = slide.background
            fill = bg.fill
            fill.solid()
            fill.fore_color.rgb = color

        def add_textbox(slide, text, left, top, width, height,
                        font_size=14, bold=False, color=RGBColor(0x33,0x33,0x33),
                        align=PP_ALIGN.LEFT, bg_color=None, wrap=True):
            txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
            tf = txBox.text_frame
            tf.word_wrap = wrap
            p = tf.paragraphs[0]
            p.alignment = align
            run = p.add_run()
            run.text = text
            run.font.size = Pt(font_size)
            run.font.bold = bold
            run.font.color.rgb = color
            if bg_color:
                from pptx.oxml.ns import qn
                from lxml import etree
                sp = txBox._element
                spPr = sp.find(qn('p:spPr'))
                solidFill = etree.SubElement(spPr, qn('a:solidFill'))
                srgbClr = etree.SubElement(solidFill, qn('a:srgbClr'))
                srgbClr.set('val', f'{bg_color[0]:02X}{bg_color[1]:02X}{bg_color[2]:02X}')
            return txBox

        def add_rect(slide, left, top, width, height, fill_color, line_color=None):
            shape = slide.shapes.add_shape(1, Inches(left), Inches(top), Inches(width), Inches(height))
            shape.fill.solid()
            shape.fill.fore_color.rgb = fill_color
            if line_color:
                shape.line.color.rgb = line_color
            else:
                shape.line.fill.background()
            return shape

        # HTML에서 섹션 추출
        clean = re.sub(r'<[^>]+>', ' ', response_text)
        clean = clean.replace('&bull;', '•').replace('&lt;br&gt;', ' ').replace('&amp;', '&')
        clean = re.sub(r'\s+', ' ', clean).strip()

        # ----- 슬라이드 1: 표지 -----
        slide1 = add_slide()
        set_bg(slide1, BLUE)
        add_rect(slide1, 0, 5.5, 13.33, 2, RGBColor(0x0D, 0x3A, 0x7A))
        add_textbox(slide1, "AI 기업분석 결과보고서", 1, 1.5, 11.33, 1.2,
                    font_size=36, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_textbox(slide1, c_name, 1, 2.8, 11.33, 0.8,
                    font_size=28, bold=True, color=RGBColor(0xAD, 0xD8, 0xFF), align=PP_ALIGN.CENTER)
        add_textbox(slide1, f"작성일: {datetime.now().strftime('%Y년 %m월 %d일')}", 1, 3.8, 11.33, 0.5,
                    font_size=14, color=RGBColor(0xCC, 0xDD, 0xFF), align=PP_ALIGN.CENTER)
        add_textbox(slide1, "본 보고서는 AI 컨설팅 시스템에 의해 자동 생성되었습니다.",
                    1, 6.0, 11.33, 0.5, font_size=11,
                    color=RGBColor(0xAA, 0xBB, 0xDD), align=PP_ALIGN.CENTER)

        # ----- 슬라이드 2: 기업현황 -----
        slide2 = add_slide()
        set_bg(slide2, WHITE)
        add_rect(slide2, 0, 0, 13.33, 1.2, BLUE)
        add_textbox(slide2, "1. 기업현황분석", 0.3, 0.2, 12, 0.8,
                    font_size=22, bold=True, color=WHITE)

        info_items = [
            ("기업명", d.get('in_company_name', '미입력')),
            ("대표자명", d.get('in_rep_name', '미입력')),
            ("업종", d.get('in_industry', '미입력')),
            ("사업개시일", d.get('in_start_date', '미입력')),
            ("사업장 주소", d.get('in_biz_addr', '미입력')),
            ("사업자번호", format_biz_no(d.get('in_raw_biz_no', '미입력'))),
        ]
        for i, (label, value) in enumerate(info_items):
            col = i % 2
            row = i // 2
            x = 0.3 + col * 6.5
            y = 1.4 + row * 1.5
            add_rect(slide2, x, y, 6.2, 1.2, LIGHT_BG)
            add_textbox(slide2, label, x+0.1, y+0.05, 2, 0.4, font_size=10, bold=True, color=BLUE)
            add_textbox(slide2, value, x+0.1, y+0.45, 5.8, 0.6, font_size=12, color=DARK)

        # ----- 슬라이드 3: SWOT -----
        slide3 = add_slide()
        set_bg(slide3, WHITE)
        add_rect(slide3, 0, 0, 13.33, 1.2, BLUE)
        add_textbox(slide3, "2. SWOT 분석", 0.3, 0.2, 12, 0.8, font_size=22, bold=True, color=WHITE)

        swot_data = [
            ("S 강점", RGBColor(0xE3, 0xF2, 0xFD), BLUE),
            ("W 약점", RGBColor(0xFF, 0xEB, 0xEE), RGBColor(0xC6, 0x28, 0x28)),
            ("O 기회", RGBColor(0xE8, 0xF5, 0xE9), RGBColor(0x2E, 0x7D, 0x32)),
            ("T 위협", RGBColor(0xFF, 0xF3, 0xE0), RGBColor(0xE6, 0x5C, 0x00)),
        ]
        positions = [(0.3, 1.4), (6.8, 1.4), (0.3, 4.3), (6.8, 4.3)]
        for i, ((label, bg, tc), (x, y)) in enumerate(zip(swot_data, positions)):
            add_rect(slide3, x, y, 6.2, 2.7, bg)
            add_textbox(slide3, label, x+0.15, y+0.1, 5.8, 0.5, font_size=14, bold=True, color=tc)
            add_textbox(slide3, "AI 분석 결과를 참조하세요.", x+0.15, y+0.7, 5.8, 1.8, font_size=11, color=DARK)

        # ----- 슬라이드 4: 핵심경쟁력 -----
        slide4 = add_slide()
        set_bg(slide4, WHITE)
        add_rect(slide4, 0, 0, 13.33, 1.2, BLUE)
        add_textbox(slide4, "4. 핵심경쟁력분석", 0.3, 0.2, 12, 0.8, font_size=22, bold=True, color=WHITE)

        comp_labels = ["핵심경쟁력 포인트 1", "핵심경쟁력 포인트 2", "핵심경쟁력 포인트 3"]
        for i, label in enumerate(comp_labels):
            y = 1.4 + i * 1.8
            add_rect(slide4, 0.3, y, 12.7, 1.5, LIGHT_BG)
            add_rect(slide4, 0.3, y, 0.12, 1.5, BLUE)
            add_textbox(slide4, label, 0.6, y+0.1, 4, 0.5, font_size=13, bold=True, color=BLUE)
            add_textbox(slide4, "AI 분석 리포트 내용을 참조하세요.", 0.6, y+0.65, 12, 0.6, font_size=11, color=DARK)

        # ----- 슬라이드 5: 자금사용계획 -----
        slide5 = add_slide()
        set_bg(slide5, WHITE)
        add_rect(slide5, 0, 0, 13.33, 1.2, BLUE)
        add_textbox(slide5, "5. 자금 사용계획", 0.3, 0.2, 12, 0.8, font_size=22, bold=True, color=WHITE)
        req_fund = format_kr_currency(d.get('in_req_amount', 0))
        fund_type = d.get('in_fund_type', '운전자금')
        add_textbox(slide5, f"총 신청자금: {req_fund}  |  자금구분: {fund_type}",
                    0.3, 1.3, 12.7, 0.5, font_size=13, bold=True, color=BLUE)
        for i in range(2):
            y = 2.0 + i * 2.3
            add_rect(slide5, 0.3, y, 12.7, 2.0, LIGHT_BG)
            add_textbox(slide5, f"세부항목 {i+1}", 0.5, y+0.1, 3, 0.5, font_size=12, bold=True, color=BLUE)
            add_textbox(slide5, "AI 분석 리포트 내용을 참조하세요.", 0.5, y+0.65, 9, 0.6, font_size=11, color=DARK)
            add_textbox(slide5, "금액: -", 9.5, y+0.1, 3, 0.5, font_size=12, bold=True, color=BLUE)

        # ----- 슬라이드 6: 매출전망 -----
        slide6 = add_slide()
        set_bg(slide6, WHITE)
        add_rect(slide6, 0, 0, 13.33, 1.2, BLUE)
        add_textbox(slide6, "6. 매출 1년 전망", 0.3, 0.2, 12, 0.8, font_size=22, bold=True, color=WHITE)

        stages = [
            ("1단계\n도입", RGBColor(0xE8, 0xEA, 0xF6)),
            ("2단계\n성장", RGBColor(0xD1, 0xD5, 0xF0)),
            ("3단계\n확장", RGBColor(0xB0, 0xBB, 0xE8)),
            ("4단계\n안착", BLUE),
        ]
        for i, (label, bg) in enumerate(stages):
            x = 0.3 + i * 3.2
            add_rect(slide6, x, 1.4, 3.0, 5.5, bg)
            tc = WHITE if i == 3 else BLUE
            add_textbox(slide6, label, x+0.1, 1.6, 2.8, 0.8, font_size=14, bold=True, color=tc, align=PP_ALIGN.CENTER)
            add_textbox(slide6, "AI 분석 내용 참조", x+0.1, 2.6, 2.8, 3.0, font_size=10, color=tc if i==3 else DARK)
            add_textbox(slide6, "목표: - 만원", x+0.1, 6.1, 2.8, 0.5, font_size=11, bold=True, color=RGBColor(0xD3,0x2F,0x2F) if i<3 else WHITE)

        # ----- 슬라이드 7: 성장비전 -----
        slide7 = add_slide()
        set_bg(slide7, WHITE)
        add_rect(slide7, 0, 0, 13.33, 1.2, BLUE)
        add_textbox(slide7, "7. 성장비전 및 AI 코멘트", 0.3, 0.2, 12, 0.8, font_size=22, bold=True, color=WHITE)

        visions = [
            ("🌱 단기 비전", RGBColor(0xE8, 0xF5, 0xE9), RGBColor(0x2E, 0x7D, 0x32)),
            ("🚀 중기 비전", RGBColor(0xFF, 0xF3, 0xE0), RGBColor(0xE6, 0x5C, 0x00)),
            ("👑 장기 비전", RGBColor(0xFF, 0xEB, 0xEE), RGBColor(0xC6, 0x28, 0x28)),
        ]
        for i, (label, bg, tc) in enumerate(visions):
            y = 1.4 + i * 1.9
            add_rect(slide7, 0.3, y, 12.7, 1.7, bg)
            add_rect(slide7, 0.3, y, 0.12, 1.7, tc)
            add_textbox(slide7, label, 0.6, y+0.1, 4, 0.5, font_size=13, bold=True, color=tc)
            add_textbox(slide7, "AI 분석 리포트 내용을 참조하세요.", 0.6, y+0.7, 12, 0.7, font_size=11, color=DARK)

        pptx_buffer = io.BytesIO()
        prs.save(pptx_buffer)
        pptx_buffer.seek(0)
        return pptx_buffer.getvalue()
    except Exception as e:
        st.error(f"PPTX 생성 오류: {e}")
        return None

# ==========================================
# 메인 앱
# ==========================================
def show_main_app():

    with st.sidebar:
        st.markdown("### 🤖 AI 컨설팅 시스템")
        st.markdown("---")

        st.header("⚙️ AI 엔진 설정")
        if "api_key" not in st.session_state:
            st.session_state["api_key"] = st.secrets.get("GEMINI_API_KEY", "")

        api_key_input = st.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
        if st.button("💾 API KEY 저장"):
            st.session_state["api_key"] = api_key_input
            st.success("✅ 저장됨")
            time.sleep(0.5)
            st.rerun()

        if st.session_state.get("api_key", ""):
            genai.configure(api_key=st.session_state["api_key"])

        st.markdown("---")
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
                        text=[format_kr_currency(v) for v in monthly_vals], textposition="top center",
                        textfont=dict(size=11), line=dict(color='#1E88E5', width=4, shape='spline'),
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

                    max_val = max(monthly_vals) if max(monthly_vals) > 0 else 1
                    chart_html = '<div style="background-color:#f8f9fa; padding:20px; border-radius:15px; border:1px solid #e0e0e0; margin:20px 0;">'
                    chart_html += '<div style="text-align:center; font-weight:bold; color:#174EA6; margin-bottom:15px; font-size:18px;">📈 향후 1년간 월별 예상 매출 상승 곡선</div>'
                    chart_html += '<table style="width:100%; height:180px; border-bottom:2px solid #ccc; border-collapse:collapse; table-layout:fixed;"><tr>'
                    for val in monthly_vals:
                        height_px = int((val / max_val) * 140) + 5
                        val_str = format_kr_currency(val).replace('만원', '만')
                        chart_html += f'<td style="vertical-align:bottom; padding:0 5px; border:none;"><div style="font-size:11px; color:#555; margin-bottom:5px; text-align:center;">{val_str}</div><div style="width:80%; height:{height_px}px; background-color:#1E88E5; border-radius:4px 4px 0 0; margin:0 auto;"></div></td>'
                    chart_html += '</tr></table><table style="width:100%; border-collapse:collapse; table-layout:fixed; margin-top:5px;"><tr>'
                    for label in monthly_labels:
                        chart_html += f'<td style="text-align:center; font-size:13px; font-weight:bold; color:#333; padding:5px 0; border:none;">{label}</td>'
                    chart_html += '</tr></table></div>'

                    # ★ 핵심 변경: 4번, 6번, 7번 세로형 레이아웃 적용
                    prompt = f"""
당신은 20년 경력의 중소기업 경영컨설턴트입니다.
아래 양식과 서식 규칙을 반드시 100% 똑같이 지켜서 출력하세요. 마크다운(##, **) 절대 금지.
외부 지식을 총동원하여 각 항목을 3~4문장 이상 상세하게 채우세요. 문장 끝마다 &lt;br&gt; 필수.

[기업 정보]
- 기업명: {c_name} / 대표자: {rep_name} / 업종: {c_ind} / 아이템: {item} / 신청자금: {req_fund}

[출력 양식]
<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업현황분석</h2>
<table style="width:100%; border-collapse: collapse; font-size: 1.1em; background-color:#f8f9fa; border-radius:15px; overflow:hidden; margin-bottom:15px;">
  <tr><td style="padding:15px; border-bottom:1px solid #e0e0e0; width:15%;"><b>기업명</b></td><td style="padding:15px; border-bottom:1px solid #e0e0e0; width:35%;">{c_name}</td><td style="padding:15px; border-bottom:1px solid #e0e0e0; width:15%;"><b>대표자명</b></td><td style="padding:15px; border-bottom:1px solid #e0e0e0; width:35%;">{rep_name}</td></tr>
  <tr><td style="padding:15px; border-bottom:1px solid #e0e0e0;"><b>업종</b></td><td style="padding:15px; border-bottom:1px solid #e0e0e0;">{c_ind}</td><td style="padding:15px; border-bottom:1px solid #e0e0e0;"><b>사업/법인번호</b></td><td style="padding:15px; border-bottom:1px solid #e0e0e0;">{biz_no}{corp_text}</td></tr>
  <tr><td style="padding:15px;"><b>사업장 주소</b></td><td colspan="3" style="padding:15px;">{address}</td></tr>
</table>
<div style="margin-bottom:15px;">(긍정적 잠재력 3~4줄. &lt;br&gt;)</div>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. SWOT 분석</h2>
<table style="width:100%; table-layout:fixed; border-collapse: separate; border-spacing: 15px; margin-bottom:15px; text-align:center;">
  <tr><td style="background-color:#e3f2fd; padding:20px; border-radius:15px; vertical-align:top;"><b>S (강점)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(3~4줄 분석 &lt;br&gt;)</div></td><td style="background-color:#ffebee; padding:20px; border-radius:15px; vertical-align:top;"><b>W (약점)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(3~4줄 분석 &lt;br&gt;)</div></td></tr>
  <tr><td style="background-color:#e8f5e9; padding:20px; border-radius:15px; vertical-align:top;"><b>O (기회)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(3~4줄 분석 &lt;br&gt;)</div></td><td style="background-color:#fff3e0; padding:20px; border-radius:15px; vertical-align:top;"><b>T (위협)</b><br><div style="text-align:left; margin-top:10px; line-height:1.6;">(3~4줄 분석 &lt;br&gt;)</div></td></tr>
</table>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 시장현황 및 경쟁력 비교</h2>
<div style="background-color:#f3e5f5; padding:20px; border-radius:15px; margin-bottom:15px;"><b>📊 시장 현황 분석</b><br><br>&bull; (시장 트렌드 3~4줄 요약 &lt;br&gt;)</div>
<div style="padding:15px; background-color:#fff; border-radius:15px; border:1px solid #e0e0e0;"><b>⚔️ 주요 경쟁사 비교 분석표</b><br>
  <table style="width:100%; border-collapse: collapse; text-align:center; font-size:0.95em; margin-top:10px;">
    <tr style="background-color:#eceff1;"><th style="padding:12px; border:1px solid #ccc;">비교 항목</th><th style="padding:12px; border:1px solid #ccc;">{c_name} (자사)</th><th style="padding:12px; border:1px solid #ccc;">경쟁사 A</th><th style="padding:12px; border:1px solid #ccc;">경쟁사 B</th></tr>
    <tr><td style="padding:12px; border:1px solid #ccc; font-weight:bold;">핵심 타겟</td><td style="padding:12px; border:1px solid #ccc;">(자사)</td><td style="padding:12px; border:1px solid #ccc;">(A)</td><td style="padding:12px; border:1px solid #ccc;">(B)</td></tr>
    <tr><td style="padding:12px; border:1px solid #ccc; font-weight:bold;">차별화 요소</td><td style="padding:12px; border:1px solid #ccc;">(자사)</td><td style="padding:12px; border:1px solid #ccc;">(A)</td><td style="padding:12px; border:1px solid #ccc;">(B)</td></tr>
  </table>
</div>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 핵심경쟁력분석</h2>
<div style="display:flex; flex-direction:column; gap:15px; margin-bottom:15px;">
  <div style="border-left:5px solid #00ACC1; border-radius:10px; background-color:#E0F7FA; padding:20px;">
    <div style="font-weight:bold; font-size:1.05em; color:#00838F; margin-bottom:8px;">포인트 1 (키워드)</div>
    <div style="font-size:0.95em; line-height:1.7;">&bull; (3~4줄 분석 &lt;br&gt;)</div>
  </div>
  <div style="border-left:5px solid #00ACC1; border-radius:10px; background-color:#E0F7FA; padding:20px;">
    <div style="font-weight:bold; font-size:1.05em; color:#00838F; margin-bottom:8px;">포인트 2 (키워드)</div>
    <div style="font-size:0.95em; line-height:1.7;">&bull; (3~4줄 분석 &lt;br&gt;)</div>
  </div>
  <div style="border-left:5px solid #00ACC1; border-radius:10px; background-color:#E0F7FA; padding:20px;">
    <div style="font-weight:bold; font-size:1.05em; color:#00838F; margin-bottom:8px;">포인트 3 (키워드)</div>
    <div style="font-size:0.95em; line-height:1.7;">&bull; (3~4줄 분석 &lt;br&gt;)</div>
  </div>
</div>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">5. 자금 사용계획 (총 신청자금: {req_fund})</h2>
<table style="width:100%; border-collapse: collapse; text-align:left; margin-bottom:15px;">
 <tr style="background-color:#eceff1;"><th style="padding:15px; border:1px solid #ccc; width:20%;">구분 ({fund_type})</th><th style="padding:15px; border:1px solid #ccc; width:60%;">상세 사용계획</th><th style="padding:15px; border:1px solid #ccc; width:20%;">사용예정금액</th></tr>
 <tr><td style="padding:15px; border:1px solid #ccc; font-weight:bold;">(세부항목 1)</td><td style="padding:15px; border:1px solid #ccc;">&bull; (사용처 2~3줄 &lt;br&gt;)</td><td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0;">(금액)</td></tr>
 <tr><td style="padding:15px; border:1px solid #ccc; font-weight:bold;">(세부항목 2)</td><td style="padding:15px; border:1px solid #ccc;">&bull; (사용처 2~3줄 &lt;br&gt;)</td><td style="padding:15px; border:1px solid #ccc; font-weight:bold; color:#1565c0;">(금액)</td></tr>
</table>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">6. 매출 1년 전망</h2>
<div style="display:flex; flex-direction:column; gap:12px; margin-bottom:15px;">
  <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; border-left:5px solid #3949AB;">
    <div style="font-size:1.1em; font-weight:bold; color:#1565c0; margin-bottom:8px;">1단계 (도입)</div>
    <div style="font-size:0.95em; line-height:1.7;">&bull; (전략 3~4줄 &lt;br&gt;)</div>
    <div style="color:#d32f2f; font-weight:bold; margin-top:8px;">목표: OOO만원</div>
  </div>
  <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; border-left:5px solid #3949AB;">
    <div style="font-size:1.1em; font-weight:bold; color:#1565c0; margin-bottom:8px;">2단계 (성장)</div>
    <div style="font-size:0.95em; line-height:1.7;">&bull; (전략 3~4줄 &lt;br&gt;)</div>
    <div style="color:#d32f2f; font-weight:bold; margin-top:8px;">목표: OOO만원</div>
  </div>
  <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; border-left:5px solid #3949AB;">
    <div style="font-size:1.1em; font-weight:bold; color:#1565c0; margin-bottom:8px;">3단계 (확장)</div>
    <div style="font-size:0.95em; line-height:1.7;">&bull; (전략 3~4줄 &lt;br&gt;)</div>
    <div style="color:#d32f2f; font-weight:bold; margin-top:8px;">목표: OOO만원</div>
  </div>
  <div style="background-color:#e8eaf6; padding:20px; border-radius:15px; border-left:5px solid #3949AB;">
    <div style="font-size:1.1em; font-weight:bold; color:#1565c0; margin-bottom:8px;">4단계 (안착)</div>
    <div style="font-size:0.95em; line-height:1.7;">&bull; (전략 3~4줄 &lt;br&gt;)</div>
    <div style="color:#d32f2f; font-weight:bold; margin-top:8px;">최종목표: OOO만원</div>
  </div>
</div>

[GRAPH_INSERT_POINT]

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">7. 성장비전 및 AI 컨설턴트 코멘트</h2>
<div style="display:flex; flex-direction:column; gap:15px; margin-bottom:20px;">
  <div style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #388E3C;">
    <b>🌱 단기 비전</b>
    <div style="margin-top:10px; line-height:1.7;">&bull; (핵심 비전 3~4줄 &lt;br&gt;)</div>
  </div>
  <div style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #F57C00;">
    <b>🚀 중기 비전</b>
    <div style="margin-top:10px; line-height:1.7;">&bull; (핵심 비전 3~4줄 &lt;br&gt;)</div>
  </div>
  <div style="background-color:#ffebee; padding:20px; border-radius:15px; border-left:5px solid #C62828;">
    <b>👑 장기 비전</b>
    <div style="margin-top:10px; line-height:1.7;">&bull; (핵심 비전 3~4줄 &lt;br&gt;)</div>
  </div>
</div>
<div style="background-color:#eeeeee; border-left:5px solid #1565c0; padding:25px; border-radius:15px; margin-top:15px; line-height:1.8;">
  <b>💡 필수 인증 및 특허 확보 조언:</b><br><br>
  &bull; (인증 조언 3~4줄 &lt;br&gt;)<br>
  &bull; (지식재산권 전략 3~4줄 &lt;br&gt;)
</div>
"""
                    response = model.generate_content(prompt)
                    status.update(label="✅ 기업분석리포트 생성 완료!", state="complete")

                try: response_text = response.text
                except: response_text = ""

                if "[GRAPH_INSERT_POINT]" in response_text:
                    parts = response_text.partition("[GRAPH_INSERT_POINT]")
                    st.markdown(parts[0], unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown(parts[2], unsafe_allow_html=True)
                else:
                    st.markdown(response_text, unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)

                st.balloons()
                st.divider()

                # ★ 다운로드 섹션 - PDF / PPTX 선택
                st.subheader("💾 리포트 다운로드")
                safe_file_name = "".join([c for c in c_name if c.isalnum() or c in (" ", "_")]).strip()
                if not safe_file_name: safe_file_name = "업체"

                dl_col1, dl_col2 = st.columns(2)

                with dl_col1:
                    st.markdown("**📄 PDF 다운로드**")
                    with st.spinner("PDF 생성 중..."):
                        pdf_data = generate_pdf(c_name, response_text)
                    if pdf_data:
                        st.download_button(
                            label="📥 PDF로 다운로드",
                            data=pdf_data,
                            file_name=f"{safe_file_name}_기업분석.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )

                with dl_col2:
                    st.markdown("**📊 PPT 다운로드**")
                    with st.spinner("PPT 생성 중..."):
                        pptx_data = generate_pptx(c_name, response_text, d)
                    if pptx_data:
                        st.download_button(
                            label="📥 PPT로 다운로드",
                            data=pptx_data,
                            file_name=f"{safe_file_name}_기업분석.pptx",
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            type="primary",
                            use_container_width=True
                        )

            except Exception as e:
                st.error(f"❌ 분석 중 오류 발생: {str(e)}")

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

                    prompt = f"""당신은 전문 경영컨설턴트입니다. 마크다운 사용 절대 금지.
[입력] 기업명:{c_name} / 업종:{c_ind} / 전년도매출:{s_25} / 총기대출:{total_debt} / 필요자금:{req_fund}
[출력 양식]
<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업 스펙 진단 요약</h2>
<div style="background-color:#f8f9fa; padding:20px; border-radius:15px; border:1px solid #e0e0e0; margin-bottom:15px;">
  <b>기업명:</b> {c_name} | <b>업종:</b> {c_ind} ({biz_type}) | <b>업력:</b> 약 {biz_years}년<br>
  <b>NICE 점수:</b> {nice_score}점 | <b>인증:</b> {cert_status}<br>
  <b>전년도매출:</b> <span style="color:#1565c0; font-weight:bold;">{s_25}</span> | <b>총 기대출:</b> <span style="color:red;">{total_debt}</span> | <b>필요자금: {req_fund}</b>
</div>
<div style="margin-bottom:20px;">(2~3줄 요약. &lt;br&gt;)</div>
<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. 우선순위 추천 정책자금</h2>
<table style="width:100%; table-layout:fixed; border-collapse:separate; border-spacing:15px; margin-bottom:15px;">
  <tr>
    <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32; vertical-align:top;"><b style="font-size:1.2em; color:#2e7d32;">🥇 1순위: [기관명] / [자금명] / 예상한도</b><br><br>&bull; (사유 &lt;br&gt;)</td>
    <td style="background-color:#e8f5e9; padding:20px; border-radius:15px; border-left:5px solid #2e7d32; vertical-align:top;"><b style="font-size:1.2em; color:#2e7d32;">🥈 2순위: [기관명] / [자금명] / 예상한도</b><br><br>&bull; (사유 &lt;br&gt;)</td>
  </tr>
</table>
<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 후순위 추천</h2>
<table style="width:100%; table-layout:fixed; border-collapse:separate; border-spacing:15px; margin-bottom:15px;">
  <tr>
    <td style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00; vertical-align:top;"><b style="font-size:1.2em; color:#ef6c00;">🥉 3순위: [기관명] / [자금명] / 예상한도</b><br><br>&bull; (사유 &lt;br&gt;)</td>
    <td style="background-color:#fff3e0; padding:20px; border-radius:15px; border-left:5px solid #ef6c00; vertical-align:top;"><b style="font-size:1.2em; color:#ef6c00;">🏅 4순위: [기관명] / [자금명] / 예상한도</b><br><br>&bull; (사유 &lt;br&gt;)</td>
  </tr>
</table>
<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 보완 가이드</h2>
<div style="background-color:#ffebee; border-left:5px solid #d32f2f; padding:20px; border-radius:15px;">
  <b style="color:#c62828;">🚨 보완 조언:</b><br><br>&bull; (전략 &lt;br&gt;)
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
body {{font-family:'Malgun Gothic',sans-serif; padding:30px; line-height:1.6; color:#333; max-width:1000px; margin:0 auto; background-color:#fff;}}
.print-btn {{display:block; width:100%; padding:15px; background-color:#174EA6; color:white; font-size:18px; font-weight:bold; border:none; border-radius:10px; cursor:pointer; margin-bottom:30px; text-align:center;}}
@media print {{.print-btn {{display:none;}} @page {{size:A4; margin:10mm;}} body {{padding:0 !important; font-size:13px !important; zoom:0.85;}}}}</style>
</head><body>
<button class="print-btn" onclick="window.print()">🖨️ 클릭하여 PDF로 저장하기</button>
<h1>🎯 AI 정책자금 매칭 리포트: {c_name}</h1>
{response.text}</body></html>"""
                st.download_button(label="📥 매칭 리포트 다운로드 (HTML)", data=html_export, file_name=f"{safe_file_name}_매칭리포트.html", mime="text/html", type="primary")

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

        # ==========================================
        # 1. 기업현황 (사업장 주소 아래 추가사업장)
        # ==========================================
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
            # ★ 수정: 사업장 주소 먼저, 그 아래 추가사업장
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
        # ★ 수정: 순서 변경 [중진공-소진공-신용보증재단-신용보증기금] / [기술보증기금-신용대출-담보대출-기타]
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
