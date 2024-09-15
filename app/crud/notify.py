import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, To
from core.config import settings
from email_validator import validate_email, EmailNotValidError

from log_config import configure_logging

# Configure logging
logger = configure_logging()

VERIFICATION_URL = "https://chat.adaletgpt.com/user/verify"
DOWNLOAD_URL = "https://chat.adaletgpt.com/user/exportdata"


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
