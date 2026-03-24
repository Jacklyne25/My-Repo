from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout

class AcademicTimeLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'is_student') and request.user.is_student():
            if hasattr(request.user, 'is_over_time_limit') and request.user.is_over_time_limit():
                messages.error(request, "Your academic time limit has been exceeded. Please contact the Academic Registrar's office.")
                logout(request)
                return redirect('login')
        
        response = self.get_response(request)
        return response
