try:
    import openai
except ImportError:
    openai = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from typing import Dict, Any, Optional, List
from app.config.settings import Config
import re

class TextProcessor:
    def __init__(self, openai_config=None, gemini_config=None, siliconflow_config=None):
        # 常量定义
        self.MAX_TOKENS_PER_REQUEST = 32000  # 大幅提高token限制以支持长视频
        self.MAX_CHARS_PER_SEGMENT = 48000  # 大幅增加每段最大字符数以减少分段
        self.TOKEN_ESTIMATE_RATIO = 1.5  # 中文字符到token的估算比例
        
        # 跟踪运行时配置的自定义提供商
        self.runtime_custom_provider = False
        
        # 初始化配置
        if openai_config:
            self.openai_config = openai_config
        else:
            self.openai_config = Config.get_api_config('openai')
            
        if gemini_config:
            self.gemini_config = gemini_config
        else:
            self.gemini_config = Config.get_api_config('gemini')
            
        if siliconflow_config:
            self.siliconflow_config = siliconflow_config
        else:
            self.siliconflow_config = Config.get_api_config('siliconflow')
        
        # 初始化 OpenAI Client
        self.openai_client = None
        if self.openai_config.get('api_key') and openai:
            try:
                self.openai_client = openai.OpenAI(
                    api_key=self.openai_config['api_key'],
                    base_url=self.openai_config.get('base_url')
                )
            except TypeError as e:
                # 如果遇到proxies参数错误，尝试不使用base_url
                if 'proxies' in str(e):
                    try:
                        self.openai_client = openai.OpenAI(
                            api_key=self.openai_config['api_key']
                        )
                    except Exception:
                        self.openai_client = None
                else:
                    self.openai_client = None
            except Exception:
                self.openai_client = None
        
        # 初始化 Gemini
        self.gemini_model = None
        if self.gemini_config.get('api_key') and genai:
            try:
                # 如果配置了自定义base_url，设置为环境变量
                if self.gemini_config.get('base_url'):
                    import os
                    os.environ['GOOGLE_AI_STUDIO_API_URL'] = self.gemini_config['base_url']
                
                genai.configure(api_key=self.gemini_config['api_key'])
                self.gemini_model = genai.GenerativeModel(
                    self.gemini_config.get('model', 'gemini-pro')
                )
            except Exception:
                self.gemini_model = None
                
        # 初始化 SiliconFlow Client (使用OpenAI兼容接口)
        self.siliconflow_client = None
        if self.siliconflow_config.get('api_key'):
            try:
                self.siliconflow_client = openai.OpenAI(
                    api_key=self.siliconflow_config['api_key'],
                    base_url=self.siliconflow_config.get('base_url', 'https://api.siliconflow.cn/v1')
                )
            except Exception:
                self.siliconflow_client = None
    
    def set_runtime_config(self, text_processor_config: dict):
        """设置运行时配置"""
        if not text_processor_config:
            return
            
        provider = text_processor_config.get('provider', 'siliconflow')
        api_key = text_processor_config.get('api_key')
        base_url = text_processor_config.get('base_url')
        model = text_processor_config.get('model')
        
        if not api_key:
            return
            
        # 根据provider更新对应的配置和客户端
        if provider == 'siliconflow':
            self.siliconflow_config = {
                'api_key': api_key,
                'base_url': base_url or 'https://api.siliconflow.cn/v1',
                'model': model or 'Qwen/Qwen3-Coder-30B-A3B-Instruct'
            }
            try:
                self.siliconflow_client = openai.OpenAI(
                    api_key=api_key,
                    base_url=self.siliconflow_config['base_url']
                )
            except Exception:
                self.siliconflow_client = None
                
        elif provider == 'custom':
            # 自定义选项使用OpenAI兼容接口
            self.openai_config = {
                'api_key': api_key,
                'base_url': base_url,
                'model': model or 'gpt-4'
            }
            try:
                self.openai_client = openai.OpenAI(
                    api_key=api_key,
                    base_url=base_url if base_url else None
                )
                # 标记为运行时自定义提供商
                self.runtime_custom_provider = True
            except Exception:
                self.openai_client = None
                self.runtime_custom_provider = False
                
        elif provider == 'gemini':
            self.gemini_config = {
                'api_key': api_key,
                'base_url': base_url,
                'model': model or 'gemini-pro'
            }
            try:
                # 如果配置了自定义base_url，设置为环境变量
                if base_url:
                    import os
                    os.environ['GOOGLE_AI_STUDIO_API_URL'] = base_url
                
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel(
                    self.gemini_config['model']
                )
            except Exception:
                self.gemini_model = None
    
    def get_available_providers(self) -> List[str]:
        """获取可用的服务提供商列表"""
        available = []
        if self.siliconflow_client:
            available.append('siliconflow')
        if self.openai_client:
            # 如果是运行时设置的自定义提供商，添加'custom'；否则添加'openai'
            if self.runtime_custom_provider:
                available.append('custom')
            else:
                available.append('openai')
        if self.gemini_model:
            available.append('gemini')
        return available
    
    def is_provider_available(self, provider: str) -> bool:
        """检查指定的服务提供商是否可用"""
        return provider.lower() in self.get_available_providers()
    
    def get_default_provider(self) -> str:
        """获取默认可用的服务提供商"""
        available = self.get_available_providers()
        if not available:
            raise ValueError("没有可用的AI文本处理服务提供商，请先配置API密钥")
        
        # 优先级：siliconflow > custom > openai > gemini
        if 'siliconflow' in available:
            return 'siliconflow'
        elif 'custom' in available:
            return 'custom'
        elif 'openai' in available:
            return 'openai'
        else:
            return available[0]
    
    def estimate_tokens(self, text: str) -> int:
        """估算文本的token数量"""
        if not text:
            return 0
        # 中文字符通常1字符=1.5-2 tokens，这里取保守估算
        return int(len(text) * self.TOKEN_ESTIMATE_RATIO)
    
    def split_text_intelligently(self, text: str, max_chars: int = None) -> List[str]:
        """智能分割长文本"""
        if not max_chars:
            max_chars = self.MAX_CHARS_PER_SEGMENT
            
        if len(text) <= max_chars:
            return [text]
        
        # 尝试按段落分割
        paragraphs = text.split('\n\n')
        segments = []
        current_segment = ""
        
        for paragraph in paragraphs:
            # 如果段落本身超过最大长度，需要进一步分割
            if len(paragraph) > max_chars:
                # 先添加当前段落（如果有）
                if current_segment.strip():
                    segments.append(current_segment.strip())
                    current_segment = ""
                
                # 按句子分割长段落
                sentences = re.split(r'[。！？.!?]', paragraph)
                sub_segment = ""
                
                for sentence in sentences:
                    if len(sub_segment + sentence) <= max_chars - 50:  # 留50字符缓冲
                        sub_segment += sentence + "。"
                    else:
                        if sub_segment.strip():
                            segments.append(sub_segment.strip())
                        sub_segment = sentence + "。"
                
                if sub_segment.strip():
                    segments.append(sub_segment.strip())
                    
            else:
                # 检查添加新段落是否会超过限制
                if len(current_segment + paragraph + "\n\n") <= max_chars:
                    current_segment += paragraph + "\n\n"
                else:
                    # 先保存当前段落
                    if current_segment.strip():
                        segments.append(current_segment.strip())
                    current_segment = paragraph + "\n\n"
        
        # 添加最后一段
        if current_segment.strip():
            segments.append(current_segment.strip())
        
        # 再次检查每个分段，确保都不超过限制
        final_segments = []
        for segment in segments:
            if len(segment) <= max_chars:
                final_segments.append(segment)
            else:
                # 如果还有超长的段落，强制分割
                chunks = [segment[i:i+max_chars] for i in range(0, len(segment), max_chars)]
                final_segments.extend(chunks)
        
        print(f"智能分段：原始文本 {len(text)} 字符，分割为 {len(final_segments)} 个段落")
        for i, segment in enumerate(final_segments):
            print(f"段落 {i+1}: {len(segment)} 字符")
        
        return final_segments
    
    def process_long_text(self, text: str, prompt_template: str, provider: str, 
                         max_chars_per_segment: int = None) -> str:
        """处理长文本的核心方法"""
        segments = self.split_text_intelligently(text, max_chars_per_segment)
        results = []
        
        for i, segment in enumerate(segments):
            print(f"处理长文本第 {i+1}/{len(segments)} 段 ({len(segment)} 字符)")
            
            try:
                if provider.lower() == 'siliconflow':
                    # 动态调整token限制
                    estimated_tokens = self.estimate_tokens(prompt_template + segment)
                    dynamic_max_tokens = min(max(estimated_tokens + 2000, 8000), self.MAX_TOKENS_PER_REQUEST)
                    
                    result = self.process_with_siliconflow(
                        segment, prompt_template, max_tokens=dynamic_max_tokens
                    )
                elif provider.lower() == 'openai' or provider.lower() == 'custom':
                    # 动态调整token限制
                    estimated_tokens = self.estimate_tokens(prompt_template + segment)
                    dynamic_max_tokens = min(max(estimated_tokens + 2000, 8000), self.MAX_TOKENS_PER_REQUEST)
                    
                    result = self.process_with_openai(
                        segment, prompt_template, max_tokens=dynamic_max_tokens
                    )
                elif provider.lower() == 'gemini':
                    result = self.process_with_gemini(segment, prompt_template)
                else:
                    raise ValueError(f"不支持的服务提供商: {provider}")
                
                results.append(result)
                print(f"第 {i+1} 段处理成功，结果长度: {len(result)} 字符")
                
            except Exception as e:
                print(f"第 {i+1} 段处理失败: {e}")
                # 如果某段处理失败，使用原始文本
                results.append(f"[段落处理失败，使用原始文本]\n\n{segment}")
        
        # 合并所有结果
        final_result = "\n\n".join(results)
        print(f"长文本处理完成：共 {len(segments)} 段，总结果长度: {len(final_result)} 字符")
        return final_result
    
    def process_with_siliconflow(self, text: str, prompt_template: str,
                               model: Optional[str] = None, max_tokens: Optional[int] = None) -> str:
        """使用SiliconFlow处理文本"""
        if not self.siliconflow_client:
            raise ValueError("SiliconFlow API密钥未配置")
        
        if not model:
            model = self.siliconflow_config.get('model', 'Qwen/Qwen3-Coder-30B-A3B-Instruct')
        
        # 动态设置token限制
        if not max_tokens:
            estimated_tokens = self.estimate_tokens(prompt_template + text)
            max_tokens = min(max(estimated_tokens + 2000, 8000), self.MAX_TOKENS_PER_REQUEST)
        
        try:
            response = self.siliconflow_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt_template},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"SiliconFlow处理失败: {e}")
    
    def process_with_openai(self, text: str, prompt_template: str, 
                          model: Optional[str] = None, max_tokens: Optional[int] = None) -> str:
        """使用OpenAI处理文本"""
        if not self.openai_client:
            raise ValueError("OpenAI API密钥未配置")
        
        if not model:
            model = self.openai_config.get('model', 'gpt-4')
        
        # 动态设置token限制
        if not max_tokens:
            estimated_tokens = self.estimate_tokens(prompt_template + text)
            max_tokens = min(max(estimated_tokens + 2000, 8000), self.MAX_TOKENS_PER_REQUEST)
        
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt_template},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=max_tokens
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
    
    def generate_transcript(self, raw_text: str, provider: str = None) -> str:
        """生成格式化的逐字稿"""
        # 如果没有指定provider或指定的provider不可用，使用默认provider
        if not provider or not self.is_provider_available(provider):
            provider = self.get_default_provider()
        
        prompt = """请将以下语音转文字的原始文本整理成格式规范的逐字稿。要求：
1. 修正语音识别可能的错误
2. 添加适当的标点符号
3. 分段处理，使内容更易读
4. 保持原意不变
5. 如果有明显的口语化表达，适当转换为书面语

请直接输出整理后的逐字稿，不要添加额外说明。"""
        
        # 检查文本长度，决定是否使用长文本处理
        estimated_tokens = self.estimate_tokens(raw_text)
        
        if estimated_tokens > self.MAX_TOKENS_PER_REQUEST - 1000:  # 留1000 tokens缓冲
            print(f"文本过长（估算 {estimated_tokens} tokens），使用智能分段处理")
            return self.process_long_text(raw_text, prompt, provider)
        else:
            print(f"文本长度适中（估算 {estimated_tokens} tokens），直接处理")
            # 短文本直接处理
            if provider.lower() == 'siliconflow':
                return self.process_with_siliconflow(raw_text, prompt)
            elif provider.lower() == 'openai' or provider.lower() == 'custom':
                return self.process_with_openai(raw_text, prompt)
            elif provider.lower() == 'gemini':
                return self.process_with_gemini(raw_text, prompt)
            else:
                raise ValueError(f"不支持的服务提供商: {provider}")
    
    def generate_summary(self, transcript: str, provider: str = None) -> Dict[str, str]:
        """生成总结报告"""
        # 如果没有指定provider或指定的provider不可用，使用默认provider
        if not provider or not self.is_provider_available(provider):
            provider = self.get_default_provider()
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
                if provider.lower() == 'siliconflow':
                    results[summary_type] = self.process_with_siliconflow(transcript, prompt)
                elif provider.lower() == 'openai' or provider.lower() == 'custom':
                    results[summary_type] = self.process_with_openai(transcript, prompt)
                elif provider.lower() == 'gemini':
                    results[summary_type] = self.process_with_gemini(transcript, prompt)
                else:
                    raise ValueError(f"不支持的服务提供商: {provider}")
            except Exception as e:
                results[summary_type] = f"生成失败: {e}"
        
        return results
    
    def analyze_content(self, transcript: str, provider: str = None) -> Dict[str, Any]:
        """内容分析"""
        # 如果没有指定provider或指定的provider不可用，使用默认provider
        if not provider or not self.is_provider_available(provider):
            provider = self.get_default_provider()
            
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
            if provider.lower() == 'siliconflow':
                result = self.process_with_siliconflow(transcript, prompt)
            elif provider.lower() == 'openai' or provider.lower() == 'custom':
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