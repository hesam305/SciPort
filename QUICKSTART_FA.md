# راهنمای شروع سریع

## مراحل راه‌اندازی

### 1. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

یا استفاده از اسکریپت راه‌اندازی:

```bash
bash setup.sh
```

### 2. تنظیم Gmail API

1. به [Google Cloud Console](https://console.cloud.google.com/) بروید
2. یک پروژه جدید ایجاد کنید یا پروژه موجود را انتخاب کنید
3. در بخش "APIs & Services" > "Library"، Gmail API را جستجو و فعال کنید
4. به "APIs & Services" > "Credentials" بروید
5. روی "Create Credentials" کلیک کنید و "OAuth client ID" را انتخاب کنید
6. نوع Application را "Desktop app" انتخاب کنید
7. فایل `credentials.json` را دانلود کنید
8. فایل را در پوشه پروژه قرار دهید

### 3. تنظیم OpenAI (اختیاری اما توصیه می‌شود)

برای استفاده از خلاصه‌سازی پیشرفته:

1. به [OpenAI Platform](https://platform.openai.com/) بروید
2. یک حساب کاربری ایجاد کنید
3. از بخش API Keys، یک کلید جدید ایجاد کنید
4. کلید را به یکی از روش‌های زیر تنظیم کنید:

**روش 1: متغیر محیطی (توصیه می‌شود)**
```bash
export OPENAI_API_KEY='sk-your-api-key-here'
```

**روش 2: فایل config.json**
فایل `config.json` را باز کنید و کلید را در قسمت `openai_api_key` قرار دهید.

### 4. تست سیستم

قبل از اجرای اصلی، سیستم را تست کنید:

```bash
python test_system.py
```

این دستور تمام کامپوننت‌ها را تست می‌کند و فایل‌های نمونه ایجاد می‌کند.

### 5. اجرای برنامه

```bash
python main.py
```

در اولین اجرا، مرورگر باز می‌شود و از شما می‌خواهد به Gmail دسترسی دهید. پس از تایید، token ذخیره می‌شود و دیگر نیازی به تایید مجدد نیست.

## اجرای خودکار

برای اجرای خودکار هر روز، می‌توانید از cron استفاده کنید:

```bash
# باز کردن crontab
crontab -e

# اضافه کردن خط زیر (هر روز ساعت 9 صبح)
0 9 * * * cd /path/to/project && /usr/bin/python3 main.py >> logs/cron.log 2>&1
```

یا استفاده از systemd timer (برای سیستم‌های Linux مدرن):

فایل `/etc/systemd/user/google-alerts.service`:
```ini
[Unit]
Description=Google Alerts Processor

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /path/to/project/main.py
WorkingDirectory=/path/to/project
```

فایل `/etc/systemd/user/google-alerts.timer`:
```ini
[Unit]
Description=Run Google Alerts Processor Daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

سپس:
```bash
systemctl --user enable google-alerts.timer
systemctl --user start google-alerts.timer
```

## ساختار خروجی

پس از اجرا، فایل‌های زیر ایجاد می‌شوند:

- `google_alerts_summary.ipynb`: نوت‌بوک اصلی با تمام خلاصه‌ها
- `alerts_data.json`: داده‌های پردازش شده
- `audio_outputs/`: فایل‌های صوتی MP3
- `visual_outputs/`: تصاویر PNG خلاصه‌ها
- `last_check.json`: آخرین تاریخ بررسی

## مشاهده نتایج

برای مشاهده نتایج، نوت‌بوک Jupyter را باز کنید:

```bash
jupyter notebook google_alerts_summary.ipynb
```

یا در VS Code/Cursor، فایل `.ipynb` را باز کنید.

## عیب‌یابی

### مشکل: "credentials.json یافت نشد"
- مطمئن شوید فایل را از Google Cloud Console دانلود کرده‌اید
- نام فایل باید دقیقاً `credentials.json` باشد

### مشکل: "OPENAI_API_KEY تنظیم نشده"
- این یک هشدار است، نه خطا
- سیستم از خلاصه‌سازی ساده استفاده می‌کند
- برای خلاصه‌سازی بهتر، کلید OpenAI را تنظیم کنید

### مشکل: "gTTS نصب نشده است"
- اجرا کنید: `pip install gtts`
- یا از pyttsx3 استفاده می‌شود (پشتیبانی محدود از فارسی)

### مشکل: فایل صوتی ایجاد نمی‌شود
- اتصال اینترنت را بررسی کنید (gTTS نیاز به اینترنت دارد)
- یا از pyttsx3 استفاده کنید که آفلاین کار می‌کند

## پشتیبانی

برای سوالات و مشکلات، لطفاً issues را بررسی کنید.
