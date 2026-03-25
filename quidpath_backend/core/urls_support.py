from django.urls import path
from quidpath_backend.core.views.support import contact_support, send_feedback

urlpatterns = [
    path('contact/', contact_support, name='contact_support'),
    path('feedback/', send_feedback, name='send_feedback'),
]
