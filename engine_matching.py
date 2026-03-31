import google.generativeai as genai
def run_report(api_key, data):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"금융 전문가로서 다음 데이터에 가장 적합한 [정부 정책자금]을 추천하라: {data}"
    return model.generate_content(prompt).text
