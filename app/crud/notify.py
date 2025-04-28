import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, To
from core.config import settings
from email_validator import validate_email, EmailNotValidError

from log_config import configure_logging

# Configure logging
logger = configure_logging(__name__)

VERIFICATION_URL = settings.VERIFICATION_URL
DOWNLOAD_URL = settings.DOWNLOAD_URL

def send_reset_password_mail(recipient_email, user_name, verify_code):
    logger.info(f"Sending reset password email to {recipient_email}")
    try:
        # Get the parent directory of the current script
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        email_template_dir = os.path.join(parent_dir, "..", "email_template")

        # Construct the relative path to the HTML file
        html_file_path = os.path.join(email_template_dir, "reset_password_email.html")

        # Open the HTML file
        with open(html_file_path, "r") as file:
            html_content = file.read()

        added_user_name = html_content.replace("user_name", user_name)
        final_html_content = added_user_name.replace("verify_code", verify_code)
        message = Mail(
            from_email=settings.SENDGRID_AUTH_EMAIL,
            to_emails=[To(recipient_email)],
            subject="Forgot Your Password",
            is_multiple=True,
            html_content=final_html_content,
        )

        sendgrid_api_key = settings.SENDGRID_API_KEY
        sg = SendGridAPIClient(api_key=sendgrid_api_key)
        response = sg.send(message)
        logger.debug(f"SendGrid response status code: {response.status_code}")
        logger.debug(f"SendGrid response body: {response.body}")
        logger.debug(f"SendGrid response headers: {response.headers}")

        logger.info(f"Reset password email sent successfully to {recipient_email}")
        return response.status_code
    except Exception as e:
        logger.error(f"Error sending reset password email to {recipient_email}: {e}")
        return None


def send_verify_email(recipient_email: str, token: str):
    logger.info(f"Sending verification email to {recipient_email}")
    try:
        message = Mail(
            from_email=settings.SENDGRID_AUTH_EMAIL,
            to_emails=[To(recipient_email)],
            subject="Verify Email",
            is_multiple=True,
            html_content=f'Please verify your email by clicking the following link: <a href="{VERIFICATION_URL}?token={token}">Verify</a>',
        )

        sendgrid_api_key = settings.SENDGRID_API_KEY
        sg = SendGridAPIClient(api_key=sendgrid_api_key)
        response = sg.send(message)
        logger.debug(f"SendGrid response status code: {response.status_code}")
        logger.debug(f"SendGrid response body: {response.body}")
        logger.debug(f"SendGrid response headers: {response.headers}")

        logger.info(f"Verification email sent successfully to {recipient_email}")
        return response.status_code
    except Exception as e:
        logger.error(f"Error sending verification email to {recipient_email}: {e}")
        return None


def send_export_email(recipient_email: str, url: str):
    logger.info(f"Sending export data email to {recipient_email}")
    try:
        message = Mail(
            from_email=settings.SENDGRID_AUTH_EMAIL,
            to_emails=[To(recipient_email)],
            subject="Export Data",
            is_multiple=True,
            html_content=f'Please download your data by clicking the following link: <a href="{url}">Download Link</a>',
        )

        sendgrid_api_key = settings.SENDGRID_API_KEY
        sg = SendGridAPIClient(api_key=sendgrid_api_key)
        response = sg.send(message)
        logger.debug(f"SendGrid response status code: {response.status_code}")
        logger.debug(f"SendGrid response body: {response.body}")
        logger.debug(f"SendGrid response headers: {response.headers}")

        logger.info(f"Export data email sent successfully to {recipient_email}")
        return response.status_code
    except Exception as e:
        logger.error(f"Error sending export data email to {recipient_email}: {e}")
        return None


def send_subscription_expiry_notification(recipient_email: str, days_remaining: int, subscription_plan: str, status_message: str):
    logger.info(f"Sending subscription expiry notification to {recipient_email}")
    try:
        # Determine subject and HTML content based on subscription status
        if days_remaining > 0:
            subject = f"Your {subscription_plan} Subscription Will Expire Soon"
            html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #ff9900;">Subscription Expiry Notice</h2>
                    <p style="font-size: 16px; line-height: 1.5;">{status_message}</p>
                    <div style="background-color: #f8f8f8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 0; color: #666;">
                            <strong>Subscription Plan:</strong> {subscription_plan}<br>
                            <strong>Days Remaining:</strong> {days_remaining}
                        </p>
                    </div>
                    <p style="font-size: 16px; line-height: 1.5;">Please renew your subscription to continue enjoying our services without interruption.</p>
                    <p style="font-size: 14px; color: #666; margin-top: 30px;">Thank you for choosing our service!</p>
                </div>
            """
        else:
            subject = f"Your {subscription_plan} Subscription Has Expired"
            html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #ff0000;">Subscription Expired</h2>
                    <p style="font-size: 16px; line-height: 1.5;">{status_message}</p>
                    <div style="background-color: #fff0f0; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 0; color: #666;">
                            <strong>Subscription Plan:</strong> {subscription_plan}<br>
                            <strong>Status:</strong> Expired
                        </p>
                    </div>
                    <p style="font-size: 16px; line-height: 1.5;">To restore access to all features, please renew your subscription as soon as possible.</p>
                    <p style="font-size: 14px; color: #666; margin-top: 30px;">Thank you for your continued support!</p>
                </div>
            """

        message = Mail(
            from_email=settings.SENDGRID_AUTH_EMAIL,
            to_emails=[To(recipient_email)],
            subject=subject,
            is_multiple=True,
            html_content=html_content
        )

        sendgrid_api_key = settings.SENDGRID_API_KEY
        sg = SendGridAPIClient(api_key=sendgrid_api_key)
        response = sg.send(message)
        logger.debug(f"SendGrid response status code: {response.status_code}")
        
        logger.info(f"Subscription expiry notification sent successfully to {recipient_email}")
        return response.status_code
    except Exception as e:
        logger.error(f"Error sending subscription expiry notification to {recipient_email}: {e}")
        return None
