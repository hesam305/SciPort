"""
سیستم مانیتورینگ ایمیل برای دریافت اعلان‌های گوگل
"""
import os
import base64
import json
from datetime import datetime
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailMonitor:
    def __init__(self, credentials_path='credentials.json', token_path='token.pickle'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        
    def authenticate(self):
        """احراز هویت با Gmail API"""
        creds = None
        
        # بررسی وجود token ذخیره شده
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # اگر token معتبر نیست، احراز هویت مجدد
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"فایل {self.credentials_path} یافت نشد. "
                        "لطفاً از Google Cloud Console دانلود کنید."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # ذخیره token برای استفاده بعدی
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('gmail', 'v1', credentials=creds)
        return self.service
    
    def search_google_alerts(self, query='from:googlealerts-noreply@google.com', max_results=10):
        """جستجوی ایمیل‌های اعلان گوگل"""
        try:
            if not self.service:
                self.authenticate()
            
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return messages
        except HttpError as error:
            print(f'خطا در دریافت ایمیل‌ها: {error}')
            return []
    
    def get_message_content(self, msg_id):
        """دریافت محتوای کامل یک ایمیل"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            payload = message['payload']
            headers = payload.get('headers', [])
            
            # استخراج اطلاعات هدر
            email_data = {
                'id': msg_id,
                'subject': '',
                'from': '',
                'date': '',
                'body': ''
            }
            
            for header in headers:
                if header['name'] == 'Subject':
                    email_data['subject'] = header['value']
                elif header['name'] == 'From':
                    email_data['from'] = header['value']
                elif header['name'] == 'Date':
                    email_data['date'] = header['value']
            
            # استخراج بدنه ایمیل
            email_data['body'] = self._extract_body(payload)
            
            return email_data
        except HttpError as error:
            print(f'خطا در دریافت محتوای ایمیل: {error}')
            return None
    
    def _extract_body(self, payload):
        """استخراج متن از بدنه ایمیل"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    body += base64.urlsafe_b64decode(data).decode('utf-8')
                elif part['mimeType'] == 'text/html':
                    data = part['body']['data']
                    html = base64.urlsafe_b64decode(data).decode('utf-8')
                    # تبدیل HTML ساده به متن
                    import re
                    body += re.sub('<[^<]+?>', '', html)
        else:
            if payload['mimeType'] == 'text/plain':
                data = payload['body']['data']
                body = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return body
    
    def get_new_alerts(self, last_check_date=None):
        """دریافت اعلان‌های جدید از آخرین بررسی"""
        messages = self.search_google_alerts()
        new_alerts = []
        
        for msg in messages:
            content = self.get_message_content(msg['id'])
            if content:
                # اگر تاریخ بررسی وجود دارد، فقط ایمیل‌های جدید را برگردان
                if last_check_date:
                    msg_date = datetime.fromisoformat(
                        content['date'].replace('+', '+').replace('-', '-')
                    )
                    if msg_date > last_check_date:
                        new_alerts.append(content)
                else:
                    new_alerts.append(content)
        
        return new_alerts


if __name__ == '__main__':
    monitor = GmailMonitor()
    alerts = monitor.get_new_alerts()
    print(f"تعداد اعلان‌های یافت شده: {len(alerts)}")
    for alert in alerts[:3]:
        print(f"\nموضوع: {alert['subject']}")
        print(f"از: {alert['from']}")
        print(f"تاریخ: {alert['date']}")
