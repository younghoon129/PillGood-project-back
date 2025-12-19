from django.db import models
from django.contrib.auth.models import AbstractUser
from pills.models import Category


class User(AbstractUser):
    # 성별
    GENDER_CHOICES = (
        ('M', '남성'),
        ('F', '여성'),
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        null=True,
    )

    # 나이
    age = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    # 주간 평균 독서 시간
    weekly_avg_eating_time = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    # 연간 독서량
    annual_eating_amount = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    # 프로필 사진
    profile_img = models.ImageField(
        upload_to='user_profile_img/',
        blank=True,
        null=True,
    )

    # 관심 장르 (다중 선택, M:N 관계)
    interested_genres = models.ManyToManyField(
        Category,
        blank=True,
        related_name="users",
    )

    # 팔로잉
    followings = models.ManyToManyField(
        'self', symmetrical=False, related_name='followers'
    )

    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username

