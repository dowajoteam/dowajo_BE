from django.urls import path
from .views import RestaurantListView  # views.py 파일에서 RestaurantListView를 가져옵니다.

urlpatterns = [
    path('restaurants/', RestaurantListView.as_view(), name='restaurant-list'),

]
