from django.shortcuts import render

def dashboard(request):
    """Renders the main three-panel landing page."""
    return render(request, 'home/index.html')