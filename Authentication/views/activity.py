"""
Activity feed views for dashboard.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q

from Authentication.models.logbase import Transaction
from OrgAuth.models import CorporateUser


class ActivityPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# Activity type to human-readable mapping
ACTIVITY_MESSAGES = {
    "USER_LOGIN": "logged in",
    "USER_LOGOUT": "logged out",
    "USER_REGISTERED": "registered",
    "INVOICE_CREATED": "created an invoice",
    "INVOICE_LIST_SUCCESS": "viewed invoices",
    "INVOICE_UPDATED": "updated an invoice",
    "INVOICE_DELETED": "deleted an invoice",
    "EXPENSE_CREATED": "created an expense",
    "EXPENSE_LIST_SUCCESS": "viewed expenses",
    "VENDOR_CREATED": "created a vendor",
    "CUSTOMER_CREATED": "created a customer",
    "JOURNAL_ENTRY_CREATED": "created a journal entry",
    "JOURNAL_ENTRY_POSTED": "posted a journal entry",
    "BANK_ACCOUNT_CREATED": "created a bank account",
    "TRANSACTION_CREATED": "created a transaction",
    "PURCHASE_ORDER_CREATED": "created a purchase order",
    "VENDOR_BILL_CREATED": "created a vendor bill",
    "QUOTATION_CREATED": "created a quotation",
    "PAYMENT_RECORD_SUCCESS": "recorded a payment",
    "CORPORATE_USER_CREATED": "created a user",
    "CORPORATE_USER_UPDATED": "updated a user",
    "CORPORATE_USER_DELETED": "deleted a user",
    "CORPORATE_USER_SUSPENDED": "suspended a user",
    "CORPORATE_USER_UNSUSPENDED": "unsuspended a user",
    "CORPORATE_CREATED": "created an organization",
    "CORPORATE_UPDATED": "updated organization details",
}

# Activity type to category mapping for color coding
ACTIVITY_CATEGORIES = {
    "USER_LOGIN": "auth",
    "USER_LOGOUT": "auth",
    "USER_REGISTERED": "auth",
    "INVOICE_CREATED": "finance",
    "INVOICE_UPDATED": "finance",
    "INVOICE_DELETED": "finance",
    "EXPENSE_CREATED": "finance",
    "VENDOR_CREATED": "finance",
    "CUSTOMER_CREATED": "finance",
    "JOURNAL_ENTRY_CREATED": "accounting",
    "JOURNAL_ENTRY_POSTED": "accounting",
    "BANK_ACCOUNT_CREATED": "banking",
    "TRANSACTION_CREATED": "banking",
    "PURCHASE_ORDER_CREATED": "procurement",
    "VENDOR_BILL_CREATED": "procurement",
    "QUOTATION_CREATED": "sales",
    "PAYMENT_RECORD_SUCCESS": "payment",
    "CORPORATE_USER_CREATED": "admin",
    "CORPORATE_USER_UPDATED": "admin",
    "CORPORATE_USER_DELETED": "admin",
    "CORPORATE_USER_SUSPENDED": "admin",
    "CORPORATE_USER_UNSUSPENDED": "admin",
    "CORPORATE_CREATED": "admin",
    "CORPORATE_UPDATED": "admin",
}


def get_activity_type(transaction_type_name: str) -> str:
    """Map transaction type to activity category."""
    return ACTIVITY_CATEGORIES.get(transaction_type_name, "general")


def format_activity_message(transaction) -> str:
    """Format a human-readable activity message."""
    txn_type = transaction.transaction_type.name
    user_name = transaction.user.username if transaction.user else "System"
    
    # Get the action from mapping or use a default
    action = ACTIVITY_MESSAGES.get(txn_type, "performed an action")
    
    # Build the message
    message = f"{user_name} {action}"
    
    # Add additional context from the transaction message if available
    if transaction.message and len(transaction.message) < 100:
        # Extract useful info from message (e.g., invoice number, reference)
        if "reference" in transaction.message.lower() or "invoice" in transaction.message.lower():
            message += f" ({transaction.message})"
    
    return message


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_recent_activity(request):
    """
    Get recent activity feed for the authenticated user.
    
    - Superusers see all activities across all corporates
    - Regular users see only their own activities
    - Corporate admins (SUPERADMIN role) see all activities in their corporate
    
    Query params:
    - page: page number
    - page_size: items per page (default 20, max 100)
    - category: filter by category (auth, finance, accounting, banking, etc.)
    """
    try:
        user = request.user
        
        # Check if user is a system superuser
        is_system_superuser = getattr(user, "is_superuser", False)
        
        # Get user's corporate and role
        corporate_user = None
        is_corporate_admin = False
        corporate_id = None
        
        try:
            corporate_user = CorporateUser.objects.filter(id=user.id).first()
            if corporate_user:
                corporate_id = corporate_user.corporate_id
                # Check if user has SUPERADMIN role in their corporate
                if corporate_user.role and corporate_user.role.name == "SUPERADMIN":
                    is_corporate_admin = True
        except Exception:
            pass
        
        # Build queryset based on permissions
        if is_system_superuser:
            # System superuser sees everything
            queryset = Transaction.objects.all()
        elif is_corporate_admin and corporate_id:
            # Corporate admin sees all activities from users in their corporate
            corporate_users = CorporateUser.objects.filter(
                corporate_id=corporate_id
            ).values_list("id", flat=True)
            queryset = Transaction.objects.filter(
                Q(user_id__in=corporate_users) | Q(user=user)
            )
        else:
            # Regular user sees only their own activities
            queryset = Transaction.objects.filter(user=user)
        
        # Filter by category if provided
        category = request.query_params.get("category")
        if category:
            # Get all transaction types for this category
            txn_types = [
                txn_type for txn_type, cat in ACTIVITY_CATEGORIES.items()
                if cat == category
            ]
            if txn_types:
                queryset = queryset.filter(transaction_type__name__in=txn_types)
        
        # Order by most recent first
        queryset = queryset.select_related(
            "user", "transaction_type", "state"
        ).order_by("-created_at")
        
        # Paginate
        paginator = ActivityPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        # Serialize
        activities_data = []
        for txn in page:
            activity_type = get_activity_type(txn.transaction_type.name)
            
            activities_data.append({
                "id": str(txn.id),
                "message": format_activity_message(txn),
                "type": activity_type,
                "category": activity_type,
                "user": {
                    "id": str(txn.user.id) if txn.user else None,
                    "username": txn.user.username if txn.user else "System",
                    "email": txn.user.email if txn.user else None,
                },
                "transaction_type": txn.transaction_type.name,
                "state": txn.state.name,
                "created_at": txn.created_at.isoformat(),
                "source_ip": txn.source_ip,
            })
        
        return paginator.get_paginated_response(activities_data)
    
    except Exception as e:
        import traceback
        print(f"Error in get_recent_activity: {str(e)}")
        print(traceback.format_exc())
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_activity_stats(request):
    """
    Get activity statistics for the dashboard.
    Returns counts by category for the current user's scope.
    """
    try:
        user = request.user
        
        # Check permissions (same logic as get_recent_activity)
        is_system_superuser = getattr(user, "is_superuser", False)
        corporate_user = None
        is_corporate_admin = False
        corporate_id = None
        
        try:
            corporate_user = CorporateUser.objects.filter(id=user.id).first()
            if corporate_user:
                corporate_id = corporate_user.corporate_id
                if corporate_user.role and corporate_user.role.name == "SUPERADMIN":
                    is_corporate_admin = True
        except Exception:
            pass
        
        # Build queryset
        if is_system_superuser:
            queryset = Transaction.objects.all()
        elif is_corporate_admin and corporate_id:
            corporate_users = CorporateUser.objects.filter(
                corporate_id=corporate_id
            ).values_list("id", flat=True)
            queryset = Transaction.objects.filter(
                Q(user_id__in=corporate_users) | Q(user=user)
            )
        else:
            queryset = Transaction.objects.filter(user=user)
        
        # Count by category
        stats = {}
        for txn_type, category in ACTIVITY_CATEGORIES.items():
            if category not in stats:
                stats[category] = 0
            count = queryset.filter(transaction_type__name=txn_type).count()
            stats[category] += count
        
        # Total activities
        total = queryset.count()
        
        return Response({
            "total": total,
            "by_category": stats,
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        import traceback
        print(f"Error in get_activity_stats: {str(e)}")
        print(traceback.format_exc())
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
