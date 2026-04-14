"""
Reusable server-side pagination and search utility.

Usage in any list view:
    from quidpath_backend.core.utils.pagination import paginate_queryset, apply_search

    # 1. Get all records (list of dicts from ServiceRegistry)
    records = registry.database(model_name="Invoices", operation="filter", data={...})

    # 2. Apply search
    records = apply_search(records, search_term, fields=["number", "customer_id"])

    # 3. Paginate
    page_data = paginate_queryset(records, request)
    # page_data = {"results": [...], "total": N, "page": X, "page_size": Y, "total_pages": Z}
"""
from typing import Any, Dict, List, Optional


DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200


def apply_search(records: List[Dict], search: Optional[str], fields: List[str]) -> List[Dict]:
    """
    Filter a list of dicts by checking if `search` appears (case-insensitive)
    in any of the specified `fields`.
    """
    if not search or not search.strip():
        return records
    term = search.strip().lower()
    result = []
    for rec in records:
        for field in fields:
            val = rec.get(field)
            if val is not None and term in str(val).lower():
                result.append(rec)
                break
    return result


def paginate_queryset(records: List[Any], request) -> Dict:
    """
    Paginate a list of records using `page` and `page_size` query params.

    Query params:
        page      - 1-based page number (default: 1)
        page_size - records per page (default: 25, max: 200)

    Returns dict with:
        results    - sliced list for this page
        total      - total record count (after search)
        page       - current page (1-based)
        page_size  - records per page
        total_pages - total number of pages
    """
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        page_size = min(MAX_PAGE_SIZE, max(1, int(request.GET.get("page_size", DEFAULT_PAGE_SIZE))))
    except (ValueError, TypeError):
        page_size = DEFAULT_PAGE_SIZE

    total = len(records)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "results": records[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
