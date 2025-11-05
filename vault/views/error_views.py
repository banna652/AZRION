from .common_imports import *

def error_404_page(request, exception):
    return render(request, '404.html', status=404)