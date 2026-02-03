# Document attachments views
import hashlib
import logging
import os
import uuid
from decimal import Decimal

import boto3
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from Accounting.models.attachments import DocumentAttachment
from Accounting.models.audit import AuditLog
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data

logger = logging.getLogger(__name__)


# Initialize S3 client
def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


@csrf_exempt
def upload_attachment(request):
    """
    Upload a document attachment.

    POST /api/v1/accounting/attachments/upload/

    Request (multipart/form-data):
    - file: File to upload
    - content_type: Model name (e.g., 'Invoices', 'Quotation', 'PurchaseOrder')
    - object_id: UUID of the object to attach to
    - description: Optional description
    - is_public: Optional boolean (default: False)

    Response:
    {
        "code": 200,
        "message": "Attachment uploaded successfully",
        "data": {
            "attachment_id": "uuid",
            "file_url": "https://s3...",
            "file_name": "...",
            "file_size": 12345
        }
    }
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        # Get file from request
        if "file" not in request.FILES:
            return ResponseProvider(message="File is required", code=400).bad_request()

        file = request.FILES["file"]
        content_type_name = data.get("content_type")
        object_id = data.get("object_id")
        description = data.get("description", "")
        is_public = data.get("is_public", False)

        if not content_type_name or not object_id:
            return ResponseProvider(
                message="content_type and object_id are required", code=400
            ).bad_request()

        # Get corporate
        registry = ServiceRegistry()
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        # Get ContentType
        try:
            content_type = ContentType.objects.get(model=content_type_name.lower())
        except ContentType.DoesNotExist:
            return ResponseProvider(
                message=f"Invalid content_type: {content_type_name}", code=400
            ).bad_request()

        # Upload to S3
        s3_client = get_s3_client()
        bucket_name = os.environ.get("AWS_S3_BUCKET_NAME", "quidpath-attachments")

        # Generate unique file name
        file_extension = os.path.splitext(file.name)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        s3_key = f"attachments/{corporate_id}/{content_type_name}/{object_id}/{unique_filename}"

        # Calculate file hash
        file_content = file.read()
        file_hash = hashlib.sha256(file_content).hexdigest()
        file.seek(0)  # Reset file pointer

        # Upload to S3
        s3_client.upload_fileobj(
            file,
            bucket_name,
            s3_key,
            ExtraArgs={
                "ContentType": file.content_type,
                "ACL": "public-read" if is_public else "private",
            },
        )

        # Generate S3 URL
        file_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"

        # Create attachment record
        with transaction.atomic():
            attachment_data = {
                "corporate_id": corporate_id,
                "uploaded_by_id": user_id,
                "content_type_id": content_type.id,
                "object_id": object_id,
                "file_name": file.name,
                "file_url": file_url,
                "file_size": file.size,
                "mime_type": file.content_type,
                "checksum": file_hash,
                "description": description,
                "is_public": is_public,
            }

            attachment = registry.database(
                model_name="DocumentAttachment",
                operation="create",
                data=attachment_data,
            )

            # Log audit
            AuditLog.objects.create(
                corporate_id=corporate_id,
                user_id=user_id,
                action_type="CREATE",
                model_name="DocumentAttachment",
                object_id=attachment.get("id"),
                description=f"Uploaded attachment: {file.name}",
                ip_address=metadata.get("ip_address"),
            )

            TransactionLogBase.log(
                transaction_type="ATTACHMENT_UPLOADED",
                user=user,
                message=f"Attachment uploaded: {file.name}",
                state_name="Success",
                request=request,
            )

        return ResponseProvider(
            data={
                "attachment_id": attachment.get("id"),
                "file_url": file_url,
                "file_name": file.name,
                "file_size": file.size,
                "mime_type": file.content_type,
            },
            message="Attachment uploaded successfully",
            code=200,
        ).success()

    except Exception as e:
        logger.exception(f"Error uploading attachment: {e}")
        return ResponseProvider(
            message=f"Error uploading attachment: {str(e)}", code=500
        ).exception()


@csrf_exempt
def list_attachments(request):
    """
    List attachments for a document.

    POST /api/v1/accounting/attachments/list/

    Request:
    {
        "content_type": "Invoices",
        "object_id": "uuid"
    }

    Response:
    {
        "code": 200,
        "data": {
            "attachments": [...]
        }
    }
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    try:
        content_type_name = data.get("content_type")
        object_id = data.get("object_id")

        if not content_type_name or not object_id:
            return ResponseProvider(
                message="content_type and object_id are required", code=400
            ).bad_request()

        # Get corporate
        registry = ServiceRegistry()
        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        # Get ContentType
        try:
            content_type = ContentType.objects.get(model=content_type_name.lower())
        except ContentType.DoesNotExist:
            return ResponseProvider(
                message=f"Invalid content_type: {content_type_name}", code=400
            ).bad_request()

        # Get attachments
        attachments = registry.database(
            model_name="DocumentAttachment",
            operation="filter",
            data={
                "corporate_id": corporate_id,
                "content_type_id": content_type.id,
                "object_id": object_id,
            },
        )

        return ResponseProvider(
            data={"attachments": attachments},
            message="Attachments retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        logger.exception(f"Error listing attachments: {e}")
        return ResponseProvider(
            message=f"Error listing attachments: {str(e)}", code=500
        ).exception()


@csrf_exempt
def delete_attachment(request, attachment_id):
    """
    Delete an attachment.

    DELETE /api/v1/accounting/attachments/{attachment_id}/

    Response:
    {
        "code": 200,
        "message": "Attachment deleted successfully"
    }
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    try:
        registry = ServiceRegistry()
        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )

        # Get attachment
        attachment = registry.database(
            model_name="DocumentAttachment", operation="get", data={"id": attachment_id}
        )

        if not attachment:
            return ResponseProvider(
                message="Attachment not found", code=404
            ).bad_request()

        # Verify user has access (same corporate)
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        if attachment.get("corporate_id") != corporate_id:
            return ResponseProvider(
                message="Attachment not found", code=404
            ).bad_request()

        # Delete from S3
        try:
            s3_client = get_s3_client()
            bucket_name = os.environ.get("AWS_S3_BUCKET_NAME", "quidpath-attachments")
            file_url = attachment.get("file_url")
            if file_url:
                # Extract S3 key from URL
                s3_key = file_url.split(f"{bucket_name}.s3.amazonaws.com/")[-1]
                s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
        except Exception as e:
            logger.warning(f"Error deleting file from S3: {e}")
            # Continue with DB deletion even if S3 deletion fails

        # Delete attachment record
        with transaction.atomic():
            registry.database(
                model_name="DocumentAttachment",
                operation="delete",
                instance_id=attachment_id,
            )

            # Log audit
            AuditLog.objects.create(
                corporate_id=corporate_id,
                user_id=user_id,
                action_type="DELETE",
                model_name="DocumentAttachment",
                object_id=attachment_id,
                description=f"Deleted attachment: {attachment.get('file_name')}",
                ip_address=metadata.get("ip_address"),
            )

        return ResponseProvider(
            message="Attachment deleted successfully", code=200
        ).success()

    except Exception as e:
        logger.exception(f"Error deleting attachment: {e}")
        return ResponseProvider(
            message=f"Error deleting attachment: {str(e)}", code=500
        ).exception()
