# سیستم پردازش خودکار اعلان‌های گوگل

این سیستم به صورت خودکار اعلان‌های گوگل را از ایمیل دریافت می‌کند و آنها را به خلاصه متنی، صوتی و تصویری تبدیل می‌کند.

## ویژگی‌ها

- ✅ دریافت خودکار اعلان‌های گوگل از Gmail
- ✅ تولید خلاصه متنی با استفاده از LLM (OpenAI GPT-4)
- ✅ تبدیل خلاصه به فایل صوتی (Text-to-Speech)
- ✅ تولید خلاصه تصویری (اینفوگرافیک)
- ✅ ایجاد نوت‌بوک Jupyter برای نمایش نتایج

## نصب و راه‌اندازی

### 1. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### 2. تنظیم Gmail API

1. به [Google Cloud Console](https://console.cloud.google.com/) بروید
2. یک پروژه جدید ایجاد کنید
3. Gmail API را فعال کنید
4. Credentials ایجاد کنید (OAuth 2.0 Client ID)
5. فایل `credentials.json` را دانلود کرده و در پوشه پروژه قرار دهید

### 3. تنظیم OpenAI API (اختیاری)

اگر می‌خواهید از OpenAI برای خلاصه‌سازی استفاده کنید:

1. کلید API خود را از [OpenAI](https://platform.openai.com/api-keys) دریافت کنید
2. در فایل `config.json` قرار دهید یا به عنوان متغیر محیطی تنظیم کنید:

```bash
export OPENAI_API_KEY='your-api-key-here'
```

### 4. اجرای برنامه

```bash
python main.py
```

## ساختار پروژه

```
.
├── main.py                 # برنامه اصلی
├── email_monitor.py        # مانیتورینگ ایمیل Gmail
├── summarizer.py          # تولید خلاصه با LLM
├── audio_generator.py     # تبدیل متن به صدا
├── visual_generator.py    # تولید خلاصه تصویری
├── notebook_generator.py  # ایجاد نوت‌بوک Jupyter
├── config.json            # فایل تنظیمات
├── requirements.txt       # وابستگی‌ها
└── README.md             # این فایل
```

## استفاده

### اجرای دستی

```bash
python main.py
```

### اجرای خودکار (Cron Job)

برای اجرای خودکار هر روز، می‌توانید از cron استفاده کنید:

```bash
# ویرایش crontab
crontab -e

# اضافه کردن خط زیر برای اجرای روزانه در ساعت 9 صبح
0 9 * * * cd /path/to/project && /usr/bin/python3 main.py
```

## خروجی‌ها

پس از اجرا، فایل‌های زیر ایجاد می‌شوند:

- `google_alerts_summary.ipynb`: نوت‌بوک Jupyter با تمام خلاصه‌ها
- `alerts_data.json`: داده‌های پردازش شده به صورت JSON
- `audio_outputs/`: فایل‌های صوتی خلاصه‌ها
- `visual_outputs/`: تصاویر خلاصه‌ها
- `last_check.json`: آخرین تاریخ بررسی

## تنظیمات

می‌توانید تنظیمات را در فایل `config.json` تغییر دهید:

- `gmail_credentials`: مسیر فایل credentials گوگل
- `openai_api_key`: کلید API OpenAI (یا از متغیر محیطی)
- `llm_model`: مدل LLM استفاده شده
- `tts_language`: زبان تبدیل متن به صدا (fa برای فارسی)
- `notebook_path`: مسیر فایل نوت‌بوک

## نکات

- اگر OpenAI API ندارید، سیستم از خلاصه‌سازی ساده استفاده می‌کند
- برای تبدیل متن به صدا، gTTS (Google Text-to-Speech) استفاده می‌شود که نیاز به اتصال اینترنت دارد
- فایل‌های صوتی به فرمت MP3 ذخیره می‌شوند
- تصاویر خلاصه به فرمت PNG ذخیره می‌شوند

## پشتیبانی

در صورت بروز مشکل، لطفاً issues را بررسی کنید یا یک issue جدید ایجاد کنید.
