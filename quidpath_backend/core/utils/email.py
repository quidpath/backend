# core/utils/email.py
from django.core.mail import send_mail
def send_email(subject, message, recipient_list):
    send_mail(subject, message, 'from@example.com', recipient_list)