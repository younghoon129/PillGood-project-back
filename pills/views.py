from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.authentication import TokenAuthentication
from django.views.decorators.http import (
    require_http_methods,
    require_safe,
    require_POST,
)
import json
import requests
from datetime import datetime, timedelta
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.contrib.auth.decorators import login_required
# category model 가져와야됨
from accounts.models import Category
from .models import Pill, Thread, Comment, Substance, UserPill, CustomPill,Nutrient
from .forms import ThreadForm, CommentForm
from .serializers import (
    PillListSerializer, 
    PillDetailSerializer, 
    ThreadSerializer, 
    CommentSerializer,
    CategoryWithSubstancesSerializer,
    SubstanceSerializer,
    UserPillSerializer,
    CustomPillSerializer
)
from django.db.models import Count
from django.contrib.auth import update_session_auth_hash

from .utils import get_purchase_link
from rest_framework.views import APIView
from .utils import get_pill_recommendation

# Index 페이지
# 장르별 필터링
# index, filter 합침
@api_view(['GET'])
@permission_classes([AllowAny]) # 로그인 없이도 누구나 볼 수 있게 설정
def index(request):
    pills = Pill.objects.exclude(price=-1).order_by('-pk')
    search_type = request.GET.get('search_type') # 예: 'name', 'company', 'ingredient', 'shape'
    keyword = request.GET.get('keyword') # 예: '비타민', '종근당'

    if keyword:
        # [제품명]으로 검색
        if search_type == 'name':
            pills = pills.filter(PRDLST_NM__icontains=keyword)
        
        # [제조사]로 검색
        elif search_type == 'company':
            pills = pills.filter(BSSH_NM__icontains=keyword)
        
        # [성분]으로 검색
        elif search_type == 'ingredient':
            pills = pills.filter(STDR_STND__icontains=keyword)
            
        # [형태]로 검색 (정제, 캡슐 등)
        # elif search_type == 'shape':
        #     pills = pills.filter(PRDT_SHAP_CD_NM__icontains=keyword)
        # else: # 전체 검색
        #     pills = pills.filter(
        #         Q(PRDLST_NM__icontains=keyword) |
        #         Q(BSSH_NM__icontains=keyword) |
        #         Q(STDR_STND__icontains=keyword) |
        #         Q(PRDT_SHAP_CD_NM__icontains=keyword)
        #     )
    
    shapes_str = request.GET.get('shapes') 
    
    if shapes_str:
        shape_list = shapes_str.split(',') # 콤마로 쪼개서 리스트로 만듦
        q_shape = Q()

        for shape in shape_list:
            if shape == '정(알약)':
                # 사용자가 '정(알약)'을 선택하면 DB에서 '정' 또는 '알약'이 들어간 걸 찾음
                q_shape |= Q(PRDT_SHAP_CD_NM__icontains='정') | Q(PRDT_SHAP_CD_NM__icontains='알약')
            elif shape == '분말(가루)':
                 q_shape |= Q(PRDT_SHAP_CD_NM__icontains='분말') | Q(PRDT_SHAP_CD_NM__icontains='가루')
            else:
                # 나머지는 선택한 단어 그대로 검색 (예: 캡슐, 액상, 젤리 등)
                q_shape |= Q(PRDT_SHAP_CD_NM__icontains=shape)
        
        # 전체 pills 결과에 제형 필터를 덧씌움 (AND 조건)
        # 즉, 검색어로 찾은 결과 중에서 + 제형도 맞는 것만 남김
        pills = pills.filter(q_shape)


    paginator = PageNumberPagination()
    paginator.page_size = 20  # 한 페이지당 20개 데이터만 넘겨 받기
    
    # 필터링된 pills를 페이징 처리
    result_page = paginator.paginate_queryset(pills, request)
    
    # 4. 시리얼라이징 (JSON 변환)
    # pills_data = []
    # for pill in pills:
    #     pills_data.append({
    #         'id': pill.pk,
    #         'title': pill.PRDLST_NM,       # JS에서 쓸 이름(title) : 모델 필드명(PRDLST_NM)
    #         'company': pill.BSSH_NM,       # 제조사
    #         'description': pill.STDR_STND, # 성분/설명
    #         'cover': pill.cover if pill.cover else None, # 이미지
    #     })
    serializer = PillListSerializer(result_page, many=True)
    # JSON 형태로 응답 (render가 아님!)
    return paginator.get_paginated_response(serializer.data)
    # return JsonResponse({'pills': pills_data})


@api_view(['GET'])
@permission_classes([AllowAny])
def detail(request, pill_pk):
    pill = get_object_or_404(Pill, pk=pill_pk)

    print(f"\n📢 [DEBUG] ID: {pill.id} / 제품명: {pill.PRDLST_NM}")
    
    # 🔥 [수정 포인트]
    # 1. '자미오리' 제품이거나 (잘못된 링크 수정용)
    # 2. URL이 없거나
    # 3. 가격이 없거나 실패(-1)했던 경우
    # -> 무조건 검색 로직 실행!
    force_update = (pill.PRDLST_NM == '자미오리') # 자미오리만 강제 검색
    
    if force_update or not pill.purchase_url or pill.price == -1 or pill.price is None or pill.price == 0:
        print("🚀 네이버 검색 API 호출 시작... (검증 로직 적용됨)")
        
        # utils.py의 개선된 함수 호출 (기업명 검증 포함)
        link_data = get_purchase_link(pill.PRDLST_NM, pill.BSSH_NM) 
        
        if link_data:
            print(f"✅ 검색 성공! 최저가: {link_data['price']}원")
            print(f"   🔗 링크: {link_data['link']}")
            pill.purchase_url = link_data['link']
            pill.price = link_data['price']
            pill.mall_name = link_data['mall']
        else:
            print("❌ 검색 결과 없음 또는 제조사 불일치 (제습기 차단됨 🛡️)")
            pill.price = -1
            pill.purchase_url = ""
            
        pill.save()
        print("💾 DB 업데이트 완료")
    
    else:
        print("⚡ 이미 데이터가 있어서 생략함")

    serializer = PillDetailSerializer(pill)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def category_list(request):
    categories = Category.objects.all()
    # 프론트에서 쓰기 편하게 id와 name만 추출
    data = [{"id": c.id, "name": c.name} for c in categories]
    return Response(data)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def thread_create_api(request, pill_pk):
    pill = get_object_or_404(Pill, pk=pill_pk)
    
    # ThreadSerializer를 사용하여 데이터 검증 및 저장
    # context에 request를 전달하여 SerializerMethodField (is_liked 등)가 작동하도록 합니다.
    serializer = ThreadSerializer(data=request.data, context={'request': request}) 
    
    if serializer.is_valid(raise_exception=True):
        # user 필드를 저장하지 않습니다 (모델에서 nullable이거나 default 값이 있어야 함)
        # request.user를 사용하지 않으므로, Thread 모델의 user 필드가 null=True여야 합니다.
        thread = serializer.save(pill=pill, user=request.user) 
        
        # 성공 시, 생성된 쓰레드의 상세 정보를 JSON으로 반환 (201 Created)
        return Response(ThreadSerializer(thread, context={'request': request}).data, status=201)
    
# 필 굿 프로젝트 쓰레드 업데이트 로직----------------------------------------
@csrf_exempt
@api_view(['POST']) # Vue에서 POST로 보내므로 POST 허용
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def thread_update(request, pill_pk, thread_pk):
    thread = get_object_or_404(Thread, pk=thread_pk)

    # 🚩 권한 확인: 글 작성자와 현재 로그인 유저가 같은지 확인
    if thread.user != request.user:
        return Response({"detail": "수정 권한이 없습니다."}, status=403)

    # partial=True를 설정하면 제목이나 내용 중 하나만 보내도 수정이 가능합니다.
    serializer = ThreadSerializer(
        instance=thread, 
        data=request.data, 
        partial=True, 
        context={'request': request}
    )

    if serializer.is_valid(raise_exception=True):
        serializer.save()
        return Response(serializer.data)
# -------------------------------------------------------------------------
# 필 굿 프로젝트 쓰레드 삭제 로직 -------------------------------------------
@csrf_exempt
@api_view(['DELETE', 'POST']) # 안전하게 DELETE와 POST 모두 허용
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def thread_delete(request, pill_pk, thread_pk):
    thread = get_object_or_404(Thread, pk=thread_pk)

    # 🚩 권한 확인
    if thread.user != request.user:
        return Response({"detail": "삭제 권한이 없습니다."}, status=403)

    thread.delete()
    return Response({"detail": "후기가 삭제되었습니다."}, status=204)
# --------------------------------------------------------------------------

# --------사용자 영양제함 ----------------------------------------------------
@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def toggle_pill(request, pill_pk):
    pill = get_object_or_404(Pill, pk=pill_pk)
    user = request.user

    if request.method == 'POST':
        # 영양제함에 추가
        user_pill, created = UserPill.objects.get_or_create(user=user, pill=pill)
        if created:
            return Response({'message': '영양제함에 추가되었습니다.'}, status=201)
        return Response({'message': '이미 등록된 영양제입니다.'}, status=400)

    elif request.method == 'DELETE':
        # 영양제함에서 삭제
        user_pill = UserPill.objects.filter(user=user, pill=pill)
        if user_pill.exists():
            user_pill.delete()
            return Response({'message': '영양제함에서 삭제되었습니다.'}, status=204)
        return Response({'message': '등록되지 않은 영양제입니다.'}, status=400)
# ---------------------------------------------------------------------------
# ---------영양제함 목록 조회 api ---------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_pills(request):
    pills = UserPill.objects.filter(user=request.user).select_related('pill').prefetch_related('pill__nutrient_details')
    serializer = UserPillSerializer(pills, many=True)
    return Response(serializer.data)
# ---------------------------------------------------------------------------
# --------- 영양제가 사용자의 영양제함에 들어있는지 확인하는 함수----------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_pill_enrollment(request, pill_pk):
    # 현재 로그인한 유저가 이 영양제를 가지고 있는지 확인 (True/False)
    is_enrolled = UserPill.objects.filter(user=request.user, pill_id=pill_pk).exists()
    return Response({'is_enrolled': is_enrolled})
# ---------------------------------------------------------------------------
# --------------- 사용자 커스텀 영양제 ----------------------------------------
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def custom_pill_list(request):
    if request.method == 'GET':
        pills = CustomPill.objects.filter(user=request.user)
        serializer = CustomPillSerializer(pills, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = CustomPillSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save(user=request.user)
            return Response(serializer.data, status=201)
# ---------------------------------------------------------------------------
# ------------ 커스텀 영양제 삭제 ---------------------------------------------
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def custom_pill_detail(request, pk):
    # 본인이 작성한 커스텀 영양제만 가져옵니다.
    custom_pill = get_object_or_404(CustomPill, pk=pk, user=request.user)
    
    if request.method == 'DELETE':
        custom_pill.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
# ----------------------------------------------------------------------------
# -------------영양제 함량 가져오기 (중복 섭취 기능) ----------------------------
@api_view(['GET'])
def all_ingredients_list(request):
    # 모든 성분명(substance_name)을 가져와 중복 제거 후 가나다순 정렬
    ingredients = Nutrient.objects.values_list('substance_name', flat=True).distinct().order_by('substance_name')
    return Response(list(ingredients))
# ----------------------------------------------------------------------------


# @login_required
# @require_http_methods(["GET", "POST"])
# def thread_create(request, pill_pk):
#     pill = Pill.objects.get(pk=pill_pk)
#     if request.method == "POST":
#         form = ThreadForm(request.POST, request.FILES)
#         if form.is_valid():
#             thread = form.save(commit=False)
#             thread.pill = pill
#             thread.user = request.user
#             thread.save()

#             # generated_image_path = generate_image_with_openai(thread.title, thread.content, pill.PRDLST_NM, pill.BSSH_NM)
#             # if generated_image_path:
#             #     thread.cover_img = generated_image_path
#             #     thread.save()
                
#             return redirect("pills:thread_detail", pill.pk, thread.pk)
#     else:
#         form = ThreadForm()
#     context = {
#         "form": form,
#         "pill": pill,
#     }
#     return render(request, "pills/thread_create.html", context)


# @login_required
# @require_safe
# def thread_detail(request, pill_pk, thread_pk):
#     pill = Pill.objects.get(pk=pill_pk)
#     thread = Thread.objects.get(pk=thread_pk)
#     comment_form = CommentForm()
#     context = {
#         "pill" : pill,
#         "thread": thread,
#         "comment_form" : comment_form,
#     }
#     return render(request, "pills/thread_detail.html", context)
@api_view(['GET'])
@permission_classes([AllowAny])
def thread_detail(request, pill_pk, thread_pk):
    thread = get_object_or_404(Thread, pk=thread_pk, pill_id=pill_pk)
    serializer = ThreadSerializer(thread, context={'request': request})
    
    return Response(serializer.data)


# @login_required
# @require_http_methods(["GET", "POST"])
# def thread_update(request, pill_pk, thread_pk):
#     pill = Pill.objects.get(pk=pill_pk)
#     thread = Thread.objects.get(pk=thread_pk)
#     comment_form = CommentForm(request.POST)
#     if thread.user == request.user:
#         if request.method == "POST":
#             form = ThreadForm(request.POST, request.FILES, instance=thread)
#             if form.is_valid():
#                 form.save()  
#                 return redirect('pills:thread_detail', pill_pk=pill.pk, thread_pk=thread.pk)
#         else:
#             form = ThreadForm(instance=thread)
#     else :
#         return redirect('pills:index') 
#     context = {
#         "form": form,
#         "pill": pill,
#         "comment_form" : comment_form,
#     }
#     return render(request, "pills/thread_update.html", context)


# @login_required
# @require_POST
# def thread_delete(request, pill_pk, thread_pk):
#     thread = Thread.objects.get(pk=thread_pk)
#     if thread.user == request.user:
#         thread.delete()
#     return redirect("pills:detail", pill_pk)


# 쓰레드 좋아요 비동기 처리
@csrf_exempt
@api_view(['POST']) 
@authentication_classes([TokenAuthentication]) # 토큰으로 유저 신분 확인
@permission_classes([IsAuthenticated]) 
def likes(request, pill_pk, thread_pk):
    thread = get_object_or_404(Thread, pk=thread_pk)
    
    if thread.likes.filter(pk=request.user.pk).exists():
        thread.likes.remove(request.user)
        is_liked = False
    else:
        thread.likes.add(request.user)
        is_liked = True

    context = {
        'is_liked': is_liked,
        'likes_count': thread.likes.count(),
    }

    return Response(context, status=200)

# 쓰레드 댓글 비동기 처리
@require_POST
@login_required
def create_comment(request, pill_pk, thread_pk):
    thread = get_object_or_404(Thread, pk=thread_pk)
    comment_form = CommentForm(request.POST)

    if comment_form.is_valid():
        comment = comment_form.save(commit=False)
        comment.thread = thread
        comment.user = request.user
        comment.save()
        context = {
            'pk' : comment.pk,
            'content' : comment.content,
            'userName' : comment.user.username,
        }
        return JsonResponse(context)
    return JsonResponse({'message' : '유효성 검사 실패'}, status=400)

@require_POST
@login_required
def delete_comment(request, pill_pk, comment_pk):
    comment = get_object_or_404(Comment, pk=comment_pk)

    if request.user == comment.user:
        comment.delete()
        return JsonResponse({'pk' : comment_pk})
    return JsonResponse({'message' : '권한이 없습니다.'}, status=403)



@api_view(['GET'])
@permission_classes([AllowAny])
def thread_list(request, pill_pk):
    # 1. pill_pk에 해당하는 영양제 객체 가져오기 (없으면 404)
    pill = get_object_or_404(Pill, pk=pill_pk)
    
    # 2. 해당 영양제에 연결된 모든 후기(Thread)를 최신순으로 가져오기
    # Pill 모델에 related_name이 명시되어 있다면 해당 이름을 사용해도 됩니다.
    # 여기서는 Thread 모델이 pill 필드를 가지고 있다고 가정합니다.
    threads = pill.thread_set.all().annotate(
        comment_count=Count('comments') 
    ).order_by('-pk')
    
    # 3. 페이징 처리 (옵션)
    # 후기가 많아질 경우를 대비하여 페이징 처리를 고려할 수 있습니다.
    # 필요하다면 index 함수처럼 PageNumberPagination을 사용하세요.
    paginator = PageNumberPagination()
    paginator.page_size = 10 # 한 페이지당 10개
    result_page = paginator.paginate_queryset(threads, request)

    # 4. 시리얼라이징 (JSON 변환)
    # ThreadSerializer는 후기 목록을 위해 필요한 필드만 포함하도록 정의되어야 합니다.
    serializer = ThreadSerializer(result_page, many=True)
    
    # 5. JSON 응답
    # 페이징 처리를 사용했다면 paginator의 응답 함수를 사용합니다.
    return paginator.get_paginated_response(serializer.data)


# ==========================================
# ▼▼▼ 맞춤 추천 및 상세 검색 기능 추가 ▼▼▼
# ==========================================


# 2. 특정 카테고리 클릭 시 -> 성분 리스트 조회
@api_view(['GET'])
def category_detail(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    serializer = CategoryWithSubstancesSerializer(category)
    return Response(serializer.data)

# 3. 성분 상세 정보 조회 (효능, 부작용, 권장량 등)
@api_view(['GET'])
def substance_detail(request, substance_id):
    substance = get_object_or_404(Substance, pk=substance_id)
    serializer = SubstanceSerializer(substance)
    return Response(serializer.data)

# 4. ★ 핵심: 특정 성분이 포함된 영양제 리스트 (필터 + 페이징)
@api_view(['GET'])
def substance_pills(request, substance_id):
    substance = get_object_or_404(Substance, pk=substance_id)
    
    # [1] 기본 검색: 해당 성분이 포함된 영양제 찾기
    # models.py 구조: Pill <-> Nutrient <-> Substance
    # Nutrient 모델의 'substance' 필드를 통해 역참조하여 Pill을 찾습니다.
    pills = Pill.objects.filter(nutrient_details__substance=substance).exclude(price=-1).distinct()

    # [2] 카테고리 필터링 (교집합)
    categories_param = request.GET.get('category')
    if categories_param:
        # "간 건강,눈 건강" -> ["간 건강", "눈 건강"] 리스트로 변환
        category_list = categories_param.split(',')
        # __in 연산자를 써서 리스트에 포함된 것들을 모두 찾음
        pills = pills.filter(category__name__in=category_list)

    # [3] 제형(모양) 필터링 (포함 검색)
    shapes_param = request.GET.get('shapes')
    if shapes_param:
        shape_list = shapes_param.split(',')
        q_objects = Q()
        for shape in shape_list:
            # 예: '정(알약)' 검색 시 '정'이나 '알약' 글자가 포함되면 매칭
            q_objects |= Q(PRDT_SHAP_CD_NM__icontains=shape)
        pills = pills.filter(q_objects)

    # [4] 페이지네이션 (20개씩 끊어서 보내기)
    paginator = PageNumberPagination()
    paginator.page_size = 20
    result_page = paginator.paginate_queryset(pills, request)
    
    serializer = PillListSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)


# ------------- AI 추천 서비스 --------------------------------
@api_view(['POST'])
def chatbot_view(request):
    user_input = request.data.get('message')
    reply = get_pill_recommendation(user_input)
    return Response({'reply': reply})
# ------------------------------------------------------------



# --------구글 캘린더------------------------------------------
@csrf_exempt
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def register_google_calendar(request):
    pill_name = request.data.get('pillName')
    selected_date = request.data.get('date')
    intake_time = request.data.get('time')
    google_token = request.headers.get('Google-Access-Token')

    # RFC3339 시간 포맷 설정
    start_time = f"{selected_date}T{intake_time}:00+09:00"
    end_dt = datetime.strptime(f"{selected_date}T{intake_time}", "%Y-%m-%dT%H:%M") + timedelta(minutes=30)
    end_time = end_dt.strftime("%Y-%m-%dT%H:%M:%S+09:00")

    payload = {
        'summary': f'💊 {pill_name} 복용',
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Seoul'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Seoul'},
    }

    res = requests.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        json=payload,
        headers={"Authorization": f"Bearer {google_token}"}
    )

    if res.status_code in [200, 201]:
        return Response({"message": "등록 성공"}, status=200)
    return Response(res.json(), status=res.status_code)
# -----------------------------------------------------------------

