from django.urls import path
from . import views

app_name = 'accounts'
urlpatterns = [
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('signup/', views.signup, name='signup'),
    # path('profile/<username>/', views.profile, name='profile'),
    path('<int:user_pk>/follow/', views.follow, name='follow'),
    path('kakao/login/', views.kakao_login, name='kakao_login'),
    path('naver/login/', views.naver_login, name='naver_login'),
    path('google/callback/', views.google_callback, name='google_callback'),
    path('profile/' , views.user_profile, name='user_profile'),
    path('user-delete/', views.user_delete, name='user_delete'),
    path('allergies/', views.allergy_list, name='allergy_list'),
    # 자체 회원 비밀번호 변경
    path('change-password/', views.change_password, name='change_password'),
]
