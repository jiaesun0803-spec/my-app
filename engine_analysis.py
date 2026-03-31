import google.generativeai as genai

def run_report(api_key, data):
    """
    제공된 데이터를 기반으로 (주)대박컴퍼니 스타일의 전문 HTML 기업분석리포트를 생성합니다.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 리포트 구성을 위한 아주 상세한 프롬프트 설정
    prompt = f"""
    당신은 대한민국 최고의 기업 경영 컨설턴트입니다. 
    아래 [기업 데이터]를 정밀 분석하여, 전문가용 'AI 기업분석리포트'를 HTML 형식으로 작성하세요.
    반드시 제공된 [디자인 및 구성 지시사항]을 엄격히 준수해야 합니다.

    [기업 데이터]
    {data}

    [디자인 및 구성 지시사항]
    1. 전체 스타일: 
       - 폰트: 'Malgun Gothic', sans-serif 적용.
       - 레이아웃: 최대 너비 1000px, 중앙 정렬, 전문적인 여백 확보.
       - 컬러: 메인 포인트 컬러(#174EA6)와 섹션별 파스텔 배경색(SWOT, 비전 등) 사용.
    
    2. 필수 섹션 구성:
       - 섹션 1. 기업현황분석: 기업명, 사업자번호, 업종 등을 포함한 정돈된 <table> 형식. 하단에 아이템 개요 서술.
       - 섹션 2. SWOT 분석: 강점(Blue), 약점(Red), 기회(Green), 위협(Orange) 테마 박스를 2x2 형태로 구성.
       - 섹션 3. 시장현황 및 경쟁력: 불릿 포인트 요약과 자사/경쟁사A/경쟁사B 비교 분석표 포함.
       - 섹션 4. 핵심경쟁력분석: '포인트 1, 2, 3'으로 나누어 3열 그리드 박스 디자인 적용.
       - 섹션 5. 자금 사용계획: 용도(원재료, 시설, 마케팅 등), 상세내용, 예정금액을 표로 정리.
       - 섹션 6. 매출 1년 전망: 1단계~4단계 성장 로드맵 박스와 Plotly 기반의 매출 상승 곡선 스크립트 포함.
       - 섹션 7. 성장비전 및 코멘트: 단기/중기/장기 비전 박스와 AI 컨설턴트의 핵심 조언(Alert Box) 추가.

    3. 작성 규칙:
       - 모든 문장은 전문적인 비즈니스 용어를 사용하며, 명확한 개조식과 서술식을 혼용할 것.
       - 데이터에 없는 구체적인 수치(매출 목표 등)는 업종 평균과 성장성을 고려하여 '전략적으로 추정'하여 채울 것.
       - 결과물은 <!DOCTYPE html>로 시작하는 완전한 HTML 문서여야 함.
       - 프린트 시 A4 용지에 최적화되도록 CSS Media Query 적용.

    지금 바로 (주)대박컴퍼니 리포트 수준의 최상급 리포트를 생성하세요.
    """
    
    try:
        response = model.generate_content(prompt)
        # 결과에서 HTML 부분만 추출하거나 클리닝
        text = response.text
        if "```html" in text:
            text = text.split("```html")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return text
    except Exception as e:
        return f"<div>리포트 생성 중 오류가 발생했습니다: {str(e)}</div>"
