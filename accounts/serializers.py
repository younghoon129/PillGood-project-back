from rest_framework import serializers
from django.contrib.auth import get_user_model
from pills.models import Category

User = get_user_model()

# ----------------------------------------------------------------
# [1] 간단한 유저 정보 (게시글/댓글 작성자 표시용)
# ----------------------------------------------------------------
class UserTinySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # 아이디, 닉네임, 프로필 사진만 노출 (비밀번호 등 민감정보 제외)
        fields = ('id', 'username', 'profile_img')

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
    
    followers_count = serializers.IntegerField(source='followers.count', read_only=True)
    followings_count = serializers.IntegerField(source='followings.count', read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'gender', 'age', 
            'weekly_avg_eating_time', 'annual_eating_amount', 
            'profile_img', 'interested_genres', 'interested_genres_names',
            'followers_count', 'followings_count',
        )
        read_only_fields = ('followings',) # 팔로잉은 별도 API로 제어 권장