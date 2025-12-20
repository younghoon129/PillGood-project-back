from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Pill, Category, Substance, Nutrient, Allergen, Thread, Comment
from accounts.serializers import UserTinySerializer # 위에서 만든 유저 시리얼라이저 import

User = get_user_model()

# ----------------------------------------------------------------
# [1] 기초 정보 (카테고리, 성분, 알레르기)
# ----------------------------------------------------------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name')

class SubstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Substance
        fields = '__all__'

class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = ('name',) # 알레르기는 이름만 있으면 됨

# 중간 테이블(Nutrient) 시리얼라이저
class NutrientDetailSerializer(serializers.ModelSerializer):
    # substance_name 필드가 모델에 이미 있으므로 그대로 사용
    class Meta:
        model = Nutrient
        fields = ('substance_name', 'value', 'unit')


# ----------------------------------------------------------------
# [2] 영양제(Pill) 시리얼라이저 (★ 핵심 ★)
# ----------------------------------------------------------------

# [2-1] 목록 조회용 (List): 가볍게 필수 정보만 전송
class PillListSerializer(serializers.ModelSerializer):
    # 카테고리는 객체 전체보다 '이름'만 보내는 것이 리스트 로딩에 유리함
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Pill
        fields = (
            'id', 
            'PRDLST_NM',       # 제품명
            'BSSH_NM',         # 제조사
            'category_name',   # 카테고리 이름
            'cover',           # 이미지 URL
            'PRIMARY_FNCLTY',  # 주요 기능 (목록 미리보기용)
        )

# [2-2] 상세 조회용 (Detail): 모든 관계 데이터 포함 (Nested)
class PillDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True) # 카테고리 상세 정보
    
    # ★ 역참조 활용: models.py의 related_name과 일치시켜야 함 ★
    # nutrient_details: Nutrient 모델의 related_name
    nutrient_details = NutrientDetailSerializer(many=True, read_only=True)
    
    # allergens_info: Allergen 모델의 related_name
    allergens_info = AllergenSerializer(many=True, read_only=True)

    class Meta:
        model = Pill
        fields = '__all__' # 모든 필드 + 위에서 정의한 Nested 필드 포함


# ----------------------------------------------------------------
# [3] 커뮤니티 (Thread, Comment)
# ----------------------------------------------------------------

class CommentSerializer(serializers.ModelSerializer):
    # 작성자 정보 포함 (UserTinySerializer 사용)
    user = UserTinySerializer(read_only=True)

    class Meta:
        model = Comment
        fields = '__all__'
        read_only_fields = ('thread', 'user') # 자동 할당

class ThreadSerializer(serializers.ModelSerializer):
    user = UserTinySerializer(read_only=True)

    # 게시글 상세 조회 시 댓글도 같이 보고 싶다면 포함 (선택 사항)
    comments = CommentSerializer(many=True, read_only=True)

    comment_count = serializers.IntegerField(read_only=True)
    
    # 좋아요 개수 카운트 (DB 부하를 줄이기 위해 count만 전송)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    
    # 현재 로그인한 유저가 좋아요를 눌렀는지 여부 (SerializerMethodField 활용)
    is_liked = serializers.SerializerMethodField()

    # 현재 로그인한 유저가 작성자인지 확인
    is_author = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = (
            'id', 'title', 'content', 'cover_img', 
            'user', 'comments', 'comment_count', 'likes_count', 'is_liked', 'created_at','updated_at','is_author'
        )
        read_only_fields = ('user', 'likes')

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(pk=request.user.pk).exists()
        return False
    
    def get_is_author(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False
    
# 3. 카테고리 클릭 시 -> 포함된 성분 리스트를 보여주기 위한 시리얼라이저
class CategoryWithSubstancesSerializer(serializers.ModelSerializer):
    # 위에서 정의한 SubstanceSerializer를 가져다 씁니다.
    substances = SubstanceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'substances']