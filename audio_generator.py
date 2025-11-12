"""
سیستم تبدیل متن به صدا (Text-to-Speech)
"""
import os
from typing import Optional
from datetime import datetime


class AudioGenerator:
    def __init__(self, output_dir='audio_outputs', language='fa', voice='default'):
        """
        مقداردهی اولیه تولیدکننده صدا
        
        Args:
            output_dir: پوشه خروجی فایل‌های صوتی
            language: زبان (fa برای فارسی)
            voice: نوع صدا
        """
        self.output_dir = output_dir
        self.language = language
        self.voice = voice
        
        # ایجاد پوشه خروجی
        os.makedirs(output_dir, exist_ok=True)
    
    def text_to_speech(self, text: str, filename: Optional[str] = None) -> str:
        """
        تبدیل متن به فایل صوتی
        
        Args:
            text: متن برای تبدیل
            filename: نام فایل خروجی (اختیاری)
            
        Returns:
            مسیر فایل صوتی تولید شده
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'summary_{timestamp}.mp3'
        
        filepath = os.path.join(self.output_dir, filename)
        
        # تلاش برای استفاده از gTTS (Google Text-to-Speech)
        try:
            return self._generate_with_gtts(text, filepath)
        except ImportError:
            print("gTTS نصب نشده است. تلاش برای استفاده از pyttsx3...")
            try:
                return self._generate_with_pyttsx3(text, filepath)
            except ImportError:
                print("pyttsx3 نیز نصب نشده است. استفاده از روش جایگزین...")
                return self._generate_with_alternative(text, filepath)
    
    def _generate_with_gtts(self, text: str, filepath: str) -> str:
        """استفاده از Google Text-to-Speech"""
        from gtts import gTTS
        
        # تبدیل به mp3
        tts = gTTS(text=text, lang=self.language, slow=False)
        tts.save(filepath)
        
        print(f"فایل صوتی با gTTS ایجاد شد: {filepath}")
        return filepath
    
    def _generate_with_pyttsx3(self, text: str, filepath: str) -> str:
        """استفاده از pyttsx3 (پشتیبانی محدود از فارسی)"""
        import pyttsx3
        
        engine = pyttsx3.init()
        
        # تنظیمات صدا
        if self.language == 'fa':
            # تلاش برای تنظیم زبان فارسی (ممکن است پشتیبانی نشود)
            voices = engine.getProperty('voices')
            for voice in voices:
                if 'persian' in voice.name.lower() or 'farsi' in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    break
        
        engine.setProperty('rate', 150)  # سرعت گفتار
        engine.setProperty('volume', 0.9)  # حجم صدا
        
        # ذخیره به فایل
        engine.save_to_file(text, filepath.replace('.mp3', '.wav'))
        engine.runAndWait()
        
        print(f"فایل صوتی با pyttsx3 ایجاد شد: {filepath.replace('.mp3', '.wav')}")
        return filepath.replace('.mp3', '.wav')
    
    def _generate_with_alternative(self, text: str, filepath: str) -> str:
        """روش جایگزین - ذخیره متن برای پردازش بعدی"""
        # ذخیره متن در فایل برای استفاده بعدی
        text_file = filepath.replace('.mp3', '.txt')
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"متن در فایل ذخیره شد: {text_file}")
        print("برای تبدیل به صدا، لطفاً از سرویس TTS خارجی استفاده کنید.")
        return text_file
    
    def generate_summary_audio(self, summary_data: dict, alert_id: str) -> str:
        """
        تولید فایل صوتی از خلاصه
        
        Args:
            summary_data: دیکشنری شامل خلاصه و نکات کلیدی
            alert_id: شناسه اعلان
            
        Returns:
            مسیر فایل صوتی
        """
        # ترکیب خلاصه و نکات کلیدی
        audio_text = f"خلاصه: {summary_data.get('summary', '')}\n\n"
        audio_text += "نکات کلیدی:\n"
        
        key_points = summary_data.get('key_points', [])
        for i, point in enumerate(key_points, 1):
            audio_text += f"{i}. {point}\n"
        
        filename = f"alert_{alert_id}_{datetime.now().strftime('%Y%m%d')}.mp3"
        return self.text_to_speech(audio_text, filename)


if __name__ == '__main__':
    # تست
    generator = AudioGenerator()
    test_text = "این یک تست برای سیستم تبدیل متن به صدا است."
    result = generator.text_to_speech(test_text)
    print(f"فایل صوتی ایجاد شد: {result}")
