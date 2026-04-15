from django.urls import path
from quidpath_backend.core.views.support import contact_support, send_feedback, send_contact_email

urlpatterns = [
    path('contact/', contact_support, name='contact_support'),
    path('feedback/', send_feedback, name='send_feedback'),
    path('send-email/', send_contact_email, name='send_contact_email'),
]
