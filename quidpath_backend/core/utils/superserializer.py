import datetime
import decimal
from uuid import UUID
from django.db.models.query import QuerySet
from django.db.models import Model

def format_pretty_datetime(dt):
    if isinstance(dt, datetime.datetime):
        # Format: July 29, 2025, 1:27 a.m.
        month = dt.strftime('%B')
        day = dt.day
        year = dt.year
        hour = dt.strftime('%I').lstrip("0") or "12"
        minute = dt.strftime('%M')
        am_pm = dt.strftime('%p').lower().replace('am', 'a.m.').replace('pm', 'p.m.')
        return f"{month} {day}, {year}, {hour}:{minute} {am_pm}"
    elif isinstance(dt, datetime.date):
        return dt.strftime('%B %d, %Y')
    return dt

def json_super_serializer(obj):
    if isinstance(obj, UUID):
        return str(obj)

    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return format_pretty_datetime(obj)

    elif isinstance(obj, decimal.Decimal):
        return float(obj)

    elif isinstance(obj, QuerySet):
        return list(obj.values())

    elif isinstance(obj, Model):
        if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
            return obj.to_dict()
        else:
            return {field.name: getattr(obj, field.name) for field in obj._meta.fields}

    elif hasattr(obj, '__str__'):
        return str(obj)

    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
