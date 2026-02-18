import json
from channels.generic.websocket import  AsyncWebsocketConsumer
from django.utils import timezone

from chat.models import Message

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.course_id = self.scope['url_route']['kwargs']['course_id']
        self.room_group_name = 'chat_%s' % self.course_id
        #join room group
        await self.channel_layer.group_add(
            self.room_group_name, self.channel_name
        )
        #accept connection
        await self.accept()
    async def disconnect(self, close_code):
        #leave room group
        
        await self.channel_layer.group_discard (
            self.room_group_name, self.channel_name
        )
        
    async def persist_message(self, message):
    #send message to WebSocket
    
        await Message.objects.acreate(
            user=self.user,
            course_id=self.course_id,
            content=message
        )
    #Recieve message from Websocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        now = timezone.now()
        #send message to room group
        await self.channel_layer.group_send (
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'user': self.user.username,
                'datetime': now.isoformat(),
            }
        )
        #persist message
        await self.persist_message(message)
        #receive message from room group
    async def chat_message(self, event):
        #send message to wobsocket
        
        await self.send(text_data=json.dumps(event))
    

    