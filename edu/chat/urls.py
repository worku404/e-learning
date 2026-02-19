from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('room/<int:course_id>/', views.course_chat_room, name='course_chat_room'),
    path('history/<int:course_id>/', views.chat_history, name='chat_history'), # Add this
]