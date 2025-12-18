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
from django.contrib.auth import authenticate
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.views.decorators.http import (
    require_POST,
)
from .serializers import SignupSerializer
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
            'id': user.id
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
            'message': '회원가입이 완료되었습니다.'
        }, status=status.HTTP_201_CREATED)


def profile(request, username):
    User = get_user_model()
    person = User.objects.get(username=username)
    context = {
        'person': person,
    }
    return render(request, 'accounts/profile.html', context)

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
    # 1. 프론트엔드에서 보낸 인가 코드 받기
    code = request.data.get('code')
    if not code:
        return Response({'error': '코드가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    # 카카오 설정 정보 (본인의 키로 교체 필요)
    # 실제 프로젝트에서는 settings.py나 환경변수로 관리하는 것이 좋습니다.
    REST_API_KEY = "8bfc2c0375eb0ec262342e4f996b7e4d"
    REDIRECT_URI = "http://localhost:5173/login/kakao"

    # 2. 인가 코드로 카카오 'Access Token' 요청하기
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

    # 3. Access Token으로 카카오 유저 정보 가져오기
    user_info_res = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_json = user_info_res.json()
    kakao_account = user_json.get("kakao_account")
    nickname = kakao_account.get("profile").get("nickname") # 사용자의 실제 닉네임

    # 4. 유저 저장 또는 가져오기
    user, created = User.objects.get_or_create(
        username=f"kakao_{user_json.get('id')}",
        defaults={
            'email': kakao_account.get("email", ""),
            'first_name': nickname,  # 닉네임을 first_name 필드에 저장
            'password': get_random_string(32),
        }
    )

    if not created and user.first_name != nickname:
        user.first_name = nickname
        user.save()

    # 5. 우리 프로젝트 전용 토큰(DRF Token) 발급
    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'username': user.username,
        'nickname': f'kakao_{user.first_name}',
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

    # 1. 액세스 토큰 요청
    token_url = f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={code}&state={state}"
    token_res = requests.get(token_url)
    token_json = token_res.json()
    
    access_token = token_json.get('access_token')

    # 액세스 토큰이 없으면 여기서 중단하여 UnboundLocalError 방지
    if not access_token:
        print(f"네이버 토큰 발급 실패: {token_json}")
        return Response({'error': '네이버 토큰을 가져오지 못했습니다.'}, status=400)

    # 2. 유저 정보 요청 (이 부분이 실행되어야 user_res가 정의됩니다)
    user_res = requests.get(
        "https://openapi.naver.com/v1/nid/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    # 여기서 user_res를 사용하므로 위에서 반드시 정의되어야 함
    user_response_data = user_res.json().get('response') 

    if not user_response_data:
        return Response({'error': '네이버 유저 정보를 가져오지 못했습니다.'}, status=400)

    # 3. 유저 생성 및 로그인 처리
    # (이후 로직은 이전과 동일하게 닉네임 추출 및 Response 반환)
    naver_nickname = user_response_data.get('nickname', 'NaverUser')
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

    if not created:
        user.first_name = naver_nickname
        user.save()

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'username': user.username,
        'nickname': f"naver_{user.first_name}",
    })
# -------------------------------------------------------------