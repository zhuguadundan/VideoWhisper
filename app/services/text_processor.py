import openai
import google.generativeai as genai
from typing import Dict, Any, Optional, List
from app.config.settings import Config

class TextProcessor:
    def __init__(self, openai_config=None, gemini_config=None):
        if openai_config:
            self.openai_config = openai_config
        else:
            self.openai_config = Config.get_api_config('openai')
            
        if gemini_config:
            self.gemini_config = gemini_config
        else:
            self.gemini_config = Config.get_api_config('gemini')
        
        # 初始化 OpenAI Client
        self.openai_client = None
        if self.openai_config.get('api_key'):
            try:
                self.openai_client = openai.OpenAI(
                    api_key=self.openai_config['api_key'],
                    base_url=self.openai_config.get('base_url')
                )
            except TypeError as e:
                # 如果遇到proxies参数错误，尝试不使用base_url
                if 'proxies' in str(e):
                    self.openai_client = openai.OpenAI(
                        api_key=self.openai_config['api_key']
                    )
                else:
                    raise e
        
        # 初始化 Gemini
        if self.gemini_config.get('api_key'):
            # 如果配置了自定义base_url，设置为环境变量
            if self.gemini_config.get('base_url'):
                import os
                os.environ['GOOGLE_AI_STUDIO_API_URL'] = self.gemini_config['base_url']
            
            genai.configure(api_key=self.gemini_config['api_key'])
            self.gemini_model = genai.GenerativeModel(
                self.gemini_config.get('model', 'gemini-pro')
            )
    
    def process_with_openai(self, text: str, prompt_template: str, 
                          model: Optional[str] = None) -> str:
        """使用OpenAI处理文本"""
        if not self.openai_client:
            raise ValueError("OpenAI API密钥未配置")
        
        if not model:
            model = self.openai_config.get('model', 'gpt-4')
        
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt_template},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"OpenAI处理失败: {e}")
    
    def process_with_gemini(self, text: str, prompt_template: str) -> str:
        """使用Gemini处理文本"""
        if not self.gemini_config.get('api_key'):
            raise ValueError("Gemini API密钥未配置")
        
        try:
            full_prompt = f"{prompt_template}\n\n文本内容：\n{text}"
            response = self.gemini_model.generate_content(full_prompt)
            return response.text.strip()
            
        except Exception as e:
            raise Exception(f"Gemini处理失败: {e}")
    
    def generate_transcript(self, raw_text: str, provider: str = 'openai') -> str:
        """生成格式化的逐字稿"""
        prompt = """请将以下语音转文字的原始文本整理成格式规范的逐字稿。要求：
1. 修正语音识别可能的错误
2. 添加适当的标点符号
3. 分段处理，使内容更易读
4. 保持原意不变
5. 如果有明显的口语化表达，适当转换为书面语

请直接输出整理后的逐字稿，不要添加额外说明。"""
        
        if provider.lower() == 'openai':
            return self.process_with_openai(raw_text, prompt)
        elif provider.lower() == 'gemini':
            return self.process_with_gemini(raw_text, prompt)
        else:
            raise ValueError(f"不支持的服务提供商: {provider}")
    
    def generate_summary(self, transcript: str, provider: str = 'openai') -> Dict[str, str]:
        """生成总结报告"""
        prompts = {
            'brief_summary': """请为以下逐字稿生成一个简洁的摘要（200字以内）：

要求：
- 提取核心要点
- 语言简洁明了
- 突出重要信息

请直接输出摘要，不要添加额外说明。""",
            
            'detailed_summary': """请为以下逐字稿生成一份详细的总结报告，包含以下部分：

## 主要内容概述
（用2-3段话概括主要内容）

## 关键要点
（列出3-5个关键要点，使用项目符号）

## 重要细节
（补充重要的细节信息）

## 结论或建议
（如果适用，提供结论或建议）

请按照上述格式输出，使用Markdown格式。""",
            
            'keywords': """请从以下逐字稿中提取10-15个关键词，要求：
- 涵盖主要主题
- 包含重要概念
- 适合用作标签

请以逗号分隔的格式输出关键词，不要添加其他内容。"""
        }
        
        results = {}
        
        for summary_type, prompt in prompts.items():
            try:
                if provider.lower() == 'openai':
                    results[summary_type] = self.process_with_openai(transcript, prompt)
                elif provider.lower() == 'gemini':
                    results[summary_type] = self.process_with_gemini(transcript, prompt)
                else:
                    raise ValueError(f"不支持的服务提供商: {provider}")
            except Exception as e:
                results[summary_type] = f"生成失败: {e}"
        
        return results
    
    def analyze_content(self, transcript: str, provider: str = 'openai') -> Dict[str, Any]:
        """内容分析"""
        prompt = """请对以下逐字稿进行内容分析，输出JSON格式的结果：

{
    "content_type": "内容类型（如：教育、娱乐、新闻、会议等）",
    "main_topics": ["主题1", "主题2", "主题3"],
    "sentiment": "情感倾向（积极/中性/消极）",
    "language_style": "语言风格（正式/非正式/学术等）",
    "estimated_difficulty": "内容难度等级（初级/中级/高级）",
    "target_audience": "目标受众"
}

请只输出JSON，不要添加其他内容。"""
        
        try:
            if provider.lower() == 'openai':
                result = self.process_with_openai(transcript, prompt)
            elif provider.lower() == 'gemini':
                result = self.process_with_gemini(transcript, prompt)
            else:
                raise ValueError(f"不支持的服务提供商: {provider}")
            
            # 尝试解析JSON
            import json
            return json.loads(result)
            
        except json.JSONDecodeError:
            return {"error": "JSON解析失败", "raw_result": result}
        except Exception as e:
            return {"error": f"分析失败: {e}"}

if __name__ == "__main__":
    # 测试代码
    try:
        processor = TextProcessor()
        print("文本处理器初始化成功")
    except Exception as e:
        print(f"初始化失败: {e}")