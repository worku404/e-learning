from . import views
from django.urls import path
app_name = 'assistant'

urlpatterns = [
    path(
        '',
        views.llm_page,
        name='llm_page'
    ),
    path('llm/generate/',
         views.llm_generate,
         name='llm_generate'
         ),
]
