"""
WebSocket consumers for real-time notifications
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    Clients connect to ws://domain/ws/notifications/
    """

    async def connect(self):
        """Handle WebSocket connection"""
        # Get user from scope (set by AuthMiddlewareStack)
        self.user = self.scope.get("user")
        
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return
        
        # Create a unique group name for this user
        self.user_group_name = f"user_{self.user.id}_notifications"
        
        # Join user-specific notification group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        # Also join corporate/organization group if user has one
        if hasattr(self.user, 'corporate_id') and self.user.corporate_id:
            self.corporate_group_name = f"corporate_{self.user.corporate_id}_notifications"
            await self.channel_layer.group_add(
                self.corporate_group_name,
                self.channel_name
            )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to notification stream'
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave user notification group
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
        
        # Leave corporate notification group
        if hasattr(self, 'corporate_group_name'):
            await self.channel_layer.group_discard(
                self.corporate_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle messages from WebSocket client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                # Respond to ping to keep connection alive
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
            elif message_type == 'mark_read':
                # Mark notification as read
                notification_id = data.get('notification_id')
                if notification_id:
                    await self.mark_notification_read(notification_id)
        except json.JSONDecodeError:
            pass

    async def notification_message(self, event):
        """
        Handle notification messages sent to the group.
        This is called when a notification is sent via channel_layer.group_send()
        """
        # Send notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))

    async def system_message(self, event):
        """Handle system-wide messages"""
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': event['message']
        }))

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark a notification as read in the database"""
        from Authentication.models.logbase import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                destination=self.user.email
            )
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False
