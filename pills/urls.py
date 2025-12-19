from django.urls import path
from . import views


app_name = "pills"
urlpatterns = [
    # 구글 캘린더
    path('google-calendar/', views.register_google_calendar, name='google_calendar'),
    # 카카오 캘린더 
    path('kakao-calendar/', views.register_kakao_calendar, name='kakao-calendar'),
    path("", views.index, name="index"),
    path("<int:pill_pk>/", views.detail, name="detail"),

    # 아래는 vue랑 django 연결해주는 쓰레드 목록 조회 api 새로 작성
    path("<int:pill_pk>/threads/", views.thread_list, name="thread_list"),

    # 기존의 있는 thraed/create 대신, 밑에 있는 thread_create_api로 활용
    # path('<int:pill_pk>/thread/create', views.thread_create, name='thread_create'),
    path('<int:pill_pk>/thread/create/', views.thread_create_api, name='thread_create_api'),
    
    path('categories/', views.category_list, name='category_list'),
    # path("filter-category/", views.filter_category, name="filter_category"),
    # [추가] 맞춤 추천 메인 (모든 카테고리 조회)
    path('categories/', views.category_list),
    
    # [추가] 특정 카테고리의 성분 리스트 조회
    path('categories/<int:category_id>/', views.category_detail),
    
    # [추가] 성분 상세 정보 조회
    path('substances/<int:substance_id>/', views.substance_detail),
    
    # [추가] 성분별 영양제 리스트 (필터링 포함)
    path('substances/<int:substance_id>/pills/', views.substance_pills),
    path(
        '<int:pill_pk>/thread/<int:thread_pk>/',
        views.thread_detail,
        name='thread_detail',
    ),
    path(
        '<int:pill_pk>/thread/<int:thread_pk>/update/',
        views.thread_update,
        name='thread_update',
    ),
    path(
        '<int:pill_pk>/thread/<int:thread_pk>/delete/',
        views.thread_delete,
        name='thread_delete',
    ),
    path(
        '<int:pill_pk>/thread/<int:thread_pk>/likes/',
        views.likes,
        name='likes',
    ),
     path(
        '<int:pill_pk>/comment/<int:thread_pk>/create/',
        views.create_comment,
        name='create_comment',
    ),
    path(
        '<int:pill_pk>/comment/<int:comment_pk>/delete/',
        views.delete_comment,
        name='delete_comment',
    ),

]
