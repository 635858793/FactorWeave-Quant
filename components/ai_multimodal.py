from openai import OpenAI
import base64
import pandas as pd
from loguru import logger

class AIMultimodalAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)

    def analyze_image(self, image_path: str, user_input: str = "") -> dict:
        """用OpenAI Vision分析图片内容，可结合文本分析"""
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            image_url = f"data:image/jpeg;base64,{base64_image}"

            prompt = f"请分析以下图片内容，结合用户输入：{user_input}" if user_input else "请分析以下图片内容。"

            resp = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }],
                temperature=0.2
            )
            return {"result": resp.choices[0].message.content}
        except Exception as e:
            logger.error(f"多模态图片分析失败: {e}")
            return {"error": str(e)}

    def analyze_table(self, table_path: str, user_input: str = "") -> dict:
        """用PandasAI/LLM分析表格内容，可结合文本分析"""
        try:
            df = pd.read_csv(table_path) if table_path.endswith(
                '.csv') else pd.read_excel(table_path)
            prompt = f"请分析以下表格内容，结合用户输入：{user_input}\n表格数据：{df.head(20).to_string()}"
            resp = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return {"result": resp.choices[0].message.content}
        except Exception as e:
            logger.error(f"多模态表格分析失败: {e}")
            return {"error": str(e)}

    def analyze_text(self, user_input: str) -> dict:
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": user_input}],
                temperature=0.2
            )
            return {"result": resp.choices[0].message.content}
        except Exception as e:
            logger.error(f"多模态文本分析失败: {e}")
            return {"error": str(e)}
