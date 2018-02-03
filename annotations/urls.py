
from django.conf import settings
from django.conf.urls import url
from django.contrib import admin
from django.urls import path, include
from base.views import CustomLoginView, logout_view, signup
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path(r'tasks/', include('base.urls', namespace="base")),
    url(r'accounts/login/$', CustomLoginView.as_view(), name='login'),
    url(r'logout/$', logout_view, name='logout'),
    url(r'^signup/$', signup, name='signup'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
