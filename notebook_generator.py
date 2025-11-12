"""
ایجاد و به‌روزرسانی نوت‌بوک Jupyter با نتایج
"""
import json
import os
from datetime import datetime
from typing import Dict, List


class NotebookGenerator:
    def __init__(self, notebook_path='google_alerts_summary.ipynb'):
        """
        مقداردهی اولیه تولیدکننده نوت‌بوک
        
        Args:
            notebook_path: مسیر فایل نوت‌بوک
        """
        self.notebook_path = notebook_path
    
    def create_notebook(self, alerts_data: List[Dict]):
        """
        ایجاد یا به‌روزرسانی نوت‌بوک با داده‌های اعلان
        
        Args:
            alerts_data: لیست دیکشنری‌های شامل داده‌های اعلان، خلاصه، صدا و تصویر
        """
        notebook = {
            "cells": [],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {
                    "name": "python",
                    "version": "3.8.0"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }
        
        # سلول عنوان
        notebook["cells"].append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# خلاصه اعلان‌های گوگل\n",
                f"\n",
                f"**تاریخ به‌روزرسانی:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
                f"\n",
                f"**تعداد اعلان‌ها:** {len(alerts_data)}\n"
            ]
        })
        
        # سلول کد برای نمایش خلاصه
        notebook["cells"].append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "source": [
                "import json\n",
                "from IPython.display import display, HTML, Audio, Image\n",
                "import os\n",
                "\n",
                "# بارگذاری داده‌ها\n",
                f"with open('alerts_data.json', 'r', encoding='utf-8') as f:\n",
                "    alerts_data = json.load(f)\n"
            ]
        })
        
        # برای هر اعلان، ایجاد سلول‌های نمایش
        for i, alert in enumerate(alerts_data, 1):
            # سلول عنوان اعلان
            notebook["cells"].append({
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"## اعلان {i}: {alert.get('alert_data', {}).get('subject', 'بدون عنوان')}\n",
                    f"\n",
                    f"**تاریخ:** {alert.get('alert_data', {}).get('date', '')}\n",
                    f"**از:** {alert.get('alert_data', {}).get('from', '')}\n"
                ]
            })
            
            # سلول نمایش خلاصه
            summary = alert.get('summary', {}).get('summary', '')
            notebook["cells"].append({
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "### خلاصه:\n",
                    f"{summary}\n"
                ]
            })
            
            # سلول نمایش نکات کلیدی
            key_points = alert.get('summary', {}).get('key_points', [])
            if key_points:
                points_text = "\n".join([f"- {point}" for point in key_points])
                notebook["cells"].append({
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "### نکات کلیدی:\n",
                        f"{points_text}\n"
                    ]
                })
            
            # سلول نمایش صدا
            audio_path = alert.get('audio_path', '')
            if audio_path and os.path.exists(audio_path):
                notebook["cells"].append({
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "source": [
                        f"# پخش خلاصه صوتی\n",
                        f"Audio('{audio_path}')"
                    ]
                })
            
            # سلول نمایش تصویر
            image_path = alert.get('image_path', '')
            if image_path and os.path.exists(image_path):
                notebook["cells"].append({
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "source": [
                        f"# نمایش خلاصه تصویری\n",
                        f"display(Image('{image_path}'))"
                    ]
                })
            
            # جداکننده
            notebook["cells"].append({
                "cell_type": "markdown",
                "metadata": {},
                "source": ["---\n"]
            })
        
        # ذخیره نوت‌بوک
        with open(self.notebook_path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, ensure_ascii=False, indent=2)
        
        print(f"نوت‌بوک ایجاد/به‌روزرسانی شد: {self.notebook_path}")
    
    def save_alerts_data(self, alerts_data: List[Dict], filename='alerts_data.json'):
        """ذخیره داده‌های اعلان‌ها در فایل JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(alerts_data, f, ensure_ascii=False, indent=2)
        print(f"داده‌ها ذخیره شدند: {filename}")


if __name__ == '__main__':
    # تست
    generator = NotebookGenerator()
    test_data = [{
        'alert_data': {
            'subject': 'تست اعلان',
            'date': '2024-01-01',
            'from': 'test@example.com'
        },
        'summary': {
            'summary': 'این یک خلاصه تست است.',
            'key_points': ['نکته 1', 'نکته 2']
        },
        'audio_path': 'audio_outputs/test.mp3',
        'image_path': 'visual_outputs/test.png'
    }]
    generator.create_notebook(test_data)
