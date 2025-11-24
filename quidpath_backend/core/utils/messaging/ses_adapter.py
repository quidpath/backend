# AWS SES email adapter
import boto3
import logging
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError

from .base import MessagingAdapter

logger = logging.getLogger(__name__)


class SESAdapter(MessagingAdapter):
    """
    AWS SES email adapter for sending emails.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.aws_access_key_id = config.get('aws_access_key_id')
        self.aws_secret_access_key = config.get('aws_secret_access_key')
        self.aws_region = config.get('aws_region', 'us-east-1')
        self.from_email = config.get('from_email', 'noreply@quidpath.com')
        
        # Initialize SES client
        self.ses_client = boto3.client(
            'ses',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region
        )
    
    def send(
        self,
        to: str,
        message: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send email via AWS SES.
        
        Args:
            to: Recipient email address
            message: HTML message content
            subject: Email subject
            metadata: Additional metadata (cc, bcc, attachments, etc.)
        """
        if not subject:
            subject = metadata.get('subject', 'Notification') if metadata else 'Notification'
        
        # Build email parameters
        destination = {
            'ToAddresses': [to]
        }
        
        if metadata:
            if 'cc' in metadata:
                destination['CcAddresses'] = metadata['cc'] if isinstance(metadata['cc'], list) else [metadata['cc']]
            if 'bcc' in metadata:
                destination['BccAddresses'] = metadata['bcc'] if isinstance(metadata['bcc'], list) else [metadata['bcc']]
        
        message_body = {
            'Html': {
                'Charset': 'UTF-8',
                'Data': message
            }
        }
        
        # Add text version if provided
        if metadata and 'text_message' in metadata:
            message_body['Text'] = {
                'Charset': 'UTF-8',
                'Data': metadata['text_message']
            }
        
        email_params = {
            'Source': self.from_email,
            'Destination': destination,
            'Message': {
                'Subject': {
                    'Charset': 'UTF-8',
                    'Data': subject
                },
                'Body': message_body
            }
        }
        
        # Add reply-to if provided
        if metadata and 'reply_to' in metadata:
            email_params['ReplyToAddresses'] = metadata['reply_to'] if isinstance(metadata['reply_to'], list) else [metadata['reply_to']]
        
        try:
            response = self.ses_client.send_email(**email_params)
            message_id = response.get('MessageId', '')
            
            logger.info(f"Email sent successfully: {message_id} to {to}")
            return {
                'status': 'success',
                'provider_reference': message_id,
                'message': 'Email sent successfully'
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"Failed to send email: {error_code} - {error_message}")
            return {
                'status': 'failed',
                'provider_reference': None,
                'message': f"Failed to send email: {error_message}",
                'error_code': error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return {
                'status': 'failed',
                'provider_reference': None,
                'message': f"Unexpected error: {str(e)}"
            }
    
    def send_bulk(
        self,
        recipients: List[str],
        message: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send bulk emails via AWS SES.
        Uses SES send_bulk_templated_email for better performance.
        """
        if not subject:
            subject = metadata.get('subject', 'Notification') if metadata else 'Notification'
        
        # For bulk, we'll send individual emails
        # In production, consider using SES templates for better performance
        results = []
        for recipient in recipients:
            result = self.send(recipient, message, subject, metadata)
            results.append({
                'recipient': recipient,
                **result
            })
        
        # Count successes and failures
        success_count = sum(1 for r in results if r['status'] == 'success')
        failed_count = len(results) - success_count
        
        return {
            'status': 'completed',
            'total': len(results),
            'success': success_count,
            'failed': failed_count,
            'results': results
        }
    
    def get_status(
        self,
        provider_reference: str
    ) -> Dict[str, Any]:
        """
        Get email delivery status from SES.
        Note: SES doesn't provide direct status queries.
        Use SNS notifications for delivery status.
        """
        # SES doesn't support direct status queries
        # Status is available via SNS notifications (bounce, complaint, delivery)
        return {
            'provider_reference': provider_reference,
            'status': 'unknown',
            'message': 'SES delivery status is available via SNS notifications'
        }








