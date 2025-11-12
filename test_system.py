"""
اسکریپت تست برای بررسی عملکرد سیستم
"""
from summarizer import LLMSummarizer
from audio_generator import AudioGenerator
from visual_generator import VisualGenerator
from notebook_generator import NotebookGenerator


def test_summarizer():
    """تست سیستم خلاصه‌سازی"""
    print("تست سیستم خلاصه‌سازی...")
    summarizer = LLMSummarizer()
    
    test_text = """
    هوش مصنوعی یکی از مهم‌ترین فناوری‌های قرن بیست و یکم است. 
    این فناوری در حال تغییر نحوه زندگی و کار ماست. 
    نکته کلیدی این است که باید از آن به درستی استفاده کنیم.
    نتیجه نهایی این خواهد بود که زندگی بهتری داشته باشیم.
    """
    
    result = summarizer.summarize(test_text)
    print(f"✓ خلاصه: {result['summary'][:100]}...")
    print(f"✓ نکات کلیدی: {len(result['key_points'])} نکته")
    return result


def test_audio_generator():
    """تست سیستم تولید صدا"""
    print("\nتست سیستم تولید صدا...")
    generator = AudioGenerator()
    
    test_text = "این یک تست برای سیستم تبدیل متن به صدا است."
    result = generator.text_to_speech(test_text, "test_audio.mp3")
    print(f"✓ فایل صوتی ایجاد شد: {result}")
    return result


def test_visual_generator():
    """تست سیستم تولید تصویر"""
    print("\nتست سیستم تولید تصویر...")
    generator = VisualGenerator()
    
    test_summary = {
        'summary': 'این یک خلاصه تست است که برای بررسی عملکرد سیستم استفاده می‌شود.',
        'key_points': ['نکته اول: تست', 'نکته دوم: بررسی', 'نکته سوم: عملکرد']
    }
    
    test_alert = {
        'subject': 'تست اعلان گوگل',
        'date': '2024-01-15',
        'from': 'googlealerts-noreply@google.com'
    }
    
    result = generator.generate_summary_image(test_summary, test_alert, 'test_001')
    print(f"✓ تصویر ایجاد شد: {result}")
    return result


def test_notebook_generator():
    """تست سیستم تولید نوت‌بوک"""
    print("\nتست سیستم تولید نوت‌بوک...")
    generator = NotebookGenerator('test_notebook.ipynb')
    
    test_data = [{
        'alert_data': {
            'subject': 'تست اعلان',
            'date': '2024-01-15',
            'from': 'test@example.com'
        },
        'summary': {
            'summary': 'این یک خلاصه تست است.',
            'key_points': ['نکته 1', 'نکته 2']
        },
        'audio_path': 'audio_outputs/test_audio.mp3',
        'image_path': 'visual_outputs/summary_test_001_20240115.png'
    }]
    
    generator.create_notebook(test_data)
    print(f"✓ نوت‌بوک ایجاد شد: test_notebook.ipynb")
    return 'test_notebook.ipynb'


if __name__ == '__main__':
    print("=" * 60)
    print("تست سیستم پردازش اعلان‌های گوگل")
    print("=" * 60)
    
    try:
        summary = test_summarizer()
        audio = test_audio_generator()
        visual = test_visual_generator()
        notebook = test_notebook_generator()
        
        print("\n" + "=" * 60)
        print("✓ تمام تست‌ها با موفقیت انجام شد!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ خطا در تست: {e}")
        import traceback
        traceback.print_exc()
