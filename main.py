"""
برنامه اصلی برای پردازش خودکار اعلان‌های گوگل
"""
import os
import json
from datetime import datetime
from email_monitor import GmailMonitor
from summarizer import LLMSummarizer
from audio_generator import AudioGenerator
from visual_generator import VisualGenerator
from notebook_generator import NotebookGenerator


class GoogleAlertsProcessor:
    def __init__(self, config_file='config.json'):
        """
        مقداردهی اولیه پردازشگر اعلان‌های گوگل
        
        Args:
            config_file: مسیر فایل تنظیمات
        """
        self.config = self._load_config(config_file)
        
        # مقداردهی اولیه کامپوننت‌ها
        self.email_monitor = GmailMonitor(
            credentials_path=self.config.get('gmail_credentials', 'credentials.json'),
            token_path=self.config.get('gmail_token', 'token.pickle')
        )
        
        self.summarizer = LLMSummarizer(
            api_key=self.config.get('openai_api_key'),
            model=self.config.get('llm_model', 'gpt-4'),
            use_openai=self.config.get('use_openai', True)
        )
        
        self.audio_generator = AudioGenerator(
            output_dir=self.config.get('audio_output_dir', 'audio_outputs'),
            language=self.config.get('tts_language', 'fa')
        )
        
        self.visual_generator = VisualGenerator(
            output_dir=self.config.get('visual_output_dir', 'visual_outputs')
        )
        
        self.notebook_generator = NotebookGenerator(
            notebook_path=self.config.get('notebook_path', 'google_alerts_summary.ipynb')
        )
        
        # فایل برای ذخیره آخرین تاریخ بررسی
        self.last_check_file = self.config.get('last_check_file', 'last_check.json')
    
    def _load_config(self, config_file: str) -> dict:
        """بارگذاری تنظیمات از فایل"""
        default_config = {
            'gmail_credentials': 'credentials.json',
            'gmail_token': 'token.pickle',
            'openai_api_key': os.getenv('OPENAI_API_KEY'),
            'llm_model': 'gpt-4',
            'use_openai': True,
            'audio_output_dir': 'audio_outputs',
            'visual_output_dir': 'visual_outputs',
            'tts_language': 'fa',
            'notebook_path': 'google_alerts_summary.ipynb',
            'last_check_file': 'last_check.json'
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _get_last_check_date(self) -> datetime:
        """دریافت آخرین تاریخ بررسی"""
        if os.path.exists(self.last_check_file):
            with open(self.last_check_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                last_date_str = data.get('last_check', '')
                if last_date_str:
                    try:
                        return datetime.fromisoformat(last_date_str)
                    except:
                        pass
        return None
    
    def _save_last_check_date(self, date: datetime):
        """ذخیره آخرین تاریخ بررسی"""
        with open(self.last_check_file, 'w', encoding='utf-8') as f:
            json.dump({'last_check': date.isoformat()}, f, indent=2)
    
    def process_alerts(self):
        """پردازش اعلان‌های جدید"""
        print("شروع پردازش اعلان‌های گوگل...")
        
        # احراز هویت
        print("در حال احراز هویت با Gmail...")
        self.email_monitor.authenticate()
        
        # دریافت اعلان‌های جدید
        last_check = self._get_last_check_date()
        print(f"دریافت اعلان‌های جدید از {last_check if last_check else 'همیشه'}...")
        alerts = self.email_monitor.get_new_alerts(last_check)
        
        if not alerts:
            print("هیچ اعلان جدیدی یافت نشد.")
            return
        
        print(f"تعداد {len(alerts)} اعلان جدید یافت شد.")
        
        # پردازش هر اعلان
        processed_alerts = []
        
        for i, alert in enumerate(alerts, 1):
            print(f"\nپردازش اعلان {i}/{len(alerts)}: {alert.get('subject', 'بدون عنوان')}")
            
            try:
                # تولید خلاصه
                print("  - تولید خلاصه...")
                summary = self.summarizer.summarize(alert.get('body', ''))
                
                # تولید فایل صوتی
                print("  - تولید فایل صوتی...")
                alert_id = alert.get('id', f'alert_{i}')
                audio_path = self.audio_generator.generate_summary_audio(summary, alert_id)
                
                # تولید تصویر خلاصه
                print("  - تولید تصویر خلاصه...")
                image_path = self.visual_generator.generate_summary_image(
                    summary, alert, alert_id
                )
                
                # ذخیره داده‌های پردازش شده
                processed_alert = {
                    'alert_data': alert,
                    'summary': summary,
                    'audio_path': audio_path,
                    'image_path': image_path,
                    'processed_at': datetime.now().isoformat()
                }
                processed_alerts.append(processed_alert)
                
                print(f"  ✓ اعلان پردازش شد")
                
            except Exception as e:
                print(f"  ✗ خطا در پردازش اعلان: {e}")
                continue
        
        # به‌روزرسانی نوت‌بوک
        if processed_alerts:
            print("\nبه‌روزرسانی نوت‌بوک...")
            
            # بارگذاری اعلان‌های قبلی (اگر وجود داشته باشد)
            existing_alerts = []
            alerts_data_file = 'alerts_data.json'
            if os.path.exists(alerts_data_file):
                with open(alerts_data_file, 'r', encoding='utf-8') as f:
                    existing_alerts = json.load(f)
            
            # اضافه کردن اعلان‌های جدید
            all_alerts = processed_alerts + existing_alerts
            
            # ذخیره داده‌ها
            self.notebook_generator.save_alerts_data(all_alerts)
            
            # ایجاد/به‌روزرسانی نوت‌بوک
            self.notebook_generator.create_notebook(all_alerts)
            
            # ذخیره آخرین تاریخ بررسی
            self._save_last_check_date(datetime.now())
            
            print(f"\n✓ پردازش کامل شد. {len(processed_alerts)} اعلان جدید پردازش شد.")
        else:
            print("\nهیچ اعلانی پردازش نشد.")


def main():
    """تابع اصلی"""
    processor = GoogleAlertsProcessor()
    processor.process_alerts()


if __name__ == '__main__':
    main()
