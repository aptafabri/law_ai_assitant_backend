
# import os
# from dotenv import load_dotenv
# from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
# from core.config import settings
# import asyncio
# import smtplib as smtp

# SENDER_GMAIL = settings.MAIL_FROM
# SENDER_GMAIL_PASSWORD = settings.MAIL_PASSWORD
# dirname = os.path.dirname(__file__)
# templates_folder = os.path.join(dirname, '../email_template')

# print(SENDER_GMAIL, SENDER_GMAIL_PASSWORD)
# # conf = ConnectionConfig(
# #     MAIL_USERNAME = SENDER_GMAIL,
# #     MAIL_PASSWORD = SENDER_GMAIL_PASSWORD,
# #     MAIL_FROM = SENDER_GMAIL,
# #     MAIL_PORT = 587,
# #     MAIL_SERVER = "smtp.gmail.com",
# #     MAIL_STARTTLS = True,
# #     MAIL_SSL_TLS = False,
# #     USE_CREDENTIALS = True,
# #     VALIDATE_CERTS = False,
# #     TEMPLATE_FOLDER = templates_folder,
# # )

# conf = ConnectionConfig(
#     MAIL_USERNAME =SENDER_GMAIL,
#     MAIL_PASSWORD =  SENDER_GMAIL_PASSWORD,
#     MAIL_FROM = SENDER_GMAIL,
#     MAIL_PORT = 465,
#     MAIL_SERVER = "smtp.gmail.com",
#     MAIL_STARTTLS = False,
#     MAIL_SSL_TLS = True,
#     USE_CREDENTIALS = True,
#     VALIDATE_CERTS = True,
#     TEMPLATE_FOLDER= templates_folder
# )


# async def send_reset_password_mail(recipient_email, user_name, verify_code):
#     template_body = {
#         "user_name": user_name,
#         "verify_code": verify_code
#     }
#     print('start')
#     try:
#         message = MessageSchema(
#             subject="FastAPI forgot password application reset password",
#             recipients=[recipient_email],
#             template_body=template_body,
#             subtype=MessageType.html
#         )
#         print("message",message)
#         print(conf)
#         fm = FastMail(conf)
#         print(fm)
#         await fm.send_message(message, template_name="reset_password_email.html")
#     except Exception as e:
#        print("Error:", e)