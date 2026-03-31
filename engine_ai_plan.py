import google.generativeai as genai
def run_report(api_key, data):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"혁신 성장 전략가로서 다음 아이템 기반의 [AI 사업계획서] 초안을 작성하라: {data}"
    return model.generate_content(prompt).text
