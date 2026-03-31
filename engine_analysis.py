import google.generativeai as genai

# [필독] 본인의 구글 API 키를 아래 따옴표 안에 넣어주세요.
API_KEY = "YOUR_ACTUAL_API_KEY_HERE"
genai.configure(api_key=API_KEY)

def generate_enterprise_report(data):
    """
    Gemini 1.5 Flash 모델을 사용하여 리포트를 생성합니다.
    에러 코드 404를 해결하기 위해 모델 경로를 업데이트했습니다.
    """
    try:
        # [핵심 수정] 404 에러 해결: 모델명을 'gemini-1.5-flash-latest'로 변경
        # 이 명칭은 구글 API에서 가장 권장하는 최신 버전 경로입니다.
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # AI에게 전달할 질문 구성
        prompt = f"""
        당신은 기업 분석 전문가입니다. 아래의 정보를 바탕으로 상세 리포트를 작성하세요.
        
        1. 기업명: {data['name']}
        2. 사업자번호: {data['biz_no']}
        3. 기업 상세: {data['description']}
        
        [요청사항]
        - 시장 경쟁력 분석, 향후 성장성, 종합 의견을 포함할 것.
        - 전문적인 톤앤매너로 작성할 것.
        - 마크다운(Markdown) 형식을 사용하여 보기 좋게 출력할 것.
        """

        # API 호출 및 결과 생성
        response = model.generate_content(prompt)
        
        if response.text:
            return response.text
        else:
            return "AI가 응답을 생성했으나 내용이 비어있습니다."

    except Exception as e:
        # 404 모델 에러나 다른 API 에러가 발생할 경우 출력
        return f"AI 분석 엔진 오류 발생: {str(e)}\n(모델 설정이나 API 키를 확인해 주세요.)"
