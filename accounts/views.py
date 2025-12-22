from django.http.response import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authentication import TokenAuthentication
import requests
from .models import Allergy
from django.conf import settings
from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import get_user_model
from rest_framework import status
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes,authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.views.decorators.http import (
    require_POST,
)
from .serializers import SignupSerializer,UserProfileSerializer,AllergySerializer
from django.utils.crypto import get_random_string
from django.contrib.auth import update_session_auth_hash
import os
from dotenv import load_dotenv
load_dotenv()

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
    
@csrf_exempt
@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_delete(request):
    user = request.user
    user.delete()
    return Response(
        {"message": "회원 탈퇴가 완료되었습니다. 그동안 이용해주셔서 감사합니다."}, 
        status=status.HTTP_204_NO_CONTENT
    )



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

        if 'allergies' in request.data:
            user.allergies.set(request.data.get('allergies'))
            
        user.save()
        
        return Response({
            'message': '수정 완료',
            'nickname': user.first_name,
            'allergies': list(user.allergies.values_list('id', flat=True))
        })
# -------------------------------------------------------------------
# --------------자체 회원 비밀번호 변경 ----------------------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    # 소셜 로그인 사용자는 비밀번호 변경 불가 처리
    if user.provider != 'local':
        return Response({"error": "소셜 로그인 계정은 비밀번호를 변경할 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    # 기존 비밀번호 확인
    if not user.check_password(current_password):
        return Response({"error": "현재 비밀번호가 일치하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)

    # 새 비밀번호 설정
    user.set_password(new_password)
    user.save()
    
    # 비밀번호 변경 후 로그인 세션 유지 (토큰 방식이어도 권장됨)
    update_session_auth_hash(request, user)
    
    return Response({"message": "비밀번호가 성공적으로 변경되었습니다."}, status=status.HTTP_200_OK)
# ----------------------------------------------------------------------------


# --------------------------------------------------------------------
@api_view(['GET'])
@permission_classes([AllowAny]) # 누구나 목록은 볼 수 있게 설정
def allergy_list(request):
    """
    DB에 등록된 모든 알러지 성분 목록을 반환합니다.
    """
    allergies = Allergy.objects.all()
    serializer = AllergySerializer(allergies, many=True)
    return Response(serializer.data)
# --------------------------------------------------------------------



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

    REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
    REDIRECT_URI = "http://localhost:5173/login/kakao"

    token_res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": REST_API_KEY,
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
        headers={"Content-type": "application/x-www-form-urlencoded;charset=utf-8"},
        verify=False
    )
    
    access_token = token_res.json().get("access_token")
    if not access_token:
        return Response({'error': '카카오 토큰 발급 실패'}, status=status.HTTP_400_BAD_REQUEST)

    user_info_res = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {access_token}"},
        verify=False
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
    
    CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
    CLIENT_SECRET = os.getenv("NAVER_SECRET_KEY")

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

# ------구글 연동---------------------------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def google_callback(request):
    code = request.data.get('code')
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_KEY") # 🚩 본인의 Client Secret 입력
    redirect_uri = "http://localhost:5173/login/google"

    # 1. 구글 엑세스 토큰 요청
    token_res = requests.post("https://oauth2.googleapis.com/token", data={
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    })
    token_data = token_res.json()
    google_access_token = token_data.get('access_token')

    if not google_access_token:
        return Response({'error': '구글 토큰 발급 실패', 'detail': token_data}, status=400)

    # 2. 구글 유저 정보 가져오기 (이메일 확인용)
    user_info = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={'Authorization': f'Bearer {google_access_token}'}
    ).json()
    email = user_info.get('email')

    # 🚩 [핵심] 이미 로그인된 사용자(카카오/네이버 등)가 연동을 시도한 경우
    if request.user.is_authenticated:
        token, _ = Token.objects.get_or_create(user=request.user)
        return Response({
            'status': 'linked',
            'token': token.key,
            'nickname': request.user.first_name,
            'id': request.user.id,
            'google_access_token': google_access_token
        }, status=200)

    # 3. 로그인되지 않은 상태에서 구글로 시작하는 경우 (기존 로직)
    username = f"google_{email.split('@')[0]}"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'first_name': user_info.get('name', 'GoogleUser'),
            'password': get_random_string(32)
        }
    )
    
    django_token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'status': 'login',
        'token': django_token.key,
        'nickname': user.first_name,
        'username': user.username,
        'id': user.id,
        'google_access_token': google_access_token
    }, status=200)
# --------------------------------------------------------------------
# def profile(request, username):
#     User = get_user_model()
#     person = User.objects.get(username=username)
#     context = {
#         'person': person,
#     }
#     return render(request, 'accounts/profile.html', context)