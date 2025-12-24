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
import requests
import random
from django.core.mail import send_mail
from .models import PasswordResetCode,GoogleSocialAccount
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


@api_view(['POST'])
@permission_classes([AllowAny])
def find_id(request):
    email = request.data.get('email')
    
    if not email:
        return Response({'error': '이메일을 입력해주세요.'}, status=400)
    
    # 🚩 get() 대신 filter()를 사용해 모든 계정을 가져옵니다.
    users = User.objects.filter(email=email)
    
    if not users.exists():
        return Response({'error': '해당 이메일로 가입된 계정이 없습니다.'}, status=404)
    
    user_list = []
    for user in users:
        # 소셜 로그인 유저인지 판별 (보통 소셜 유저는 비밀번호가 없거나 특정 필드가 있습니다)
        # 여기서는 소셜 로그인 연동 방식에 따라 다르지만, 일반적으로 password가 없는 경우로 체크하거나
        # 소셜 앱 이름이 포함된 경우를 체크합니다.
        is_social = not user.has_usable_password() 
        
        user_list.append({
            'username': user.username,
            'is_social': is_social,
            'date_joined': user.date_joined.strftime('%Y-%m-%d') # 가입일 추가하면 구분하기 쉬움
        })
    
    return Response({
        'users': user_list, # 🚩 여러 개를 리스트로 보냄
        'message': '아이디를 찾았습니다.'
    }, status=200)


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

# -------구글 SMTP 함수 -----------------------------------------------
# 인증번호 발송 API
@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_send(request):
    email = request.data.get('email')
    
    if not email:
        return Response({'error': '이메일을 입력해주세요.'}, status=400)
    
    # 1. 유저 존재 여부 확인
    user = User.objects.filter(email=email).first()
    if not user:
        return Response({'error': '등록되지 않은 이메일입니다.'}, status=404)
    
    # 2. 인증코드 생성 및 저장
    auth_code = str(random.randint(100000, 999999))
    PasswordResetCode.objects.filter(email=email).delete() # 기존 코드 삭제
    PasswordResetCode.objects.create(email=email, code=auth_code)

    # 3. 메일 발송
    subject = "[PillGood] 비밀번호 재설정 인증번호"
    message = f"귀하의 인증번호는 [{auth_code}] 입니다. 5분 이내에 입력해 주세요."
    
    try:
        # settings.EMAIL_HOST_USER가 None이 아닌지 꼭 확인하세요!
        send_mail(subject, message, settings.EMAIL_HOST_USER, [email], fail_silently=False)
        return Response({'message': '인증번호가 발송되었습니다.'}, status=200)
    except Exception as e:
        # 메일 서버 연결 실패 시 에러 출력
        print(f"SMTP Error: {e}")
        return Response({'error': '메일 발송에 실패했습니다. 관리자에게 문의하세요.'}, status=500)

# ------------동일 이메일 유저 인증 후 보여 줄 아이디 리스트 -------------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_verify(request):
    email = request.data.get('email')
    code = request.data.get('code')
    
    # 1. 인증번호 유효성 검사
    reset_entry = PasswordResetCode.objects.filter(email=email, code=code).first()
    
    if not reset_entry:
        return Response({'error': '인증번호가 일치하지 않습니다.'}, status=400)
    
    if not reset_entry.is_valid():
        reset_entry.delete()
        return Response({'error': '인증번호가 만료되었습니다. 다시 시도해주세요.'}, status=400)

    # 2. 인증 성공 시, 해당 이메일과 연동된 모든 아이디(username) 찾기
    users = User.objects.filter(email=email)
    user_list = [
        {'username': u.username, 'nickname': u.first_name or u.username} 
        for u in users
    ]
    
    return Response({
        'message': '인증번호가 확인되었습니다.',
        'user_list': user_list  # 프론트엔드에서 이 목록을 사용자에게 보여줍니다.
    }, status=200)

# 인증번호 검증 및 비밀번호 변경 ---------------------------------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    email = request.data.get('email')
    code = request.data.get('code')
    username = request.data.get('username') #  프론트에서 선택된 아이디를 보냅니다.
    new_password = request.data.get('new_password')
    
    # 보안을 위해 코드 다시 확인
    reset_entry = PasswordResetCode.objects.filter(email=email, code=code).first()
    if not reset_entry or not reset_entry.is_valid():
        return Response({'error': '유효하지 않은 요청입니다.'}, status=400)

    #  정확히 이메일과 아이디가 일치하는 유저만 선택하여 변경
    try:
        user = User.objects.get(email=email, username=username)
        user.set_password(new_password)
        user.save()
        reset_entry.delete()
        return Response({'message': f'[{username}] 계정의 비밀번호가 변경되었습니다.'}, status=200)
    except User.DoesNotExist:
        return Response({'error': '일치하는 사용자 정보가 없습니다.'}, status=404)
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

# ----------------- 신규회원인지 확인 --------------------------
def check_is_new_user(user):
    """
    🚩 신규 유저(추가 정보 입력 필요) 판별 함수
    성별이나 나이 정보가 없으면 True를 반환하여 마이페이지 환영 모달을 띄우게 합니다.
    """
    if not (user.gender and user.age):
        return True
    return False
# ------------------------------------------------------------


# -------------------------------------------------------------
# 카카오 로그인 코드 
@api_view(['POST'])
@permission_classes([AllowAny])
def kakao_login(request):
    code = request.data.get('code')
    if not code:
        return Response({'error': '코드가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
    REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

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
        'is_new_user': check_is_new_user(user),
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
            
        }
    )

    # [수정] 기존 유저 덮어쓰기 로직 삭제

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'username': user.username,
        'nickname': user.first_name or user.username, # [수정] 접두사 제거
        'is_new_user': check_is_new_user(user),
        'provider': 'naver',         # [추가] 프론트 배지 표시용
    })
# -------------------------------------------------------------

# ------구글 연동---------------------------------------------
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def google_callback(request):
    code = request.data.get('code')
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_KEY")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    # 1. 구글로부터 액세스 토큰 요청
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

    # 2. 구글 유저 정보 가져오기
    user_info = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={'Authorization': f'Bearer {google_access_token}'}
    ).json()
    
    google_access_token = token_data.get('access_token')
    google_id = user_info.get('id')
    email = user_info.get('email')

    

    # 🚩 [케이스 1] 이미 로그인된 유저(자체 회원/타 소셜)가 연동을 시도하는 경우
    if request.user.is_authenticated:
        user = request.user
        status_msg = 'linked'
    else:
        # [케이스 2] 로그아웃 상태에서 구글 로그인을 시도하는 경우
        google_username = f"google_{google_id[:15]}"
        user, created = User.objects.get_or_create(
            username=google_username,
            defaults={
                'email': email,
                'first_name': user_info.get('name', 'GoogleUser'),
                'password': get_random_string(32)
            }
        )
        status_msg = 'login'
    
    GoogleSocialAccount.objects.update_or_create(
        user=user,
        defaults={
            'google_access_token': google_access_token,
            'is_linked': True  # 연동 성공 상태 기록
        }
    )

    # 장고 서비스 이용을 위한 토큰 발급
    django_token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'status': status_msg,
        'token': django_token.key,
        'nickname': user.first_name or user.username,
        'username': user.username,  # 자체 회원의 경우 원래 아이디가 반환됨
        'id': user.id,
        'is_new_user': check_is_new_user(user),
        'google_access_token': google_access_token # 프론트에서 캘린더 등록 시 사용
    }, status=200)


# ------------ 구글 캘린더 연동한 사용자의 토큰을 DB 넘기는 부분 ------------------------------
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def check_google_link(request):
    # DB에 해당 유저의 연동 데이터가 있고 is_linked가 True인지 확인
    is_linked = GoogleSocialAccount.objects.filter(user=request.user, is_linked=True).exists()
    
    return Response({'is_linked': is_linked})


# ----------- 구글 연동 해제 ------------------------------------------------------------
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def google_unlink(request):
    try:
        # 현재 유저의 연동 정보를 찾아 상태를 변경합니다.
        account = GoogleSocialAccount.objects.get(user=request.user)
        account.is_linked = False
        account.google_access_token = None  # 토큰도 함께 비워주는 것이 안전합니다.
        account.save()
        return Response({'message': '연동 해제 성공'}, status=200)
    except GoogleSocialAccount.DoesNotExist:
        return Response({'error': '연동된 계정이 없습니다.'}, status=404)
    return Response({
        'status': status_msg,
        'token': django_token.key,
        'nickname': user.first_name or user.username, # 닉네임이 없으면 아이디라도 보냄
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