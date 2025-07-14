# core/utils/json_response.py
from django.http import JsonResponse
def standard_response(data, status=200):
    return JsonResponse({'data': data}, status=status)

def error_response(message, status=400):
    return JsonResponse({'error': message}, status=status)

def success_response(message, status=200):
    return JsonResponse({'success': message}, status=status)

def not_found_response(message, status=404):
    return JsonResponse({'not_found': message}, status=status)

def unauthorized_response(message, status=401):
    return JsonResponse({'unauthorized': message}, status=status)

def forbidden_response(message, status=403):
    return JsonResponse({'forbidden': message}, status=status)

def conflict_response(message, status=409):
    return JsonResponse({'conflict': message}, status=status)

def server_error_response(message, status=500):
    return JsonResponse({'server_error': message}, status=status)

def bad_request_response(message, status=400):
    return JsonResponse({'bad_request': message}, status=status)

def method_not_allowed_response(message, status=405):
    return JsonResponse({'method_not_allowed': message}, status=status)

def not_acceptable_response(message, status=406):
    return JsonResponse({'not_acceptable': message}, status=status)

def request_timeout_response(message, status=408):
    return JsonResponse({'request_timeout': message}, status=status)

def length_required_response(message, status=411):
    return JsonResponse({'length_required': message}, status=status)

def precondition_failed_response(message, status=412):
    return JsonResponse({'precondition_failed': message}, status=status)

def payload_too_large_response(message, status=413):
    return JsonResponse({'payload_too_large': message}, status=status)

def uri_too_long_response(message, status=414):
    return JsonResponse({'uri_too_long': message}, status=status)

def unsupported_media_type_response(message, status=415):
    return JsonResponse({'unsupported_media_type': message}, status=status)

def range_not_satisfiable_response(message, status=416):
    return JsonResponse({'range_not_satisfiable': message}, status=status)

def expectation_failed_response(message, status=417):
    return JsonResponse({'expectation_failed': message}, status=status)

def misdirected_request_response(message, status=421):
    return JsonResponse({'misdirected_request': message}, status=status)

def unprocessable_entity_response(message, status=422):
    return JsonResponse({'unprocessable_entity': message}, status=status)

def locked_response(message, status=423):
    return JsonResponse({'locked': message}, status=status)

def failed_dependency_response(message, status=424):
    return JsonResponse({'failed_dependency': message}, status=status)

