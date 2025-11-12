#!/bin/bash

echo "راه‌اندازی سیستم پردازش اعلان‌های گوگل..."
echo ""

# بررسی Python
if ! command -v python3 &> /dev/null; then
    echo "خطا: Python 3 نصب نشده است."
    exit 1
fi

echo "✓ Python پیدا شد"

# ایجاد محیط مجازی (اختیاری)
read -p "آیا می‌خواهید محیط مجازی ایجاد شود؟ (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 -m venv venv
    source venv/bin/activate
    echo "✓ محیط مجازی ایجاد شد"
fi

# نصب وابستگی‌ها
echo ""
echo "در حال نصب وابستگی‌ها..."
pip install -r requirements.txt

echo ""
echo "✓ نصب کامل شد"
echo ""
echo "مراحل بعدی:"
echo "1. فایل credentials.json را از Google Cloud Console دانلود کنید"
echo "2. فایل را در پوشه پروژه قرار دهید"
echo "3. (اختیاری) متغیر محیطی OPENAI_API_KEY را تنظیم کنید"
echo "4. برنامه را با دستور زیر اجرا کنید:"
echo "   python main.py"
