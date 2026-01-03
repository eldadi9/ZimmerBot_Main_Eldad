"""
Email Service for ZimmerBot
Handles sending booking confirmations, receipts, reminders, and notifications
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

# Email configuration from .env
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)


class EmailService:
    """
    Service for sending emails related to bookings
    """
    
    def __init__(self):
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.smtp_user = SMTP_USER
        self.smtp_password = SMTP_PASSWORD
        self.email_from = EMAIL_FROM
        self.is_configured = bool(SMTP_USER and SMTP_PASSWORD)
        
        if not self.is_configured:
            print("Warning: Email service not configured. Set SMTP_USER and SMTP_PASSWORD in .env")
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> bool:
        """
        Send an email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text email body (optional)
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured:
            print(f"Email service not configured. Would send to {to_email}: {subject}")
            return False
        
        if not to_email or not to_email.strip():
            print(f"No email address provided")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add text and HTML parts
            if text_body:
                text_part = MIMEText(text_body, 'plain', 'utf-8')
                msg.attach(text_part)
            
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            print(f"Email sent successfully to {to_email}: {subject}")
            return True
            
        except Exception as e:
            print(f"Error sending email to {to_email}: {e}")
            return False
    
    def send_booking_confirmation(
        self,
        customer_email: str,
        customer_name: str,
        booking_id: str,
        cabin_name: str,
        cabin_area: str,
        check_in: str,
        check_out: str,
        adults: int,
        kids: int,
        total_price: float,
        event_link: Optional[str] = None,
        cabin_address: Optional[str] = None,
        cabin_coordinates: Optional[str] = None
    ) -> bool:
        """
        Send booking confirmation email with summary
        """
        # Create Google Maps and Waze links
        maps_links = ""
        if cabin_address or cabin_coordinates:
            if cabin_coordinates:
                lat, lon = cabin_coordinates.split(',')
                google_maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                waze_url = f"https://waze.com/ul?ll={lat},{lon}&navigate=yes"
            elif cabin_address:
                encoded_address = urllib.parse.quote(cabin_address)
                google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
                waze_url = f"https://waze.com/ul?q={encoded_address}&navigate=yes"
            
            maps_links = f"""
            <div style="margin-top: 20px; padding: 15px; background: #e3f2fd; border-radius: 8px;">
              <h3 style="margin-top: 0; color: #1976d2;">📍 מיקום הצימר</h3>
              {f'<p><strong>כתובת:</strong> {cabin_address}</p>' if cabin_address else ''}
              <p>
                <a href="{google_maps_url}" target="_blank" style="display: inline-block; margin: 5px; padding: 10px 15px; background: #4285f4; color: white; text-decoration: none; border-radius: 5px;">
                  🗺️ פתח ב-Google Maps
                </a>
                <a href="{waze_url}" target="_blank" style="display: inline-block; margin: 5px; padding: 10px 15px; background: #33ccff; color: white; text-decoration: none; border-radius: 5px;">
                  🧭 פתח ב-Waze
                </a>
              </p>
            </div>
            """
        
        html_body = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="he">
        <head>
          <meta charset="UTF-8">
          <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4caf50; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
            .info-box {{ background: white; padding: 15px; margin: 10px 0; border-radius: 5px; border-right: 4px solid #4caf50; }}
            .price {{ font-size: 24px; color: #4caf50; font-weight: bold; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>✅ הזמנתך אושרה!</h1>
            </div>
            <div class="content">
              <p>שלום {customer_name},</p>
              <p>הזמנתך התקבלה בהצלחה! להלן פרטי ההזמנה:</p>
              
              <div class="info-box">
                <h3>פרטי ההזמנה</h3>
                <p><strong>מספר הזמנה:</strong> {booking_id[:8]}...</p>
                <p><strong>צימר:</strong> {cabin_name}</p>
                <p><strong>אזור:</strong> {cabin_area}</p>
                <p><strong>Check-in:</strong> {check_in}</p>
                <p><strong>Check-out:</strong> {check_out}</p>
                <p><strong>מבוגרים:</strong> {adults}</p>
                <p><strong>ילדים:</strong> {kids}</p>
                <p class="price">סכום כולל: {total_price} ILS</p>
              </div>
              
              {maps_links}
              
              {f'<p><a href="{event_link}" target="_blank">📅 פתח ביומן Google Calendar</a></p>' if event_link else ''}
              
              <p>נשמח לראותך!</p>
              <p>צוות ZimmerBot</p>
            </div>
          </div>
        </body>
        </html>
        """
        
        subject = f"אישור הזמנה - {cabin_name}"
        return self.send_email(customer_email, subject, html_body)
    
    def send_payment_receipt(
        self,
        customer_email: str,
        customer_name: str,
        booking_id: str,
        cabin_name: str,
        payment_amount: float,
        payment_method: str,
        transaction_id: Optional[str] = None
    ) -> bool:
        """
        Send payment receipt/invoice after successful payment
        """
        html_body = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="he">
        <head>
          <meta charset="UTF-8">
          <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #2196F3; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
            .receipt-box {{ background: white; padding: 20px; margin: 10px 0; border-radius: 5px; border: 2px solid #2196F3; }}
            .price {{ font-size: 28px; color: #2196F3; font-weight: bold; text-align: center; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>🧾 קבלת תשלום</h1>
            </div>
            <div class="content">
              <p>שלום {customer_name},</p>
              <p>תודה על התשלום! להלן פרטי הקבלה:</p>
              
              <div class="receipt-box">
                <h3 style="text-align: center; margin-top: 0;">קבלה</h3>
                <p><strong>מספר הזמנה:</strong> {booking_id[:8]}...</p>
                {f'<p><strong>מספר עסקה:</strong> {transaction_id}</p>' if transaction_id else ''}
                <p><strong>צימר:</strong> {cabin_name}</p>
                <p><strong>שיטת תשלום:</strong> {payment_method}</p>
                <p class="price">{payment_amount} ILS</p>
                <p style="text-align: center; color: #666; font-size: 12px;">תאריך: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
              </div>
              
              <p>הקבלה נשמרה במערכת ותוכל למצוא אותה בפאנל הניהול.</p>
              <p>נשמח לראותך!</p>
              <p>צוות ZimmerBot</p>
            </div>
          </div>
        </body>
        </html>
        """
        
        subject = f"קבלת תשלום - {cabin_name}"
        return self.send_email(customer_email, subject, html_body)
    
    def send_reminder(
        self,
        customer_email: str,
        customer_name: str,
        booking_id: str,
        cabin_name: str,
        cabin_area: str,
        check_in: str,
        cabin_address: Optional[str] = None,
        cabin_coordinates: Optional[str] = None
    ) -> bool:
        """
        Send reminder email 2 days before check-in
        """
        # Create Google Maps and Waze links
        maps_links = ""
        if cabin_address or cabin_coordinates:
            if cabin_coordinates:
                lat, lon = cabin_coordinates.split(',')
                google_maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                waze_url = f"https://waze.com/ul?ll={lat},{lon}&navigate=yes"
            elif cabin_address:
                encoded_address = urllib.parse.quote(cabin_address)
                google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
                waze_url = f"https://waze.com/ul?q={encoded_address}&navigate=yes"
            
            maps_links = f"""
            <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 8px;">
              <h3 style="margin-top: 0; color: #856404;">📍 מיקום הצימר</h3>
              {f'<p><strong>כתובת:</strong> {cabin_address}</p>' if cabin_address else ''}
              <p>
                <a href="{google_maps_url}" target="_blank" style="display: inline-block; margin: 5px; padding: 10px 15px; background: #4285f4; color: white; text-decoration: none; border-radius: 5px;">
                  🗺️ פתח ב-Google Maps
                </a>
                <a href="{waze_url}" target="_blank" style="display: inline-block; margin: 5px; padding: 10px 15px; background: #33ccff; color: white; text-decoration: none; border-radius: 5px;">
                  🧭 פתח ב-Waze
                </a>
              </p>
            </div>
            """
        
        html_body = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="he">
        <head>
          <meta charset="UTF-8">
          <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #ff9800; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
            .reminder-box {{ background: white; padding: 15px; margin: 10px 0; border-radius: 5px; border-right: 4px solid #ff9800; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>⏰ תזכורת - ההזמנה שלך מתקרבת!</h1>
            </div>
            <div class="content">
              <p>שלום {customer_name},</p>
              <p>זו תזכורת ידידותית שההזמנה שלך מתקרבת!</p>
              
              <div class="reminder-box">
                <h3>פרטי ההזמנה</h3>
                <p><strong>צימר:</strong> {cabin_name}</p>
                <p><strong>אזור:</strong> {cabin_area}</p>
                <p><strong>תאריך הגעה:</strong> {check_in}</p>
              </div>
              
              {maps_links}
              
              <p>אנו מצפים לראותך בקרוב!</p>
              <p>צוות ZimmerBot</p>
            </div>
          </div>
        </body>
        </html>
        """
        
        subject = f"תזכורת - ההזמנה שלך מתקרבת - {cabin_name}"
        return self.send_email(customer_email, subject, html_body)


# Global instance
_email_service: Optional[EmailService] = None

def get_email_service() -> EmailService:
    """Get or create email service instance"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service

