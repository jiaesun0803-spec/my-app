import google.generativeai as genai

def run_report(api_key, data):
    """
    제공된 데이터를 기반으로 전문 HTML 기업분석리포트를 생성합니다.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # AI에게 HTML 구조를 명확히 지시
    prompt = f"""
    당신은 대한민국 최고의 기업 경영 컨설턴트입니다. 
    아래 [기업 데이터]를 분석하여, 전문가용 'AI 기업분석리포트'를 HTML 형식으로 작성하세요.

    [기업 데이터]
    {data}

    [디자인 지시사항]
    1. <!DOCTYPE html>로 시작하는 완전한 HTML 문서를 작성할 것.
    2. 모든 CSS는 <style> 태그 안에 포함할 것 (폰트: Malgun Gothic, 포인트컬러: #174EA6).
    3. 테이블(Table), SWOT 분석 박스, 핵심경쟁력 그리드를 포함할 것.
    4. 매출 전망 및 자금 계획을 전문가 수준으로 추정하여 표로 정리할 것.

    [주의사항]
    - 반드시 한국어로만 작성하세요.
    - 설명 텍스트 없이 <html>...</html> 태그만 출력하세요.
    - 마크다운 기호(```html)를 사용하지 말고 순수 텍스트로 HTML 코드만 내보내세요.
    """
    
    try:
        response = model.generate_content(prompt)
        # 결과물에서 혹시 모를 마크다운 기호 제거 (안정성 강화)
        html_code = response.text.replace("```html", "").replace("```", "").strip()
        return html_code
    except Exception as e:
        return f"<div>AI 분석 엔진 오류: {str(e)}</div>"
