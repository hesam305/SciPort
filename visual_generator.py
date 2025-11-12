"""
سیستم تولید خلاصه تصویری
"""
import os
from datetime import datetime
from typing import Dict, List, Optional
import json


class VisualGenerator:
    def __init__(self, output_dir='visual_outputs'):
        """
        مقداردهی اولیه تولیدکننده تصویر
        
        Args:
            output_dir: پوشه خروجی فایل‌های تصویری
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_summary_image(self, summary_data: Dict, alert_data: Dict, 
                               alert_id: str) -> str:
        """
        تولید تصویر خلاصه از داده‌های اعلان
        
        Args:
            summary_data: دیکشنری شامل خلاصه و نکات کلیدی
            alert_data: داده‌های اصلی اعلان
            alert_id: شناسه اعلان
            
        Returns:
            مسیر فایل تصویری
        """
        # تلاش برای استفاده از matplotlib برای ایجاد اینفوگرافیک
        try:
            return self._generate_with_matplotlib(summary_data, alert_data, alert_id)
        except ImportError:
            print("matplotlib نصب نشده است. استفاده از روش جایگزین...")
            return self._generate_text_visual(summary_data, alert_data, alert_id)
    
    def _generate_with_matplotlib(self, summary_data: Dict, alert_data: Dict, 
                                   alert_id: str) -> str:
        """ایجاد اینفوگرافیک با matplotlib"""
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib import font_manager
        
        # تنظیم فونت فارسی
        try:
            # تلاش برای استفاده از فونت فارسی
            plt.rcParams['font.family'] = 'DejaVu Sans'
            plt.rcParams['axes.unicode_minus'] = False
        except:
            pass
        
        fig, ax = plt.subplots(figsize=(12, 8))
        fig.patch.set_facecolor('#f0f0f0')
        ax.axis('off')
        
        # عنوان
        title = alert_data.get('subject', 'خلاصه اعلان گوگل')
        ax.text(0.5, 0.95, title, ha='center', va='top', 
                fontsize=18, fontweight='bold', wrap=True,
                transform=ax.transAxes)
        
        # تاریخ
        date = alert_data.get('date', '')
        ax.text(0.5, 0.88, f"تاریخ: {date}", ha='center', va='top',
                fontsize=10, style='italic', transform=ax.transAxes)
        
        # خلاصه
        summary = summary_data.get('summary', '')
        ax.text(0.1, 0.75, 'خلاصه:', ha='left', va='top',
                fontsize=14, fontweight='bold', transform=ax.transAxes)
        ax.text(0.1, 0.65, summary[:500], ha='left', va='top',
                fontsize=11, wrap=True, transform=ax.transAxes)
        
        # نکات کلیدی
        key_points = summary_data.get('key_points', [])
        if key_points:
            ax.text(0.1, 0.5, 'نکات کلیدی:', ha='left', va='top',
                    fontsize=14, fontweight='bold', transform=ax.transAxes)
            
            y_pos = 0.42
            for i, point in enumerate(key_points[:5], 1):
                ax.text(0.15, y_pos, f"{i}. {point[:100]}", 
                       ha='left', va='top', fontsize=10, wrap=True,
                       transform=ax.transAxes)
                y_pos -= 0.08
        
        # اضافه کردن کادر
        rect = mpatches.Rectangle((0.05, 0.25), 0.9, 0.7,
                                 linewidth=2, edgecolor='#333', 
                                 facecolor='white', transform=ax.transAxes)
        ax.add_patch(rect)
        
        plt.tight_layout()
        
        filename = f"summary_{alert_id}_{datetime.now().strftime('%Y%m%d')}.png"
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='#f0f0f0')
        plt.close()
        
        print(f"تصویر خلاصه ایجاد شد: {filepath}")
        return filepath
    
    def _generate_text_visual(self, summary_data: Dict, alert_data: Dict,
                              alert_id: str) -> str:
        """ایجاد فایل متنی فرمت شده به عنوان جایگزین"""
        filename = f"summary_{alert_id}_{datetime.now().strftime('%Y%m%d')}.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write(f"خلاصه اعلان گوگل\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"موضوع: {alert_data.get('subject', '')}\n")
            f.write(f"تاریخ: {alert_data.get('date', '')}\n")
            f.write(f"از: {alert_data.get('from', '')}\n\n")
            f.write("-" * 60 + "\n")
            f.write("خلاصه:\n")
            f.write("-" * 60 + "\n")
            f.write(f"{summary_data.get('summary', '')}\n\n")
            f.write("-" * 60 + "\n")
            f.write("نکات کلیدی:\n")
            f.write("-" * 60 + "\n")
            
            for i, point in enumerate(summary_data.get('key_points', []), 1):
                f.write(f"{i}. {point}\n")
        
        print(f"فایل متنی خلاصه ایجاد شد: {filepath}")
        return filepath
    
    def generate_timeline_chart(self, alerts_data: List[Dict]) -> Optional[str]:
        """ایجاد نمودار زمانی از اعلان‌ها"""
        try:
            import matplotlib.pyplot as plt
            from datetime import datetime
            
            dates = []
            counts = {}
            
            for alert in alerts_data:
                date_str = alert.get('date', '')
                try:
                    # استخراج تاریخ
                    date = datetime.fromisoformat(date_str.replace('+', '+').replace('-', '-'))
                    date_key = date.strftime('%Y-%m-%d')
                    counts[date_key] = counts.get(date_key, 0) + 1
                except:
                    pass
            
            if not counts:
                return None
            
            dates = sorted(counts.keys())
            values = [counts[d] for d in dates]
            
            plt.figure(figsize=(10, 6))
            plt.bar(dates, values)
            plt.xlabel('تاریخ')
            plt.ylabel('تعداد اعلان‌ها')
            plt.title('توزیع اعلان‌های گوگل در زمان')
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            filename = f"timeline_{datetime.now().strftime('%Y%m%d')}.png"
            filepath = os.path.join(self.output_dir, filename)
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()
            
            return filepath
        except ImportError:
            return None


if __name__ == '__main__':
    # تست
    generator = VisualGenerator()
    test_summary = {
        'summary': 'این یک خلاصه تست است.',
        'key_points': ['نکته 1', 'نکته 2', 'نکته 3']
    }
    test_alert = {
        'subject': 'تست اعلان',
        'date': '2024-01-01',
        'from': 'test@example.com'
    }
    result = generator.generate_summary_image(test_summary, test_alert, 'test_001')
    print(f"تصویر ایجاد شد: {result}")
