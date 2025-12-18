from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from pills.models import Category


User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    interested_genres = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="관심 성분",
        required=False
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "last_name",
            "first_name",
            "email",
            "gender",
            "age",
            "weekly_avg_eating_time",
            "annual_eating_amount",
            "profile_img",
            "interested_genres",
        )
        labels = {
            "username": "아이디",
            "last_name": "성",
            "first_name": "이름",
            "email": "이메일",
            "gender": "성별",
            "age": "나이",
            "weekly_avg_eating_time": "주간 평균 영양제 복용 시간",
            "annual_eating_amount": "연간 복용량",
            "profile_img": "프로필 사진",
            "interested_genres": "관심 성분",
        }
        exclude = {"weekly_avg_eating_time",'annual_eating_amount',}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "비밀번호"
        self.fields["password2"].label = "비밀번호 확인"


class CustomUserChangeForm(UserChangeForm):
    interested_genres = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="관심 성분",
        required=False
    )
    class Meta:
        model = User
        fields = (
            "username",
            "last_name",
            "first_name",
            "email",
            "gender",
            "age",
            "weekly_avg_eating_time",
            "annual_eating_amount",
            "profile_img",
            "interested_genres",
        )
        labels = {
            "username": "아이디",
            "last_name": "성",
            "first_name": "이름",
            "email": "이메일",
            "gender": "성별",
            "age": "나이",
            "weekly_avg_eating_time": "주간 평균 영양제 복용 시간",
            "annual_eating_amount": "연간 복용량",
            "profile_img": "프로필 사진",
            "interested_genres": "관심 성분",
        }
