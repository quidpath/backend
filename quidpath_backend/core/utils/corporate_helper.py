"""
Helper utilities for handling corporate_id in requests.
"""


def get_corporate_id_from_data(data: dict) -> str | None:
    """
    Extract corporate_id from request data.
    Checks both 'corporate' and 'corporate_id' fields for compatibility.
    
    Args:
        data: Request data dictionary
        
    Returns:
        Corporate ID string or None if not found
    """
    # Check both possible field names
    corporate_id = data.get("corporate") or data.get("corporate_id")
    return corporate_id


def validate_corporate_id(data: dict, required: bool = True) -> tuple[str | None, str | None]:
    """
    Validate and extract corporate_id from request data.
    
    Args:
        data: Request data dictionary
        required: Whether corporate_id is required
        
    Returns:
        Tuple of (corporate_id, error_message)
        If valid: (corporate_id, None)
        If invalid: (None, error_message)
    """
    corporate_id = get_corporate_id_from_data(data)
    
    if required and not corporate_id:
        return None, "Corporate ID is required"
    
    return corporate_id, None
