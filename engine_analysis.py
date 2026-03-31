import google.generativeai as genai
def run_report(api_key, data):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"전문 컨설턴트로서 다음 기업 데이터를 정밀 분석하여 [AI 기업분석리포트]를 작성하라: {data}"
    return model.generate_content(prompt).text
