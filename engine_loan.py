import google.generativeai as genai
def run_report(api_key, data):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"정책금융기관 제출용 [융자/사업계획서 요약본]을 작성하라: {data}"
    return model.generate_content(prompt).text
