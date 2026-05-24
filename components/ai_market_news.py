from openai import OpenAI
import requests
from loguru import logger

class AIMarketNewsAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)

    def fetch_url_content(self, url: str) -> str:
        try:
            resp = requests.get(url, timeout=10)
            resp.encoding = resp.apparent_encoding
            return resp.text
        except Exception as e:
            logger.error(f"抓取新闻内容失败: {e}")
            return ""

    def analyze(self, user_input: str = "", url: str = "") -> dict:
        try:
            content = user_input
            if url:
                content = self.fetch_url_content(url)
            if not content:
                return {"error": "无可分析内容"}
            prompt = f"请对以下内容进行摘要、情感分析、投资建议和热点解读：\n{content[:2000]}"
            resp = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return {"result": resp.choices[0].message.content}
        except Exception as e:
            logger.error(f"AI行情/新闻解读失败: {e}")
            return {"error": str(e)}
