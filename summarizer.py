"""
سیستم تولید خلاصه با استفاده از LLM
"""
import os
from typing import Dict, List
import json


class LLMSummarizer:
    def __init__(self, api_key=None, model='gpt-4', use_openai=True):
        """
        مقداردهی اولیه summarizer
        
        Args:
            api_key: کلید API برای سرویس LLM
            model: نام مدل استفاده شده
            use_openai: استفاده از OpenAI یا سرویس دیگر
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        self.use_openai = use_openai
        
        if use_openai and not self.api_key:
            print("هشدار: OPENAI_API_KEY تنظیم نشده است")
    
    def summarize(self, content: str, max_length: int = 200) -> Dict[str, str]:
        """
        تولید خلاصه از محتوا
        
        Returns:
            دیکشنری شامل خلاصه و اطلاعات اضافی
        """
        if self.use_openai and self.api_key:
            return self._summarize_with_openai(content, max_length)
        else:
            # خلاصه ساده بدون API
            return self._simple_summarize(content, max_length)
    
    def _summarize_with_openai(self, content: str, max_length: int) -> Dict[str, str]:
        """استفاده از OpenAI برای تولید خلاصه"""
        try:
            import openai
            
            openai.api_key = self.api_key
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "شما یک خلاصه‌کننده حرفه‌ای هستید. محتوای ارائه شده را به فارسی خلاصه کنید و نکات کلیدی را استخراج کنید."
                    },
                    {
                        "role": "user",
                        "content": f"لطفاً این محتوا را خلاصه کنید و نکات کلیدی را استخراج کنید:\n\n{content[:4000]}"
                    }
                ],
                max_tokens=max_length,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content
            
            return {
                'summary': summary,
                'key_points': self._extract_key_points(summary),
                'model': self.model,
                'method': 'openai'
            }
        except ImportError:
            print("کتابخانه openai نصب نشده است. از خلاصه ساده استفاده می‌شود.")
            return self._simple_summarize(content, max_length)
        except Exception as e:
            print(f"خطا در تولید خلاصه با OpenAI: {e}")
            return self._simple_summarize(content, max_length)
    
    def _simple_summarize(self, content: str, max_length: int) -> Dict[str, str]:
        """خلاصه ساده بدون استفاده از API"""
        # تقسیم به جملات
        sentences = content.split('.')
        
        # انتخاب جملات مهم (جملات طولانی‌تر)
        important_sentences = sorted(
            sentences,
            key=lambda x: len(x),
            reverse=True
        )[:5]
        
        summary = '. '.join(important_sentences)
        
        # محدود کردن طول
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        
        return {
            'summary': summary,
            'key_points': self._extract_key_points_simple(content),
            'model': 'simple',
            'method': 'local'
        }
    
    def _extract_key_points(self, summary: str) -> List[str]:
        """استخراج نکات کلیدی از خلاصه"""
        # تقسیم به جملات و انتخاب مهم‌ترین‌ها
        sentences = [s.strip() for s in summary.split('.') if s.strip()]
        return sentences[:5]
    
    def _extract_key_points_simple(self, content: str) -> List[str]:
        """استخراج ساده نکات کلیدی"""
        sentences = [s.strip() for s in content.split('.') if s.strip()]
        # انتخاب جملات با کلمات کلیدی
        keywords = ['مهم', 'کلیدی', 'نکته', 'نتیجه', 'تاثیر']
        key_points = []
        
        for sentence in sentences[:20]:
            if any(keyword in sentence.lower() for keyword in keywords):
                key_points.append(sentence)
                if len(key_points) >= 5:
                    break
        
        return key_points[:5] if key_points else sentences[:3]
    
    def batch_summarize(self, contents: List[str]) -> List[Dict[str, str]]:
        """خلاصه کردن چند محتوا به صورت دسته‌ای"""
        summaries = []
        for content in contents:
            summaries.append(self.summarize(content))
        return summaries


if __name__ == '__main__':
    # تست
    test_content = """
    این یک متن نمونه است. این متن برای تست سیستم خلاصه‌سازی استفاده می‌شود.
    نکته مهم این است که سیستم باید بتواند محتوا را به درستی خلاصه کند.
    نتیجه نهایی باید شامل نکات کلیدی باشد.
    """
    
    summarizer = LLMSummarizer()
    result = summarizer.summarize(test_content)
    print("خلاصه:", result['summary'])
    print("\nنکات کلیدی:")
    for point in result['key_points']:
        print(f"- {point}")
