from django.http.response import JsonResponse
import requests
from django.conf import settings
from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import get_user_model
from rest_framework import status
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.views.decorators.http import (
    require_POST,
)
from .serializers import SignupSerializer,UserProfileSerializer
from django.utils.crypto import get_random_string


User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        # 로그인 시 유저의 상세 정보도 함께 보내주면 프론트에서 활용하기 좋습니다.
        return Response({
            'token': token.key,
            'username': user.username,
            'id': user.id,
            'nickname': user.first_name if user.first_name else user.username
        })
    return Response({'error': '아이디 또는 비밀번호가 올바르지 않습니다.'}, status=status.HTTP_400_BAD_REQUEST)


@require_POST
def logout(request):
    auth_logout(request)
    return redirect('pills:index')


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    if serializer.is_valid(raise_exception=True):
        user = serializer.save()
        # 회원가입 후 자동 로그인 효과를 위해 토큰 생성
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'username': user.username,
            'message': '회원가입이 완료되었습니다.',
            'nickname': user.first_name if user.first_name else user.username
        }, status=status.HTTP_201_CREATED)


def profile(request, username):
    User = get_user_model()
    person = User.objects.get(username=username)
    context = {
        'person': person,
    }
    return render(request, 'accounts/profile.html', context)

# -------------------------------------------------------------------
# 프로젝트 진행 중인 , 마이페이지 기능 구현 코드
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    user = request.user
    
    if request.method == 'GET':
        serializer = UserProfileSerializer(user)
        data = serializer.data
        
        # 1. 닉네임은 접두사 없이 순수하게 first_name(또는 username)만 보냄
        data['nickname'] = user.first_name if user.first_name else user.username
        
        # 2. 로그인 제공자(provider) 정보를 별도로 추가
        if user.username.startswith("kakao_"): data['provider'] = 'kakao'
        elif user.username.startswith("naver_"): data['provider'] = 'naver'
        else: data['provider'] = 'local'
        
        return Response(data)
    
    elif request.method == 'PUT':
        # 3. 수정 시에는 받은 닉네임을 그대로 first_name에 저장
        user.first_name = request.data.get('nickname', user.first_name)
        user.email = request.data.get('email', user.email)
        user.age = request.data.get('age', user.age)
        user.gender = request.data.get('gender', user.gender)
        
        # 카테고리(장르) 저장 로직 (시리얼라이저 활용 권장)
        if 'interested_genres' in request.data:
            user.interested_genres.set(request.data.get('interested_genres'))
            
        user.save()
        
        return Response({
            'message': '수정 완료',
            'nickname': user.first_name
        })
# -------------------------------------------------------------------

@require_POST
@login_required
def follow(request, user_pk):
    User = get_user_model()
    person = get_object_or_404(User, pk=user_pk)

    if person == request.user:
        return JsonResponse({'message' : '자신은 팔로우 할 수 없습니다.'},status=400)
    
    if person.followers.filter(pk=request.user.pk).exists():
        person.followers.remove(request.user)
        is_followed = False
    else:
        person.followers.add(request.user)
        is_followed = True
    context = {
        'is_followed' : is_followed,
        'followers_count' : person.followers.count(),
        'followings_count' : person.followings.count()
    }
    return JsonResponse(context)


# -------------------------------------------------------------
# 카카오 로그인 코드 
@api_view(['POST'])
@permission_classes([AllowAny])
def kakao_login(request):
    code = request.data.get('code')
    if not code:
        return Response({'error': '코드가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    REST_API_KEY = "8bfc2c0375eb0ec262342e4f996b7e4d"
    REDIRECT_URI = "http://localhost:5173/login/kakao"

    token_res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": REST_API_KEY,
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
        headers={"Content-type": "application/x-www-form-urlencoded;charset=utf-8"}
    )
    
    access_token = token_res.json().get("access_token")
    if not access_token:
        return Response({'error': '카카오 토큰 발급 실패'}, status=status.HTTP_400_BAD_REQUEST)

    user_info_res = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_json = user_info_res.json()
    kakao_account = user_json.get("kakao_account")
    nickname = kakao_account.get("profile").get("nickname")

    # [수정] get_or_create의 defaults만 사용하여 최초 가입 시에만 이름 저장
    user, created = User.objects.get_or_create(
        username=f"kakao_{user_json.get('id')}",
        defaults={
            'email': kakao_account.get("email", ""),
            'first_name': nickname,
            'password': get_random_string(32),
        }
    )

    # [수정] if not created... user.save() 로직을 삭제하여 기존 유저 정보 보호

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'username': user.username,
        'nickname': user.first_name, # [수정] 접두사 제거하고 순수 이름만 전송
        'provider': 'kakao',         # [추가] 프론트 배지 표시용
        'message': '카카오 로그인 성공'
    })

# -------------------------------------------------------------
# 네이버 로그인 코드
# accounts/views.py

@api_view(['POST'])
@permission_classes([AllowAny])
def naver_login(request):
    code = request.data.get('code')
    state = request.data.get('state')
    
    CLIENT_ID = "tPDkW3PnoZVt6H0P8LTM"
    CLIENT_SECRET = "4S5d5jnup6"

    token_url = f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={code}&state={state}"
    token_res = requests.get(token_url)
    token_json = token_res.json()
    access_token = token_json.get('access_token')

    if not access_token:
        return Response({'error': '네이버 토큰 실패'}, status=400)

    user_res = requests.get(
        "https://openapi.naver.com/v1/nid/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_response_data = user_res.json().get('response') 

    if not user_response_data:
        return Response({'error': '유저 정보 실패'}, status=400)

    naver_nickname = user_response_data.get('nickname', 'NaverUser')
    
    # [수정] 최초 가입 시에만 정보를 저장하도록 defaults 설정
    user, created = User.objects.get_or_create(
        username=f"naver_{user_response_data.get('id')[:10]}",
        defaults={
            'first_name': naver_nickname,
            'email': user_response_data.get('email', ''),
            'password': get_random_string(32),
            'age': 20,
            'gender': 'M'
        }
    )

    # [수정] 기존 유저 덮어쓰기 로직 삭제

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'username': user.username,
        'nickname': user.first_name, # [수정] 접두사 제거
        'provider': 'naver',         # [추가] 프론트 배지 표시용
    })
# -------------------------------------------------------------