from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('complete/', views.complete, name='complete'),
    path('twitter_complete/', views.twitter_complete, name='twitter_complete'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('update_data/', views.update_data, name='update_data'),
    path('remove_twitter/', views.remove_twitter, name='remove_twitter')
]
