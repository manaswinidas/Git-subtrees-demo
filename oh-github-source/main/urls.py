from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('complete/', views.complete, name='complete'),
    path('github_complete/', views.github_complete, name='github_complete'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('update_data/', views.update_data, name='update_data'),
    path('remove_github/', views.remove_github, name='remove_github')
]
