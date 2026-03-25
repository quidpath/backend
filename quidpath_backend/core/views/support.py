from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def contact_support(request):
    """
    Send support email to quidpath@gmail.com
    """
    try:
        name = request.data.get('name', '')
        email = request.data.get('email', '')
        subject = request.data.get('subject', '')
        message = request.data.get('message', '')
        category = request.data.get('category', 'general')
        priority = request.data.get('priority', 'medium')

        if not all([name, email, subject, message]):
            return Response(
                {'message': 'All fields are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Compose email
        email_subject = f'[{category.upper()}] [{priority.upper()}] {subject}'
        email_body = f"""
Support Request from QuidPath System

Name: {name}
Email: {email}
Category: {category}
Priority: {priority}

Subject: {subject}

Message:
{message}

---
This email was sent from the QuidPath Help & Support system.
        """

        # Send email
        try:
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['quidpath@gmail.com'],
                fail_silently=False,
            )
            
            logger.info(f'Support email sent from {email} - Subject: {subject}')
            
            return Response(
                {'message': 'Your message has been sent successfully. We will get back to you soon.'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f'Failed to send support email: {str(e)}')
            return Response(
                {'message': 'Failed to send email. Please try again or contact us directly at quidpath@gmail.com'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f'Error in contact_support: {str(e)}')
        return Response(
            {'message': 'An error occurred. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def send_feedback(request):
    """
    Send feedback email
    """
    try:
        message = request.data.get('message', '')
        rating = request.data.get('rating', None)

        if not message:
            return Response(
                {'message': 'Message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get user info if authenticated
        user_info = 'Anonymous'
        if request.user.is_authenticated:
            user_info = f'{request.user.username} ({request.user.email})'

        # Compose email
        email_subject = f'[FEEDBACK] User Feedback - Rating: {rating if rating else "N/A"}'
        email_body = f"""
User Feedback from QuidPath System

From: {user_info}
Rating: {rating if rating else "Not provided"}

Feedback:
{message}

---
This email was sent from the QuidPath Feedback system.
        """

        # Send email
        try:
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['quidpath@gmail.com'],
                fail_silently=False,
            )
            
            logger.info(f'Feedback email sent from {user_info}')
            
            return Response(
                {'message': 'Thank you for your feedback!'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f'Failed to send feedback email: {str(e)}')
            return Response(
                {'message': 'Failed to send feedback. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f'Error in send_feedback: {str(e)}')
        return Response(
            {'message': 'An error occurred. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
