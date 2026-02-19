from django.shortcuts import render
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from courses.models import Course
from django.core.paginator import Paginator
from django.http import JsonResponse

@login_required
def course_chat_room(request, course_id):
    try:
        # retrieve course with given id joined by the current user
        course = request.user.courses_joined.get(id=course_id)
    except Course.DoesNotExist:
        #user is not a student of the course or course does not exist
        return HttpResponseForbidden()
    # Load the most recent 100 messages initially
    # We order by sent_on descending to get newest first, then reverse in template/JS
    latest_messages = course.chat_messages.all().order_by('-sent_on')[:100]
    latest_messages = reversed(latest_messages)
    return render(request, 'chat/room.html', {'course': course, 'latest_messages': latest_messages})


@login_required
def chat_history(request, course_id):
    """
    AJAX view to fetch older messages for infinite scroll.
    """
    try:
        # retrieve course with given id joined by the current user
        course = request.user.courses_joined.get(id=course_id)
    except Course.DoesNotExist:
        #user is not a student of the course or course does not exist
        return HttpResponseForbidden()
    
    page_number = request.GET.get('page')
    
    # Get all messages ordered by newest first
    # 100 per page to match your requirement
    messages_list = course.chat_messages.all().order_by('-sent_on')
    paginator = Paginator(messages_list, 100) 
    
    try:
        messages_page = paginator.page(page_number)
    except:
        # If page is out of range (e.g. 9999), return empty
        return JsonResponse({'messages': [], 'has_next': False})

    data = []
    # We need to reverse them here so they appear in chronological order 
    # when prepended to the chat window (oldest at top of this chunk)
    for msg in reversed(messages_page.object_list):
        data.append({
            'user': msg.user.username,
            'content': msg.content,
            'sent_on': msg.sent_on.strftime('%b %d, %I:%M %p'),
            'is_me': msg.user == request.user
        })

    return JsonResponse({
        'messages': data,
        'has_next': messages_page.has_next()
    })