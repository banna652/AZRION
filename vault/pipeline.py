from django.contrib.auth import login


def login_user(strategy, backend, user=None, *args, **kwargs):
    if user and not strategy.session_get('_auth_user_id'):
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(strategy.request, user)