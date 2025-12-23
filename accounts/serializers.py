from rest_framework import serializers
from django.contrib.auth import get_user_model
from pills.models import Category
from .models import Allergy

User = get_user_model()

# ----------------------------------------------------------------
# [1] 간단한 유저 정보 (게시글/댓글 작성자 표시용)
# ----------------------------------------------------------------
class UserTinySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # 아이디, 닉네임, 프로필 사진만 노출 (비밀번호 등 민감정보 제외)
        fields = ('id', 'username', 'profile_img' , 'first_name')

# ----------------------------------------------------------------
# [2] 유저 프로필 상세 정보 (마이페이지/회원정보 수정용)
# ----------------------------------------------------------------
class UserProfileSerializer(serializers.ModelSerializer):
    # 관심 장르(Category)는 ID만 보내는 게 아니라 이름도 같이 표기하고 싶을 때 사용
    # (필요하다면 pills.serializers의 CategorySerializer를 import해서 써야 함)
    # 여기서는 간단하게 ID 리스트로 처리하거나, StringRelatedField로 이름만 보낼 수 있음
    interested_genres_names = serializers.StringRelatedField(
        source='interested_genres', many=True, read_only=True
    )

    allergies = serializers.PrimaryKeyRelatedField(many=True, queryset=Allergy.objects.all(), required=False)
    allergies_names = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
        source='allergies'
    )
    followers_count = serializers.IntegerField(source='followers.count', read_only=True)
    followings_count = serializers.IntegerField(source='followings.count', read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'gender', 'age', 
            'weekly_avg_eating_time', 'annual_eating_amount', 
            'profile_img', 'interested_genres', 'interested_genres_names',
            'followers_count', 'followings_count', 'allergies', 'allergies_names'
        )
        read_only_fields = ('followings',) # 팔로잉은 별도 API로 제어 권장

# ---------------------------
# 간단한 알러지 전용 시리얼라이저
# ---------------------------
class AllergySerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergy
        fields = '__all__'



class SignupSerializer(serializers.ModelSerializer):
    # 비밀번호는 쓰기 전용으로 설정 (응답에는 포함되지 않음)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            'username', 'password', 'email', 'gender', 'age', 
            'weekly_avg_eating_time', 'annual_eating_amount', 
            'profile_img', 'interested_genres','allergies'
        )

    def create(self, validated_data):
        # 1. 다대다 관계 데이터(M2M)는 일반 필드 생성 시 함께 넣을 수 없으므로 추출(pop)합니다.
        genres_data = validated_data.pop('interested_genres', [])
        allergies_data = validated_data.pop('allergies', [])

        # 2. 유저 객체를 먼저 생성합니다. (create_user를 사용해야 비밀번호가 암호화됩니다.)
        user = User.objects.create_user(**validated_data)

        # 3. 생성된 유저 객체(ID가 생김)에 다대다 관계를 연결합니다.
        if genres_data:
            user.interested_genres.set(genres_data)
        if allergies_data:
            user.allergies.set(allergies_data)

        return user
    