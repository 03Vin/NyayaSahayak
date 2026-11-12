from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import SignUpForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect('ask')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to NyayaSahayak, {user.username}! Your account has been created.")
            return redirect('ask')
    else:
        form = SignUpForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('ask')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.info(request, f"Welcome back, {username}!")
                next_url = request.GET.get('next', 'ask')
                return redirect(next_url)
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('home')


@login_required
def profile_view(request):
    total_queries = request.user.queries.count()
    total_notices = request.user.notice_drafts.count()
    return render(request, 'accounts/profile.html', {
        'total_queries': total_queries,
        'total_notices': total_notices,
    })
