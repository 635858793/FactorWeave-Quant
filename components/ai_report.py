from openai import OpenAI
from loguru import logger

class AIReportGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)

    def generate_report(self, obj: str, report_type: str) -> dict:
        prompt = f"请为{obj}生成{report_type}，内容包括基本面、技术面、资金面、热点、AI解读等，结构化输出。"
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return {"report": resp.choices[0].message.content}
        except Exception as e:
            logger.error(f"LLM生成报告失败: {e}")
            return {"error": str(e)}
