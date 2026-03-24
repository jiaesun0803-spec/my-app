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
# 핵심: AI 출력 후처리 - 마침표 줄바꿈 + 하이픈 강제 적용
# HTML 태그 내부 텍스트 노드에만 적용
# ==========================================
def format_sentences(text):
    """
    순수 텍스트를 마침표 기준으로 분리하고
    각 문장 앞에 '- ' 붙여서 반환 (HTML용 <br> 포함)
    """
    # 기존 하이픈 제거 (중복 방지)
    text = re.sub(r'^[-–•]\s*', '', text.strip())
    # 마침표 기준 분리
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    result = []
    for s in sentences:
        s = s.strip()
        if len(s) < 3:
            continue
        # 기존 하이픈 있으면 제거 후 단일 하이픈
        s = re.sub(r'^[-–•]+\s*', '', s)
        result.append(f"- {s}")
    return result

def postprocess_ai_html(html_text):
    """
    AI가 생성한 HTML에서 <div> 텍스트 내용을
    마침표 줄바꿈 + 하이픈으로 후처리
    테이블 내부는 건드리지 않음
    """
    def process_div_content(m):
        before = m.group(1)  # <div ...>
        content = m.group(2)  # 내부 텍스트
        after = m.group(3)   # </div>

        # 내부에 다른 HTML 태그가 많으면 처리 스킵
        tag_count = len(re.findall(r'<[^/][^>]*>', content))
        if tag_count > 4:
            return m.group(0)

        # 순수 텍스트 추출
        plain = re.sub(r'<[^>]+>', ' ', content)
        plain = re.sub(r'&bull;|•', '', plain)
        plain = re.sub(r'&amp;', '&', plain)
        plain = plain.strip()

        if len(plain) < 10:
            return m.group(0)

        # 문장 분리 + 하이픈
        sentences = format_sentences(plain)
        if not sentences:
            return m.group(0)

        # 각 문장을 줄바꿈으로 연결
        formatted = '<br>'.join(sentences)
        return f"{before}{formatted}{after}"

    # <div> 태그 내용 처리 (단, <table> 안은 제외)
    # 테이블 밖의 div만 처리
    result = re.sub(
        r'(<div[^>]*>)((?:(?!<div|</div>).)+)(</div>)',
        process_div_content,
        html_text,
        flags=re.DOTALL
    )
    return result

# ==========================================
# 섹션별 텍스트 추출 (PPT/HTML용)
# ==========================================
def extract_all_sections(html_text):
    """h2 태그 기준으로 섹션 파싱, 각 섹션 텍스트 반환"""
    sections = {}
    pattern = r'<h2[^>]*>(.*?)</h2>(.*?)(?=<h2|$)'
    matches = re.findall(pattern, html_text, re.DOTALL)
    for title_raw, body_raw in matches:
        title = re.sub(r'<[^>]+>', '', title_raw).strip()
        # 텍스트만 추출
        body = re.sub(r'<br\s*/?>', '\n', body_raw, flags=re.IGNORECASE)
        body = re.sub(r'<[^>]+>', ' ', body)
        body = re.sub(r'&bull;|•', '', body)
        body = re.sub(r'&amp;', '&', body)
        body = re.sub(r'[ \t]+', ' ', body)
        body = body.strip()

        # 마침표 기준 분리 + 하이픈
        sentences = re.split(r'(?<=[.!?])\s+', body)
        lines = []
        for s in sentences:
            s = re.sub(r'^[-–•]+\s*', '', s.strip())
            if len(s) > 3:
                lines.append(f"- {s}")
        sections[title] = '\n'.join(lines)
    return sections

def extract_swot(html_text):
    """SWOT 4개 항목 각각 텍스트 추출"""
    swot = {'S': '', 'W': '', 'O': '', 'T': ''}
    # SWOT 섹션 찾기
    swot_match = re.search(r'SWOT(.*?)(?=<h2|$)', html_text, re.DOTALL | re.IGNORECASE)
    if not swot_match:
        return swot

    swot_block = swot_match.group(1)
    patterns = {
        'S': r'S\s*[\(（][^)）]*강점[^)）]*[\)）](.*?)(?=W\s*[\(（]|$)',
        'W': r'W\s*[\(（][^)）]*약점[^)）]*[\)）](.*?)(?=O\s*[\(（]|$)',
        'O': r'O\s*[\(（][^)）]*기회[^)）]*[\)）](.*?)(?=T\s*[\(（]|$)',
        'T': r'T\s*[\(（][^)）]*위협[^)）]*[\)）](.*?)$',
    }
    for key, pat in patterns.items():
        m = re.search(pat, swot_block, re.DOTALL | re.IGNORECASE)
        if m:
            chunk = re.sub(r'<[^>]+>', ' ', m.group(1))
            chunk = re.sub(r'[ \t]+', ' ', chunk).strip()
            sentences = re.split(r'(?<=[.!?])\s+', chunk)
            lines = []
            for s in sentences:
                s = re.sub(r'^[-–•]+\s*', '', s.strip())
                if len(s) > 3:
                    lines.append(f"- {s}")
            swot[key] = '\n'.join(lines[:5])
    return swot

# ==========================================
# 월별 매출 차트 HTML (그래프 대체)
# ==========================================
def make_chart_html(monthly_vals, monthly_labels):
    max_val = max(monthly_vals) if monthly_vals else 1
    chart = '''<div style="background:#f8f9fa; padding:20px; border-radius:15px;
        border:1px solid #e0e0e0; margin:20px 0; page-break-inside:avoid;">
    <div style="text-align:center; font-weight:bold; color:#174EA6;
        margin-bottom:15px; font-size:17px;">
        📈 향후 1년간 월별 예상 매출 상승 곡선
    </div>
    <table style="width:100%; height:180px; border-bottom:2px solid #ccc;
        border-collapse:collapse; table-layout:fixed;"><tr>'''
    for val in monthly_vals:
        h = int((val / max_val) * 140) + 5
        label = format_kr_currency(val).replace('만원', '만')
        chart += f'''<td style="vertical-align:bottom; padding:0 4px; border:none;">
            <div style="font-size:10px; color:#555; margin-bottom:4px;
                text-align:center; white-space:nowrap;">{label}</div>
            <div style="width:80%; height:{h}px; background:#1E88E5;
                border-radius:4px 4px 0 0; margin:0 auto;"></div>
            </td>'''
    chart += '</tr></table>'
    chart += '<table style="width:100%; border-collapse:collapse; table-layout:fixed; margin-top:5px;"><tr>'
    for label in monthly_labels:
        chart += f'<td style="text-align:center; font-size:12px; font-weight:bold; color:#333; padding:4px 0; border:none;">{label}</td>'
    chart += '</tr></table></div>'
    return chart

# ==========================================
# HTML 다운로드 생성 (그래프 포함)
# ==========================================
def generate_html_download(c_name, response_text, d, monthly_vals, monthly_labels):
    # 그래프 자리에 차트 HTML 삽입
    chart_html = make_chart_html(monthly_vals, monthly_labels)
    body = response_text.replace('[GRAPH_INSERT_POINT]', chart_html)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{c_name} 기업분석리포트</title>
<style>
  * {{ box-sizing:border-box; -webkit-print-color-adjust:exact!important; print-color-adjust:exact!important; }}
  body {{ font-family:'Malgun Gothic','Apple SD Gothic Neo','Nanum Gothic',sans-serif;
         padding:40px; line-height:2.0; color:#333; max-width:1050px; margin:0 auto;
         font-size:14px; background:#fff; }}
  h1 {{ color:#174EA6; text-align:center; font-size:24px; margin-bottom:6px; }}
  .subtitle {{ text-align:center; color:#666; font-size:13px; margin-bottom:28px; }}
  h2, h2.section-title {{ color:#174EA6!important; font-size:16px;
         border-bottom:2px solid #174EA6!important; padding-bottom:7px; margin-top:28px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:12px; font-size:13px; }}
  th, td {{ padding:10px 12px; border:1px solid #ccc; vertical-align:top; }}
  th {{ background:#eceff1; font-weight:bold; }}
  .print-btn {{ display:block; width:100%; padding:13px; background:#174EA6; color:white;
         font-size:16px; font-weight:bold; border:none; border-radius:10px;
         cursor:pointer; margin-bottom:26px; text-align:center; }}
  @media print {{
    .print-btn {{ display:none; }}
    @page {{ size:A4; margin:14mm; }}
    body {{ padding:0!important; font-size:12px!important; }}
    h2, h2.section-title {{ page-break-before:always; margin-top:0!important; }}
    h2.section-title:first-of-type {{ page-break-before:avoid; }}
  }}
</style>
</head>
<body>
<button class="print-btn" onclick="window.print()">
  🖨️ 클릭하여 PDF로 저장 (Ctrl+P → PDF 선택)
</button>
<h1>📋 AI 기업분석 결과보고서</h1>
<div class="subtitle">
  {c_name} &nbsp;|&nbsp; 대표자: {d.get('in_rep_name','미입력')} &nbsp;|&nbsp;
  업종: {d.get('in_industry','미입력')} &nbsp;|&nbsp;
  작성일: {datetime.now().strftime('%Y년 %m월 %d일')}
</div>
<hr style="border:1.5px solid #174EA6; margin-bottom:26px;">
{body}
</body>
</html>"""
    return html.encode('utf-8')

# ==========================================
# PPT 생성 - 화면 레이아웃 그대로
# ==========================================
def generate_pptx(c_name, response_text, d, monthly_vals, monthly_labels):
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN

        # 색상 정의
        BLUE   = RGBColor(0x17,0x4E,0xA6)
        WHITE  = RGBColor(0xFF,0xFF,0xFF)
        DARK   = RGBColor(0x33,0x33,0x33)
        DBLUE  = RGBColor(0x15,0x65,0xC0)
        MBLUE  = RGBColor(0x39,0x49,0xAB)
        DRED   = RGBColor(0xD3,0x2F,0x2F)
        TEAL   = RGBColor(0x00,0x83,0x8F)
        GREEN  = RGBColor(0x38,0x8E,0x3C)
        ORANGE = RGBColor(0xF5,0x7C,0x00)
        RED2   = RGBColor(0xC6,0x28,0x28)

        # 배경색
        BG_LBLUE  = RGBColor(0xE3,0xF2,0xFD)
        BG_LRED   = RGBColor(0xFF,0xEB,0xEE)
        BG_LGREEN = RGBColor(0xE8,0xF5,0xE9)
        BG_LYELL  = RGBColor(0xFF,0xF3,0xE0)
        BG_LTEAL  = RGBColor(0xE0,0xF7,0xFA)
        BG_LPURP  = RGBColor(0xE8,0xEA,0xF6)
        BG_LSAGE  = RGBColor(0xE8,0xF5,0xE9)
        BG_GREY   = RGBColor(0xF8,0xF9,0xFA)
        BG_EBLUE  = RGBColor(0xF0,0xF4,0xFF)

        prs = Presentation()
        prs.slide_width  = Inches(13.33)
        prs.slide_height = Inches(7.5)

        def blank():
            return prs.slides.add_slide(prs.slide_layouts[6])

        def set_bg(slide, rgb):
            f = slide.background.fill
            f.solid()
            f.fore_color.rgb = rgb

        def add_rect(slide, l, t, w, h, fill_rgb, line_rgb=None, line_width=0.5):
            s = slide.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
            s.fill.solid()
            s.fill.fore_color.rgb = fill_rgb
            if line_rgb:
                s.line.color.rgb = line_rgb
                s.line.width = Pt(line_width)
            else:
                s.line.fill.background()
            return s

        def add_text(slide, text, l, t, w, h,
                     size=11, bold=False, color=None,
                     align=PP_ALIGN.LEFT, wrap=True, italic=False):
            if color is None: color = DARK
            tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
            tf = tb.text_frame
            tf.word_wrap = wrap
            lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
            if not lines:
                lines = [text.strip()] if text.strip() else ['']
            first = True
            for line in lines:
                p = tf.paragraphs[0] if first else tf.add_paragraph()
                first = False
                p.alignment = align
                run = p.add_run()
                # 중복 하이픈 제거 후 단일 하이픈
                line = re.sub(r'^-+\s*', '', line).strip()
                run.text = f"- {line}" if line else ''
                run.font.size = Pt(size)
                run.font.bold = bold
                run.font.italic = italic
                run.font.color.rgb = color
            return tb

        def add_text_raw(slide, text, l, t, w, h,
                         size=11, bold=False, color=None,
                         align=PP_ALIGN.LEFT, wrap=True):
            """하이픈 자동 추가 없이 텍스트 그대로"""
            if color is None: color = DARK
            tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
            tf = tb.text_frame
            tf.word_wrap = wrap
            p = tf.paragraphs[0]
            p.alignment = align
            run = p.add_run()
            run.text = text
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color
            return tb

        # 섹션/SWOT 파싱
        sections = extract_all_sections(response_text)
        swot     = extract_swot(response_text)

        def get_section(keywords):
            """키워드로 섹션 찾기"""
            for k in sections:
                if any(kw in k for kw in keywords):
                    return sections[k]
            return ''

        def lines_of(text, limit=20):
            return [l for l in text.split('\n') if l.strip()][:limit]

        # ============================================================
        # 슬라이드 1: 표지
        # ============================================================
        s = blank()
        set_bg(s, BLUE)
        add_rect(s, 0, 5.85, 13.33, 1.65, RGBColor(0x0D,0x3A,0x7A))
        add_text_raw(s, "AI 기업분석 결과보고서",
                     1, 1.4, 11.33, 1.1, size=34, bold=True,
                     color=WHITE, align=PP_ALIGN.CENTER)
        add_text_raw(s, c_name, 1, 2.7, 11.33, 0.9, size=26, bold=True,
                     color=RGBColor(0xAD,0xD8,0xFF), align=PP_ALIGN.CENTER)
        add_text_raw(s,
            f"작성일: {datetime.now().strftime('%Y년 %m월 %d일')}  |  "
            f"담당: {d.get('in_rep_name','미입력')}  |  "
            f"업종: {d.get('in_industry','미입력')}",
            1, 3.75, 11.33, 0.5, size=13,
            color=RGBColor(0xCC,0xDD,0xFF), align=PP_ALIGN.CENTER)
        add_text_raw(s, "본 보고서는 AI 컨설팅 시스템에 의해 자동 생성되었습니다.",
                     1, 6.1, 11.33, 0.45, size=11,
                     color=RGBColor(0xAA,0xBB,0xDD), align=PP_ALIGN.CENTER)

        # ============================================================
        # 슬라이드 2: 기업현황
        # ============================================================
        s = blank()
        set_bg(s, WHITE)
        add_rect(s, 0, 0, 13.33, 1.1, BLUE)
        add_text_raw(s, "1. 기업현황분석", 0.3, 0.18, 12, 0.75,
                     size=22, bold=True, color=WHITE)

        infos = [
            ("기업명",     d.get('in_company_name','미입력')),
            ("대표자명",   d.get('in_rep_name','미입력')),
            ("업종",       d.get('in_industry','미입력')),
            ("사업개시일", d.get('in_start_date','미입력')),
            ("사업자번호", format_biz_no(d.get('in_raw_biz_no','미입력'))),
            ("사업장 주소",d.get('in_biz_addr','미입력')),
        ]
        for i, (label, val) in enumerate(infos):
            col = i % 2
            row = i // 2
            x = 0.25 + col*6.55
            y = 1.18 + row*1.85
            add_rect(s, x, y, 6.35, 1.65, BG_GREY, RGBColor(0xE0,0xE0,0xE0))
            add_rect(s, x, y, 6.35, 0.45, BG_EBLUE)
            add_text_raw(s, label, x+0.15, y+0.08, 3, 0.32,
                         size=10, bold=True, color=BLUE)
            add_text_raw(s, str(val), x+0.15, y+0.55, 6.0, 0.95,
                         size=11, color=DARK)

        # 기업현황 분석 텍스트
        corp_text = get_section(['기업현황', '현황분석'])
        corp_lines = lines_of(corp_text, 4)
        if corp_lines:
            # 기업현황 슬라이드에 추가 텍스트 박스
            add_rect(s, 0.25, 6.75, 12.85, 0.55, BG_EBLUE)
            add_text_raw(s, corp_lines[0], 0.4, 6.8, 12.5, 0.45,
                         size=10, color=DARK)

        # ============================================================
        # 슬라이드 3: SWOT (4분할 색상박스 - 화면과 동일)
        # ============================================================
        s = blank()
        set_bg(s, WHITE)
        add_rect(s, 0, 0, 13.33, 1.1, BLUE)
        add_text_raw(s, "2. SWOT 분석", 0.3, 0.18, 12, 0.75,
                     size=22, bold=True, color=WHITE)

        swot_cfg = [
            ('S', 'S (강점)',  BG_LBLUE,  DBLUE,  0.25, 1.18),
            ('W', 'W (약점)',  BG_LRED,   RED2,   6.8,  1.18),
            ('O', 'O (기회)',  BG_LGREEN, GREEN,  0.25, 4.2),
            ('T', 'T (위협)',  BG_LYELL,  ORANGE, 6.8,  4.2),
        ]
        for key, label, bgc, tc, x, y in swot_cfg:
            add_rect(s, x, y, 6.3, 2.85, bgc, RGBColor(0xCC,0xCC,0xCC))
            add_text_raw(s, label, x+0.18, y+0.12, 5.8, 0.42,
                         size=12, bold=True, color=tc)
            content = swot.get(key, '- 분석 내용 참조.')
            add_text(s, content, x+0.18, y+0.6, 5.9, 2.1,
                     size=9.5, color=DARK)

        # ============================================================
        # 슬라이드 4: 시장현황 및 경쟁력
        # ============================================================
        s = blank()
        set_bg(s, WHITE)
        add_rect(s, 0, 0, 13.33, 1.1, BLUE)
        add_text_raw(s, "3. 시장현황 및 경쟁력 비교", 0.3, 0.18, 12, 0.75,
                     size=22, bold=True, color=WHITE)

        mkt = get_section(['시장현황', '시장', '경쟁'])
        mkt_lines = lines_of(mkt, 12)
        add_rect(s, 0.25, 1.18, 12.85, 6.1, RGBColor(0xF3,0xE5,0xF5),
                 RGBColor(0xCC,0xCC,0xCC))
        add_rect(s, 0.25, 1.18, 0.1, 6.1, RGBColor(0x6A,0x1B,0x9A))
        add_text_raw(s, "📊 시장 현황 분석", 0.48, 1.25, 5, 0.4,
                     size=12, bold=True, color=RGBColor(0x6A,0x1B,0x9A))
        add_text(s, '\n'.join(mkt_lines),
                 0.48, 1.72, 12.5, 5.4, size=10.5, color=DARK)

        # ============================================================
        # 슬라이드 5: 핵심경쟁력 (세로 3박스)
        # ============================================================
        s = blank()
        set_bg(s, WHITE)
        add_rect(s, 0, 0, 13.33, 1.1, BLUE)
        add_text_raw(s, "4. 핵심경쟁력분석", 0.3, 0.18, 12, 0.75,
                     size=22, bold=True, color=WHITE)

        comp = get_section(['핵심경쟁력', '경쟁력분석'])
        comp_lines = lines_of(comp, 15)
        chunk = max(1, len(comp_lines)//3)
        pts = [comp_lines[i*chunk:(i+1)*chunk] for i in range(3)]
        if len(comp_lines) % 3:
            pts[-1] += comp_lines[3*chunk:]

        pt_labels = ['포인트 1', '포인트 2', '포인트 3']
        for i, (pt_lines, pt_lbl) in enumerate(zip(pts, pt_labels)):
            y = 1.18 + i*1.98
            add_rect(s, 0.25, y, 12.85, 1.82, BG_LTEAL,
                     RGBColor(0x00,0xAC,0xC1))
            add_rect(s, 0.25, y, 0.1, 1.82, TEAL)
            add_text_raw(s, pt_lbl, 0.48, y+0.1, 3.5, 0.38,
                         size=11, bold=True, color=TEAL)
            add_text(s, '\n'.join(pt_lines[:3]),
                     0.48, y+0.54, 12.5, 1.15, size=10, color=DARK)

        # ============================================================
        # 슬라이드 6: 자금 사용계획
        # ============================================================
        s = blank()
        set_bg(s, WHITE)
        req_fund = format_kr_currency(d.get('in_req_amount',0))
        fund_type = d.get('in_fund_type','운전자금')
        add_rect(s, 0, 0, 13.33, 1.1, BLUE)
        add_text_raw(s, f"5. 자금 사용계획  (총 신청자금: {req_fund} / {fund_type})",
                     0.3, 0.18, 12.5, 0.75, size=19, bold=True, color=WHITE)

        fund = get_section(['자금 사용', '자금사용'])
        fund_lines = lines_of(fund, 12)
        half = max(1, len(fund_lines)//2)
        f1, f2 = fund_lines[:half], fund_lines[half:]

        for i, (fl, lbl) in enumerate(zip([f1, f2], ['세부항목 1','세부항목 2'])):
            y = 1.18 + i*2.88
            add_rect(s, 0.25, y, 12.85, 2.7, BG_GREY, RGBColor(0xE0,0xE0,0xE0))
            add_rect(s, 0.25, y, 12.85, 0.45, RGBColor(0xEC,0xEF,0xF1))
            add_text_raw(s, lbl, 0.45, y+0.08, 4, 0.32,
                         size=11, bold=True, color=BLUE)
            add_text(s, '\n'.join(fl[:4]),
                     0.45, y+0.58, 12.2, 1.95, size=10, color=DARK)

        # ============================================================
        # 슬라이드 7: 매출 1년 전망 (4단계 세로박스)
        # ============================================================
        s = blank()
        set_bg(s, WHITE)
        add_rect(s, 0, 0, 13.33, 1.1, BLUE)
        add_text_raw(s, "6. 매출 1년 전망", 0.3, 0.18, 12, 0.75,
                     size=22, bold=True, color=WHITE)

        sales = get_section(['매출', '전망'])
        sales_lines = lines_of(sales, 16)
        sc = max(1, len(sales_lines)//4)
        stage_groups = [sales_lines[i*sc:(i+1)*sc] for i in range(4)]
        stage_labels  = ['1단계 (도입)','2단계 (성장)','3단계 (확장)','4단계 (안착)']

        for i, (sl, lbl) in enumerate(zip(stage_groups, stage_labels)):
            y = 1.18 + i*1.55
            add_rect(s, 0.25, y, 12.85, 1.4, BG_LPURP, RGBColor(0x39,0x49,0xAB))
            add_rect(s, 0.25, y, 0.1, 1.4, MBLUE)
            add_text_raw(s, lbl, 0.48, y+0.08, 3.5, 0.38,
                         size=11, bold=True, color=DBLUE)
            add_text(s, '\n'.join(sl[:2]),
                     0.48, y+0.52, 12.2, 0.78, size=10, color=DARK)

        # 매출 바 차트 시각화 (간단한 도형)
        s_bar = blank()
        set_bg(s_bar, WHITE)
        add_rect(s_bar, 0, 0, 13.33, 1.1, BLUE)
        add_text_raw(s_bar, "6. 매출 1년 전망 - 그래프",
                     0.3, 0.18, 12, 0.75, size=22, bold=True, color=WHITE)

        max_v = max(monthly_vals) if monthly_vals else 1
        bar_w = 0.72
        bar_area_h = 5.0
        for i, (val, lbl) in enumerate(zip(monthly_vals, monthly_labels)):
            bar_h = (val / max_v) * bar_area_h
            x = 0.5 + i * 1.02
            y_bottom = 6.95
            y_bar = y_bottom - bar_h
            add_rect(s_bar, x, y_bar, bar_w, bar_h, RGBColor(0x1E,0x88,0xE5))
            add_text_raw(s_bar, lbl, x, 7.05, bar_w, 0.3,
                         size=9, color=DARK, align=PP_ALIGN.CENTER)
            val_label = format_kr_currency(val).replace('만원','만')
            add_text_raw(s_bar, val_label, x-0.1, y_bar-0.3, bar_w+0.2, 0.28,
                         size=8, color=DBLUE, align=PP_ALIGN.CENTER)

        # ============================================================
        # 슬라이드 9: 성장비전 (세로 3박스)
        # ============================================================
        s = blank()
        set_bg(s, WHITE)
        add_rect(s, 0, 0, 13.33, 1.1, BLUE)
        add_text_raw(s, "7. 성장비전 및 AI 컨설턴트 코멘트",
                     0.3, 0.18, 12, 0.75, size=22, bold=True, color=WHITE)

        vision = get_section(['성장비전','비전','코멘트'])
        vision_lines = lines_of(vision, 15)
        vc = max(1, len(vision_lines)//3)
        v_stages = [
            ('🌱 단기 비전', BG_LSAGE, GREEN,  vision_lines[:vc]),
            ('🚀 중기 비전', BG_LYELL, ORANGE, vision_lines[vc:2*vc]),
            ('👑 장기 비전', BG_LRED,  RED2,   vision_lines[2*vc:]),
        ]
        for i, (lbl, bgc, tc, vl) in enumerate(v_stages):
            y = 1.18 + i*1.98
            add_rect(s, 0.25, y, 12.85, 1.82, bgc, RGBColor(0xCC,0xCC,0xCC))
            add_rect(s, 0.25, y, 0.1, 1.82, tc)
            add_text_raw(s, lbl, 0.48, y+0.1, 4, 0.4,
                         size=12, bold=True, color=tc)
            add_text(s, '\n'.join(vl[:3]),
                     0.48, y+0.58, 12.2, 1.1, size=10, color=DARK)

        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        st.error(f"PPT 생성 오류: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None

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
# 메인 앱
# ==========================================
def show_main_app():

    with st.sidebar:
        st.markdown("### 🤖 AI 컨설팅 시스템")
        st.markdown("---")
        st.header("⚙️ AI 엔진 설정")

        if "api_key" not in st.session_state:
            st.session_state["api_key"] = st.secrets.get("GEMINI_API_KEY", "")

        if st.session_state["api_key"]:
            st.success("✅ API KEY 저장됨")
            genai.configure(api_key=st.session_state["api_key"])
            if st.button("🔄 API KEY 변경", use_container_width=True):
                st.session_state["api_key"] = ""
                st.rerun()
        else:
            api_key_input = st.text_input("Gemini API Key", type="password",
                                          placeholder="API 키를 입력하세요")
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
        st.header("📂 업체 관리")
        db = load_db()

        if st.button("💾 현재 정보 저장", use_container_width=True):
            c_name = st.session_state.get("in_company_name","").strip()
            if c_name:
                current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
                db[c_name] = current_data
                save_db(db)
                st.success(f"✅ '{c_name}' 저장 완료!")
            else:
                st.warning("기업명을 먼저 입력해주세요.")

        selected = st.selectbox("저장된 업체 목록", ["선택 안 함"]+list(db.keys()))
        cs1, cs2 = st.columns(2)
        with cs1:
            if st.button("📂 불러오기", use_container_width=True):
                if selected != "선택 안 함":
                    for k, v in db[selected].items():
                        st.session_state[k] = v
                    st.rerun()
        with cs2:
            if st.button("🔄 초기화", use_container_width=True):
                for k in list(st.session_state.keys()):
                    if k.startswith("in_"): del st.session_state[k]
                st.rerun()

        st.markdown("---")
        st.header("🚀 빠른 리포트 생성")
        if st.button("📊 1. 기업분석리포트 생성", use_container_width=True):
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "REPORT"; st.rerun()
        if st.button("💡 2. 정책자금 매칭 리포트", use_container_width=True):
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "MATCHING"; st.rerun()
        if st.button("📝 3. 사업계획서 생성", use_container_width=True):
            st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["view_mode"] = "PLAN"; st.rerun()

    if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
    if "permanent_data" not in st.session_state: st.session_state["permanent_data"] = {}

    # ─────────────────────────────────────────
    # REPORT 모드
    # ─────────────────────────────────────────
    if st.session_state["view_mode"] == "REPORT":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"; st.rerun()

        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name','미입력').strip()
        st.title("📋 시각화 기반 AI 기업분석 리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")

        if not st.session_state.get("api_key",""):
            st.error("⚠️ 좌측 사이드바에 API 키를 입력해주세요.")
            return

        # 캐시 재사용
        if "report_response_text" in st.session_state and "report_fig" in st.session_state:
            response_text   = st.session_state["report_response_text"]
            fig             = st.session_state["report_fig"]
            monthly_vals    = st.session_state.get("report_monthly_vals", [])
            monthly_labels  = st.session_state.get("report_monthly_labels", [])
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
                        available = [m.name for m in genai.list_models()
                                     if 'generateContent' in m.supported_generation_methods]
                    except Exception as e:
                        raise Exception(f"API 키 권한 오류: {e}")

                    if 'models/gemini-1.5-flash' in available: tm = 'gemini-1.5-flash'
                    elif 'models/gemini-1.5-pro' in available: tm = 'gemini-1.5-pro'
                    elif 'models/gemini-pro' in available: tm = 'gemini-pro'
                    elif available: tm = available[0].replace('models/','')
                    else: raise Exception("사용 가능한 모델이 없습니다.")

                    model = genai.GenerativeModel(tm)

                    c_ind    = d.get('in_industry','미입력')
                    rep_name = d.get('in_rep_name','미입력')
                    biz_no   = format_biz_no(d.get('in_raw_biz_no','미입력'))
                    corp_no  = format_corp_no(d.get('in_raw_corp_no',''))
                    corp_text = f" (법인: {corp_no})" if corp_no else ""
                    address  = d.get('in_biz_addr','미입력')
                    if d.get('in_has_additional_biz') == '유' and d.get('in_additional_biz_addr','').strip():
                        address += f" / 추가사업장: {d.get('in_additional_biz_addr')}"
                    fund_type = d.get('in_fund_type','운전자금')
                    req_fund  = format_kr_currency(d.get('in_req_amount',0))
                    item      = d.get('in_item_desc','미입력')

                    val_cur = safe_int(d.get('in_sales_current',0))
                    if val_cur <= 0: val_cur = 1000
                    sv, ev = val_cur/12, val_cur/12*1.5
                    monthly_vals = []
                    for i in range(12):
                        p = i/11.0
                        monthly_vals.append(int(sv+(ev-sv)*p+(ev-sv)*0.15*np.sin(p*np.pi*3.5)))
                    monthly_labels = [f"{i}월" for i in range(1,13)]

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=monthly_labels, y=monthly_vals,
                        mode='lines+markers+text',
                        text=[format_kr_currency(v) for v in monthly_vals],
                        textposition="top center", textfont=dict(size=11),
                        line=dict(color='#1E88E5',width=4,shape='spline'),
                        marker=dict(size=10,color='#FF5252',line=dict(width=2,color='white'))
                    ))
                    fig.update_layout(
                        title="📈 향후 1년간 월별 예상 매출 상승 곡선",
                        xaxis_title="진행 월", yaxis_title="예상 매출액",
                        xaxis=dict(showgrid=False),
                        yaxis=dict(showgrid=True,gridcolor='#e0e0e0'),
                        template="plotly_white",
                        margin=dict(l=20,r=20,t=40,b=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)"
                    )

                    prompt = f"""당신은 20년 경력의 중소기업 경영컨설턴트입니다.
아래 규칙을 반드시 지키세요:
1. 문체: '~있음', '~예상됨', '~확인됨' 간결체. '~습니다' 절대 금지.
2. 마크다운(##, **) 절대 금지.
3. <br> 태그 절대 사용 금지.
4. 각 항목 3~4문장 이상 상세하게 작성.
5. 아래 HTML 양식을 그대로 사용하되, 괄호 안 설명을 실제 내용으로 채울 것.

[기업 정보]
- 기업명: {c_name} / 대표자: {rep_name} / 업종: {c_ind} / 아이템: {item} / 신청자금: {req_fund}

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업현황분석</h2>
<table style="width:100%; border-collapse:collapse; font-size:1.05em; background-color:#f8f9fa; margin-bottom:15px;">
  <tr><td style="padding:13px; border-bottom:1px solid #e0e0e0; width:15%;"><b>기업명</b></td><td style="padding:13px; border-bottom:1px solid #e0e0e0; width:35%;">{c_name}</td><td style="padding:13px; border-bottom:1px solid #e0e0e0; width:15%;"><b>대표자명</b></td><td style="padding:13px; border-bottom:1px solid #e0e0e0; width:35%;">{rep_name}</td></tr>
  <tr><td style="padding:13px; border-bottom:1px solid #e0e0e0;"><b>업종</b></td><td style="padding:13px; border-bottom:1px solid #e0e0e0;">{c_ind}</td><td style="padding:13px; border-bottom:1px solid #e0e0e0;"><b>사업자번호</b></td><td style="padding:13px; border-bottom:1px solid #e0e0e0;">{biz_no}{corp_text}</td></tr>
  <tr><td style="padding:13px;"><b>사업장 주소</b></td><td colspan="3" style="padding:13px;">{address}</td></tr>
</table>
<div style="background-color:#EEF2FF; padding:15px; border-radius:10px; margin-bottom:15px; line-height:2.0;">(기업 잠재력 3~4문장 작성)</div>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. SWOT 분석</h2>
<table style="width:100%; table-layout:fixed; border-collapse:separate; border-spacing:13px; margin-bottom:15px;">
  <tr>
    <td style="background-color:#e3f2fd; padding:18px; border-radius:13px; vertical-align:top; line-height:2.0;"><b style="color:#1565C0;">S (강점)</b><div style="margin-top:10px;">(강점 3~4문장)</div></td>
    <td style="background-color:#ffebee; padding:18px; border-radius:13px; vertical-align:top; line-height:2.0;"><b style="color:#C62828;">W (약점)</b><div style="margin-top:10px;">(약점 3~4문장)</div></td>
  </tr>
  <tr>
    <td style="background-color:#e8f5e9; padding:18px; border-radius:13px; vertical-align:top; line-height:2.0;"><b style="color:#2E7D32;">O (기회)</b><div style="margin-top:10px;">(기회 3~4문장)</div></td>
    <td style="background-color:#fff3e0; padding:18px; border-radius:13px; vertical-align:top; line-height:2.0;"><b style="color:#E65C00;">T (위협)</b><div style="margin-top:10px;">(위협 3~4문장)</div></td>
  </tr>
</table>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 시장현황 및 경쟁력 비교</h2>
<div style="background-color:#f3e5f5; padding:18px; border-radius:13px; margin-bottom:13px; line-height:2.0;"><b>📊 시장 현황 분석</b><div style="margin-top:10px;">(시장 트렌드 3~4문장)</div></div>
<div style="padding:13px; background-color:#fff; border-radius:13px; border:1px solid #e0e0e0;">
<b>⚔️ 주요 경쟁사 비교</b>
<table style="width:100%; border-collapse:collapse; text-align:center; font-size:0.93em; margin-top:10px;">
<tr style="background-color:#eceff1;"><th style="padding:11px; border:1px solid #ccc;">비교 항목</th><th style="padding:11px; border:1px solid #ccc;">{c_name} (자사)</th><th style="padding:11px; border:1px solid #ccc;">경쟁사 A</th><th style="padding:11px; border:1px solid #ccc;">경쟁사 B</th></tr>
<tr><td style="padding:11px; border:1px solid #ccc; font-weight:bold;">핵심 타겟</td><td style="padding:11px; border:1px solid #ccc;">(자사 내용)</td><td style="padding:11px; border:1px solid #ccc;">(A 내용)</td><td style="padding:11px; border:1px solid #ccc;">(B 내용)</td></tr>
<tr><td style="padding:11px; border:1px solid #ccc; font-weight:bold;">차별화 요소</td><td style="padding:11px; border:1px solid #ccc;">(자사 내용)</td><td style="padding:11px; border:1px solid #ccc;">(A 내용)</td><td style="padding:11px; border:1px solid #ccc;">(B 내용)</td></tr>
<tr><td style="padding:11px; border:1px solid #ccc; font-weight:bold;">예상 점유율</td><td style="padding:11px; border:1px solid #ccc;">(자사 내용)</td><td style="padding:11px; border:1px solid #ccc;">(A 내용)</td><td style="padding:11px; border:1px solid #ccc;">(B 내용)</td></tr>
</table>
</div>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 핵심경쟁력분석</h2>
<div style="display:flex; flex-direction:column; gap:12px; margin-bottom:13px;">
  <div style="border-left:5px solid #00ACC1; border-radius:10px; background-color:#E0F7FA; padding:17px; line-height:2.0;"><div style="font-weight:bold; color:#00838F; margin-bottom:7px;">포인트 1: (키워드)</div><div>(분석 3~4문장)</div></div>
  <div style="border-left:5px solid #00ACC1; border-radius:10px; background-color:#E0F7FA; padding:17px; line-height:2.0;"><div style="font-weight:bold; color:#00838F; margin-bottom:7px;">포인트 2: (키워드)</div><div>(분석 3~4문장)</div></div>
  <div style="border-left:5px solid #00ACC1; border-radius:10px; background-color:#E0F7FA; padding:17px; line-height:2.0;"><div style="font-weight:bold; color:#00838F; margin-bottom:7px;">포인트 3: (키워드)</div><div>(분석 3~4문장)</div></div>
</div>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">5. 자금 사용계획 (총 신청자금: {req_fund})</h2>
<table style="width:100%; border-collapse:collapse; text-align:left; margin-bottom:13px;">
  <tr style="background-color:#eceff1;"><th style="padding:13px; border:1px solid #ccc; width:20%;">구분 ({fund_type})</th><th style="padding:13px; border:1px solid #ccc; width:60%;">상세 사용계획</th><th style="padding:13px; border:1px solid #ccc; width:20%;">사용예정금액</th></tr>
  <tr><td style="padding:13px; border:1px solid #ccc; font-weight:bold;">(세부항목 1)</td><td style="padding:13px; border:1px solid #ccc; line-height:2.0;">(사용처 2~3문장)</td><td style="padding:13px; border:1px solid #ccc; font-weight:bold; color:#1565c0;">(금액)</td></tr>
  <tr><td style="padding:13px; border:1px solid #ccc; font-weight:bold;">(세부항목 2)</td><td style="padding:13px; border:1px solid #ccc; line-height:2.0;">(사용처 2~3문장)</td><td style="padding:13px; border:1px solid #ccc; font-weight:bold; color:#1565c0;">(금액)</td></tr>
</table>

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">6. 매출 1년 전망</h2>
<div style="display:flex; flex-direction:column; gap:11px; margin-bottom:13px;">
  <div style="background-color:#e8eaf6; padding:17px; border-radius:13px; border-left:5px solid #3949AB; line-height:2.0;"><div style="font-weight:bold; color:#1565c0; margin-bottom:7px;">1단계 (도입)</div><div>(전략 2~3문장)</div><div style="color:#d32f2f; font-weight:bold; margin-top:7px;">목표: OOO만원</div></div>
  <div style="background-color:#e8eaf6; padding:17px; border-radius:13px; border-left:5px solid #3949AB; line-height:2.0;"><div style="font-weight:bold; color:#1565c0; margin-bottom:7px;">2단계 (성장)</div><div>(전략 2~3문장)</div><div style="color:#d32f2f; font-weight:bold; margin-top:7px;">목표: OOO만원</div></div>
  <div style="background-color:#e8eaf6; padding:17px; border-radius:13px; border-left:5px solid #3949AB; line-height:2.0;"><div style="font-weight:bold; color:#1565c0; margin-bottom:7px;">3단계 (확장)</div><div>(전략 2~3문장)</div><div style="color:#d32f2f; font-weight:bold; margin-top:7px;">목표: OOO만원</div></div>
  <div style="background-color:#e8eaf6; padding:17px; border-radius:13px; border-left:5px solid #3949AB; line-height:2.0;"><div style="font-weight:bold; color:#1565c0; margin-bottom:7px;">4단계 (안착)</div><div>(전략 2~3문장)</div><div style="color:#d32f2f; font-weight:bold; margin-top:7px;">최종목표: OOO만원</div></div>
</div>

[GRAPH_INSERT_POINT]

<h2 class="section-title" style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">7. 성장비전 및 AI 컨설턴트 코멘트</h2>
<div style="display:flex; flex-direction:column; gap:11px; margin-bottom:18px;">
  <div style="background-color:#e8f5e9; padding:17px; border-radius:13px; border-left:5px solid #388E3C; line-height:2.0;"><b>🌱 단기 비전</b><div style="margin-top:9px;">(단기 비전 2~3문장)</div></div>
  <div style="background-color:#fff3e0; padding:17px; border-radius:13px; border-left:5px solid #F57C00; line-height:2.0;"><b>🚀 중기 비전</b><div style="margin-top:9px;">(중기 비전 2~3문장)</div></div>
  <div style="background-color:#ffebee; padding:17px; border-radius:13px; border-left:5px solid #C62828; line-height:2.0;"><b>👑 장기 비전</b><div style="margin-top:9px;">(장기 비전 2~3문장)</div></div>
</div>
<div style="background-color:#eeeeee; border-left:5px solid #1565c0; padding:22px; border-radius:13px; line-height:2.0;">
  <b>💡 필수 인증 및 특허 확보 조언</b>
  <div style="margin-top:9px;">(인증 조언 2~3문장)</div>
  <div style="margin-top:7px;">(지식재산권 전략 2~3문장)</div>
</div>
"""
                    response = model.generate_content(prompt)
                    status.update(label="✅ 리포트 생성 완료!", state="complete")

                try: response_text = response.text
                except: response_text = ""

                # ★ 후처리: AI가 생성한 텍스트에서 마침표 줄바꿈 + 하이픈 강제 적용
                response_text = postprocess_ai_html(response_text)

                st.session_state["report_response_text"]  = response_text
                st.session_state["report_fig"]            = fig
                st.session_state["report_d"]              = d
                st.session_state["report_monthly_vals"]   = monthly_vals
                st.session_state["report_monthly_labels"] = monthly_labels

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
                st.error(f"❌ 오류 발생: {str(e)}")
                return

        # ── 다운로드 ──
        st.divider()
        st.subheader("💾 리포트 다운로드")
        response_text  = st.session_state.get("report_response_text","")
        report_d       = st.session_state.get("report_d", d)
        monthly_vals   = st.session_state.get("report_monthly_vals",[])
        monthly_labels = st.session_state.get("report_monthly_labels",[])
        safe_fn = "".join([c for c in c_name if c.isalnum() or c in (" ","_")]).strip() or "업체"

        dl1, dl2 = st.columns(2)
        with dl1:
            st.markdown("**📄 PDF 다운로드**")
            st.caption("HTML 받은 후 → 브라우저에서 Ctrl+P → PDF 저장")
            html_data = generate_html_download(
                c_name, response_text, report_d, monthly_vals, monthly_labels)
            st.download_button(
                label="📥 HTML 다운로드 (그래프 포함)",
                data=html_data,
                file_name=f"{safe_fn}_기업분석.html",
                mime="text/html; charset=utf-8",
                type="primary",
                use_container_width=True
            )
        with dl2:
            st.markdown("**📊 PPT 다운로드**")
            st.caption("화면 레이아웃 그대로 슬라이드 생성")
            if st.button("📊 PPT 생성하기", use_container_width=True):
                with st.spinner("PPT 생성 중..."):
                    pptx_data = generate_pptx(
                        c_name, response_text, report_d,
                        monthly_vals, monthly_labels)
                if pptx_data:
                    st.download_button(
                        label="📥 PPT 다운로드",
                        data=pptx_data,
                        file_name=f"{safe_fn}_기업분석.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        type="primary",
                        use_container_width=True
                    )

    # ─────────────────────────────────────────
    # MATCHING 모드
    # ─────────────────────────────────────────
    elif st.session_state["view_mode"] == "MATCHING":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"; st.rerun()

        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name','미입력').strip()
        st.title("🎯 AI 정책자금 최적화 매칭 리포트")
        st.subheader(f"📌 분석 대상 기업: {c_name}")

        if not st.session_state.get("api_key",""):
            st.error("⚠️ 좌측 사이드바에 API 키를 입력해주세요.")
            return

        try:
            with st.status("🚀 AI가 심사를 진행 중입니다...", expanded=True) as status:
                available = [m.name for m in genai.list_models()
                             if 'generateContent' in m.supported_generation_methods]
                tm = 'gemini-1.5-flash' if 'models/gemini-1.5-flash' in available else 'gemini-pro'
                model = genai.GenerativeModel(tm)

                total_debt = format_kr_currency(sum([safe_int(d.get(k,0)) for k in
                    ['in_debt_kosme','in_debt_semas','in_debt_koreg','in_debt_kodit',
                     'in_debt_kibo','in_debt_etc','in_debt_credit','in_debt_coll']]))
                s_25 = format_kr_currency(safe_int(d.get('in_sales_2025',0)))
                c_ind = d.get('in_industry','미입력')
                biz_type = d.get('in_biz_type','개인')
                nice_score = safe_int(d.get('in_nice_score',0))
                req_fund = format_kr_currency(safe_int(d.get('in_req_amount',0)))
                cert = "보유" if any([d.get('in_chk_6'),d.get('in_chk_4'),d.get('in_chk_10')]) else "미보유"
                biz_years = 0
                if d.get('in_start_date','').strip():
                    try: biz_years = max(0,2026-int(d.get('in_start_date','')[:4]))
                    except: pass

                prompt = f"""당신은 전문 경영컨설턴트입니다.
규칙: 마크다운 금지. '~있음','~예상됨' 간결체. '~습니다' 금지. <br> 태그 금지.
[입력] 기업명:{c_name} / 업종:{c_ind} / 전년도매출:{s_25} / 총기대출:{total_debt} / 필요자금:{req_fund}

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">1. 기업 스펙 진단 요약</h2>
<div style="background-color:#f8f9fa; padding:18px; border-radius:13px; border:1px solid #e0e0e0; margin-bottom:13px;">
  <b>기업명:</b> {c_name} | <b>업종:</b> {c_ind} ({biz_type}) | <b>업력:</b> 약 {biz_years}년 | <b>NICE:</b> {nice_score}점 | <b>인증:</b> {cert}<br>
  <b>전년도매출:</b> <span style="color:#1565c0;font-weight:bold;">{s_25}</span> | <b>총 기대출:</b> <span style="color:red;">{total_debt}</span> | <b>필요자금: {req_fund}</b>
</div>
<div style="background-color:#EEF2FF; padding:13px; border-radius:10px; margin-bottom:17px; line-height:2.0;">(진단 요약 2~3문장)</div>

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">2. 우선순위 추천 정책자금</h2>
<table style="width:100%; table-layout:fixed; border-collapse:separate; border-spacing:13px; margin-bottom:13px;">
  <tr>
    <td style="background-color:#e8f5e9; padding:18px; border-radius:13px; border-left:5px solid #2e7d32; vertical-align:top; line-height:2.0;"><b style="color:#2e7d32;">🥇 1순위: [기관명] / [자금명] / 예상한도</b><div style="margin-top:9px;">(사유 2~3문장)</div></td>
    <td style="background-color:#e8f5e9; padding:18px; border-radius:13px; border-left:5px solid #2e7d32; vertical-align:top; line-height:2.0;"><b style="color:#2e7d32;">🥈 2순위: [기관명] / [자금명] / 예상한도</b><div style="margin-top:9px;">(사유 2~3문장)</div></td>
  </tr>
</table>

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">3. 후순위 추천</h2>
<table style="width:100%; table-layout:fixed; border-collapse:separate; border-spacing:13px; margin-bottom:13px;">
  <tr>
    <td style="background-color:#fff3e0; padding:18px; border-radius:13px; border-left:5px solid #ef6c00; vertical-align:top; line-height:2.0;"><b style="color:#ef6c00;">🥉 3순위: [기관명] / [자금명] / 예상한도</b><div style="margin-top:9px;">(사유 2~3문장)</div></td>
    <td style="background-color:#fff3e0; padding:18px; border-radius:13px; border-left:5px solid #ef6c00; vertical-align:top; line-height:2.0;"><b style="color:#ef6c00;">🏅 4순위: [기관명] / [자금명] / 예상한도</b><div style="margin-top:9px;">(사유 2~3문장)</div></td>
  </tr>
</table>

<h2 style="color:#174EA6; border-bottom:2px solid #174EA6; padding-bottom:8px; margin-top:30px;">4. 보완 가이드</h2>
<div style="background-color:#ffebee; border-left:5px solid #d32f2f; padding:18px; border-radius:13px; line-height:2.0;">
  <b style="color:#c62828;">🚨 보완 조언</b>
  <div style="margin-top:9px;">(전략 2~3문장)</div>
</div>"""
                response = model.generate_content(prompt)
                status.update(label="✅ 매칭 리포트 생성 완료!", state="complete")

            processed = postprocess_ai_html(response.text)
            st.markdown(processed, unsafe_allow_html=True)
            st.balloons()
            st.divider()
            safe_fn = "".join([c for c in c_name if c.isalnum() or c in (" ","_")]).strip() or "업체"
            html_data = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<title>{c_name} 매칭리포트</title>
<style>*{{box-sizing:border-box;-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important;}}
body{{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;padding:35px;line-height:2.0;
color:#333;max-width:1050px;margin:0 auto;background:#fff;font-size:14px;}}
.print-btn{{display:block;width:100%;padding:13px;background:#174EA6;color:white;font-size:16px;
font-weight:bold;border:none;border-radius:10px;cursor:pointer;margin-bottom:26px;text-align:center;}}
@media print{{.print-btn{{display:none;}}@page{{size:A4;margin:12mm;}}
body{{padding:0!important;font-size:12px!important;}}}}</style>
</head><body>
<button class="print-btn" onclick="window.print()">🖨️ 클릭하여 PDF로 저장</button>
<h1>🎯 AI 정책자금 매칭 리포트: {c_name}</h1>
{processed}</body></html>""".encode('utf-8')
            st.download_button(label="📥 매칭 리포트 다운로드 (HTML→PDF)",
                               data=html_data,
                               file_name=f"{safe_fn}_매칭리포트.html",
                               mime="text/html; charset=utf-8",
                               type="primary")
        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")

    # ─────────────────────────────────────────
    # PLAN 모드
    # ─────────────────────────────────────────
    elif st.session_state["view_mode"] == "PLAN":
        if st.button("⬅️ 대시보드로 돌아가기"):
            for k, v in st.session_state["permanent_data"].items():
                st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"; st.rerun()

        d = st.session_state["permanent_data"]
        c_name = d.get('in_company_name','미입력').strip()
        rep_name = d.get('in_rep_name','미입력')
        c_ind = d.get('in_industry','미입력')
        career = d.get('in_career','미입력')
        s_25 = format_kr_currency(d.get('in_sales_2025',0))
        total_debt = format_kr_currency(sum([safe_int(d.get(k,0)) for k in
            ['in_debt_kosme','in_debt_semas','in_debt_koreg','in_debt_kodit',
             'in_debt_kibo','in_debt_etc','in_debt_credit','in_debt_coll']]))
        nice = d.get('in_nice_score',0)
        item = d.get('in_item_desc','미입력')
        market = d.get('in_market_status','미입력')
        diff = d.get('in_diff_point','미입력')
        cert = "보유" if any([d.get('in_chk_6'),d.get('in_chk_4'),d.get('in_chk_10')]) else "미보유"
        req_fund = format_kr_currency(d.get('in_req_amount',0))
        fund_type = d.get('in_fund_type','운전자금')
        fund_purpose = d.get('in_fund_purpose','미입력')
        biz_years = 0
        if d.get('in_start_date','').strip():
            try: biz_years = max(0,2026-int(d.get('in_start_date','')[:4]))
            except: pass

        ds = (f"[기업] {c_name}/{rep_name}/{c_ind}/업력{biz_years}년/{career}\n"
              f"[재무] 전년매출:{s_25}/기대출:{total_debt}/NICE:{nice}점\n"
              f"[비즈니스] {item}/{market}/{diff}/인증:{cert}\n"
              f"[자금] {req_fund}({fund_type}/{fund_purpose})")
        gem = "https://gemini.google.com/app/"
        prompts = {
            "kosme_plan": f"중진공 심사역. 사업계획서 초안. 포커스: 고용창출, 기술성, 미래성장성.\n{ds}",
            "kosme_loan": f"중진공 심사역. 융자신청서 초안. 포커스: 재무분석, 자금조달 및 상환계획.\n{ds}",
            "semas_plan": f"소진공 심사역. 사업계획서 초안. 포커스: 사업생존가능성, 지역상권 영업전략.\n{ds}",
            "semas_loan": f"소진공 심사역. 융자신청서 초안. 포커스: 매출대비 고정비 및 상환능력 증빙.\n{ds}",
            "kodit_plan": f"신보 심사역. 사업계획서 초안. 포커스: 매출 J커브 성장세, 차별성→매출확대 논리.\n{ds}",
            "kodit_loan": f"신보 심사역. 보증신청서 초안. 포커스: 기대출 대비 유동성 해결 및 상환능력.\n{ds}",
            "kibo_plan":  f"기보 심사역. 기술사업계획서 초안. 포커스: 기술혁신성, 특허현황, R&D역량.\n{ds}",
            "kibo_loan":  f"기보 심사역. 기술평가 보증신청서 초안. 포커스: 기술개발자금 사용처, 상용화 후 재무성과.\n{ds}",
            "ir_plan":    f"VC 심사역. PSST 사업계획서 초안. 포커스: Problem, Solution, Scale-up, Team.\n{ds}",
            "ir_loan":    f"VC 심사역. 투자제안 1-Pager 초안. 포커스: 핵심가치, 자금필요성, Exit시나리오.\n{ds}",
        }
        st.title("📝 기관별 맞춤형 Gems 프롬프트 팩")
        st.info("아래 프롬프트를 복사하여 각 기관별 Gems 주소로 들어가 붙여넣기 하세요.")
        tabs = st.tabs(["1. 중진공","2. 소진공","3. 신보/재단","4. 기술보증기금","5. 제안용(IR)"])
        tab_cfg = [
            ("kosme_plan","kosme_loan","🏢 중소벤처기업진흥공단"),
            ("semas_plan","semas_loan","🏪 소상공인시장진흥공단"),
            ("kodit_plan","kodit_loan","🏦 신용보증기금 / 지역신보"),
            ("kibo_plan", "kibo_loan", "🔬 기술보증기금"),
            ("ir_plan",   "ir_loan",   "📈 제안용 (IR / PSST)"),
        ]
        for tab, (k1,k2,title) in zip(tabs, tab_cfg):
            with tab:
                st.subheader(title)
                c1,c2 = st.columns(2)
                with c1:
                    st.link_button("🚀 사업계획서 Gems", gem, use_container_width=True)
                    st.code(prompts[k1], language="markdown")
                with c2:
                    st.link_button("📝 융자/보증신청서 Gems", gem, use_container_width=True)
                    st.code(prompts[k2], language="markdown")

    # ─────────────────────────────────────────
    # INPUT 모드 (대시보드)
    # ─────────────────────────────────────────
    else:
        for key in ["report_response_text","report_fig","report_d",
                    "report_monthly_vals","report_monthly_labels"]:
            if key in st.session_state: del st.session_state[key]

        st.title("📊 AI 컨설팅 대시보드")
        c1,c2,c3 = st.columns(3)
        with c1:
            if st.button("📊 1. 기업분석리포트 생성", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k:v for k,v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "REPORT"; st.rerun()
        with c2:
            if st.button("💡 2. 정책자금 매칭 리포트", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k:v for k,v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "MATCHING"; st.rerun()
        with c3:
            if st.button("📝 3. 사업계획서 생성", use_container_width=True, type="primary"):
                st.session_state["permanent_data"] = {k:v for k,v in st.session_state.items() if k.startswith("in_")}
                st.session_state["view_mode"] = "PLAN"; st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("1. 기업현황")
        c1,c2,c3 = st.columns(3)
        with c1:
            st.text_input("기업명", key="in_company_name")
            st.text_input("사업자번호", key="in_raw_biz_no")
            bt = st.radio("사업자유형", ["개인","법인"], horizontal=True, key="in_biz_type")
            if bt == "법인": st.text_input("법인등록번호", key="in_raw_corp_no")
        with c2:
            st.text_input("사업개시일", placeholder="2020.01.01", key="in_start_date")
            st.selectbox("업종", ["제조업","서비스업","IT업","도소매업","건설업","기타"], key="in_industry")
            ls = st.radio("사업장 임대여부", ["자가","임대"], horizontal=True, key="in_lease_status")
            if ls == "임대":
                lc1,lc2 = st.columns(2)
                with lc1: st.number_input("보증금(만원)", value=0, step=1, key="in_lease_deposit")
                with lc2: st.number_input("월임대료(만원)", value=0, step=1, key="in_lease_rent")
        with c3:
            st.text_input("전화번호", key="in_biz_tel")
            st.text_input("사업장 주소", key="in_biz_addr")
            ha = st.radio("추가사업장현황", ["무","유"], horizontal=True, key="in_has_additional_biz")
            if ha == "유": st.text_input("추가 사업장 정보", key="in_additional_biz_addr")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("2. 대표자 정보")
        r1,r2,r3 = st.columns(3)
        with r1:
            rc1,rc2 = st.columns(2)
            with rc1: st.text_input("대표자명", key="in_rep_name")
            with rc2: st.text_input("생년월일", key="in_rep_dob")
            st.text_input("연락처", key="in_rep_phone")
            st.selectbox("통신사", ["SKT","KT","LG U+","알뜰폰"], key="in_rep_telecom")
            st.text_input("이메일 주소", key="in_rep_email")
        with r2:
            st.text_input("거주지 주소", key="in_home_addr")
            st.radio("거주지 상태", ["자가","임대"], horizontal=True, key="in_home_status")
            st.text_input("부동산 현황", key="in_real_estate")
        with r3:
            st.text_input("최종학교", key="in_edu_school")
            st.text_input("학과", key="in_edu_major")
            st.text_area("경력(최근기준)", key="in_career")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("3. 신용 및 연체 정보")
        cr1,cr2 = st.columns(2)
        with cr1:
            cc1,cc2 = st.columns(2)
            with cc1: st.radio("세금체납", ["무","유"], horizontal=True, key="in_tax_status")
            with cc2: st.radio("금융연체", ["무","유"], horizontal=True, key="in_fin_status")
            sc1,sc2 = st.columns(2)
            with sc1: kcb = st.number_input("KCB 점수", value=0, step=1, key="in_kcb_score")
            with sc2: nice = st.number_input("NICE 점수", value=0, step=1, key="in_nice_score")
        with cr2:
            st.info(f"#### 🏆 등급 판정 결과\n\n* **KCB:** {get_credit_grade(kcb,'KCB')}등급\n* **NICE:** {get_credit_grade(nice,'NICE')}등급")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("4. 재무현황")
        m1,m2,m3,m4 = st.columns(4)
        with m1: st.number_input("금년 매출(만원)", value=0, step=1, key="in_sales_current")
        with m2: st.number_input("25년도 매출합계(만원)", value=0, step=1, key="in_sales_2025")
        with m3: st.number_input("24년도 매출합계(만원)", value=0, step=1, key="in_sales_2024")
        with m4: st.number_input("23년도 매출합계(만원)", value=0, step=1, key="in_sales_2023")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("5. 기대출현황")
        d1,d2,d3,d4 = st.columns(4)
        with d1: st.number_input("중진공(만원)", value=0, step=1, key="in_debt_kosme")
        with d2: st.number_input("소진공(만원)", value=0, step=1, key="in_debt_semas")
        with d3: st.number_input("신용보증재단(만원)", value=0, step=1, key="in_debt_koreg")
        with d4: st.number_input("신용보증기금(만원)", value=0, step=1, key="in_debt_kodit")
        d5,d6,d7,d8 = st.columns(4)
        with d5: st.number_input("기술보증기금(만원)", value=0, step=1, key="in_debt_kibo")
        with d6: st.number_input("신용대출(만원)", value=0, step=1, key="in_debt_credit")
        with d7: st.number_input("담보대출(만원)", value=0, step=1, key="in_debt_coll")
        with d8: st.number_input("기타(만원)", value=0, step=1, key="in_debt_etc")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("6. 필요자금")
        p1,p2,p3 = st.columns([1,1,2])
        with p1: st.selectbox("자금구분", ["운전자금","시설자금"], key="in_fund_type")
        with p2: st.number_input("필요자금액(만원)", value=0, step=1, key="in_req_amount")
        with p3: st.text_input("자금사용용도", key="in_fund_purpose")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("7. 인증현황")
        ac1,ac2,ac3,ac4 = st.columns(4)
        with ac1: st.checkbox("소상공인확인서", key="in_chk_1"); st.checkbox("창업확인서", key="in_chk_2")
        with ac2: st.checkbox("여성기업확인서", key="in_chk_3"); st.checkbox("이노비즈", key="in_chk_4")
        with ac3: st.checkbox("벤처인증", key="in_chk_6"); st.checkbox("뿌리기업확인서", key="in_chk_7")
        with ac4: st.checkbox("ISO인증", key="in_chk_10")

        st.markdown("<br>", unsafe_allow_html=True)
        st.header("8. 비즈니스 정보")
        st.text_area("[아이템]", key="in_item_desc")
        st.markdown("**[주거래처 정보]**")
        cli1,cli2,cli3 = st.columns(3)
        with cli1: st.text_input("거래처 1", key="in_client_1")
        with cli2: st.text_input("거래처 2", key="in_client_2")
        with cli3: st.text_input("거래처 3", key="in_client_3")
        st.text_area("[판매루트]", key="in_sales_route")
        st.text_area("[시장현황]", key="in_market_status")
        st.text_area("[차별화]", key="in_diff_point")
        st.text_area("[앞으로의 계획]", key="in_future_plan")
        st.markdown("<br>", unsafe_allow_html=True)
        st.success("✅ 세팅 완료! 좌측에 API 키 저장하시고 상단 버튼을 클릭해 주십시오.")

show_main_app()
