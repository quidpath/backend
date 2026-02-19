"""
WebSocket URL routing for real-time features
"""
from django.urls import re_path
from Authentication.consumers import NotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
]
