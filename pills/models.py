# [your_app_name]/models.py 파일 (수정됨)

import datetime
from django.db import models
from django.conf import settings 

# --------------------
# 1. 카테고리 (기능성 분류) 모델
# --------------------
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="카테고리명")
    substances = models.ManyToManyField('Substance', related_name='categories', verbose_name="포함 영양소") 
    
    def __str__(self):
        return self.name

# --------------------
# 2. 영양소/원료 마스터 모델
# --------------------
class Substance(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="영양소 이름") 
    
    # ▼▼▼ [수정] 상세 설명 필드 3개 추가 ▼▼▼
    efficacy = models.TextField(default="데이터 설명", verbose_name="효능 및 효과")
    side_effects = models.TextField(default="데이터 설명", verbose_name="부작용 및 주의사항")
    recommended_intake = models.TextField(default="데이터 설명", verbose_name="권장 섭취량")
    # ▲▲▲ 추가 완료 ▲▲▲

    def __str__(self):
        return self.name

# --------------------
# 3. 제품 (알약) 모델
# --------------------
class Pill(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='pills', verbose_name="대표 카테고리"
    ) 
    
    # --- 핵심/고유 식별 필드 ---
    PRDLST_REPORT_NO = models.CharField(max_length=20, unique=True, verbose_name="품목제조보고 번호 (고유 ID)") 
    
    # --- 제품 기본 정보 ---
    PRDLST_NM = models.CharField(max_length=255, verbose_name="제품명")
    BSSH_NM = models.CharField(max_length=100, verbose_name="제조사/판매사")
    LCNS_NO = models.CharField(max_length=20, verbose_name="인허가 번호")
    PRMS_DT = models.CharField(max_length=10, verbose_name="허가(신고) 일자")
    POG_DAYCNT = models.CharField(max_length=50, verbose_name="소비기한 (기간)")
    PRDT_SHAP_CD_NM = models.CharField(max_length=50, verbose_name="제품 형태 (예: 캡슐, 분말)")
    
    # --- 상세 정보/섭취 정보 ---
    DISPOS = models.CharField(max_length=255, verbose_name="성상 (제품의 외관)")
    PRIMARY_FNCLTY = models.TextField(verbose_name="주된 기능성")
    NTK_MTHD = models.CharField(max_length=255, verbose_name="섭취방법")
    IFTKN_ATNT_MATR_CN = models.TextField(verbose_name="섭취시 주의사항")
    CSTDY_MTHD = models.CharField(max_length=255, blank=True, verbose_name="보관 방법")
    STDR_STND = models.TextField(verbose_name="기준 규격")
    RAWMTRL_NM = models.TextField(verbose_name="원재료")
    
    # --- 시스템/메타 정보 ---
    SHAP = models.CharField(max_length=100, null=True, blank=True, verbose_name="SHAP 필드 (JSON 원본 유지)") 
    CRET_DTM = models.CharField(max_length=14, verbose_name="최초 생성 일시 (JSON 원본)")
    LAST_UPDT_DTM = models.CharField(max_length=14, verbose_name="최종 수정 일시 (JSON 원본)")
    cover = models.URLField(null=True, blank=True, verbose_name="제품 이미지 URL")
    
    # --- 제품 갯수(가성비 게산하기 위해 필요) ---
    amount = models.IntegerField(null=True, blank=True, default=0) # 갯수
    unit_type = models.CharField(max_length=10, null=True, blank=True) # 단위
    # --- 네이버 제품 등록 ---
    purchase_url = models.URLField(null=True, blank=True) # 구매 링크
    price = models.IntegerField(null=True, blank=True)    # 가격
    mall_name = models.CharField(max_length=50, null=True, blank=True) # 판매처
    def __str__(self):
        return self.PRDLST_NM

# --------------------
# 4. 영양소 함량 (중간 연결) 모델
# --------------------
class Nutrient(models.Model):
    # Pill과 Substance의 N:M 관계를 해체하며 함량 정보를 저장합니다.
    pill = models.ForeignKey(Pill, on_delete=models.CASCADE, related_name='nutrient_details', verbose_name="제품")
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT, related_name='pill_details', verbose_name="영양소") 
    
    # ▼▼▼ 성분명 중복 저장을 위한 필드 추가 ▼▼▼
    substance_name = models.CharField(max_length=255, verbose_name="영양소 이름 (중복 저장)")
    # ▲▲▲ 성분명 중복 저장을 위한 필드 추가 ▲▲▲
    
    value = models.FloatField(verbose_name="함량 값")
    unit = models.CharField(max_length=50, verbose_name="함량 단위")

    class Meta:
        # Substance_id 대신 substance_name으로 제약 조건을 변경할 수 있으나,
        # 관계형 무결성을 위해 ForeignKey 제약을 유지합니다.
        unique_together = ('pill', 'substance') 

    def __str__(self):
        # 이제 substance_name 필드를 직접 사용합니다.
        return f'{self.pill.PRDLST_NM} - {self.substance_name}: {self.value}{self.unit}' 

# --------------------
# 5. 알레르기 정보 모델
# --------------------
class Allergen(models.Model):
    pill = models.ForeignKey(
        Pill, on_delete=models.CASCADE, related_name='allergens_info'
    )
    name = models.CharField(max_length=100)   
    
    class Meta:
        unique_together = ('pill', 'name')

    def __str__(self):
        return f'{self.pill.PRDLST_NM} - {self.name}'
    
# --------------------
# 6. 기타 모델 (커뮤니티)
# --------------------
class Thread(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    eating_date = models.DateField(default=datetime.date.today)
    cover_img = models.ImageField(upload_to="thread_cover_img/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    pill = models.ForeignKey('Pill', on_delete=models.CASCADE)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="liked_threads", blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,null=True, blank=True
    )

    def __str__(self):
        return self.title
    
class Comment(models.Model):
    content = models.CharField(max_length=100)
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.content
    

# 사용자가 등록하는 영양제함-----------------------------------
class UserPill(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='my_pills'
    )
    pill = models.ForeignKey(
        Pill, 
        on_delete=models.CASCADE,
        related_name='enrolled_users'
    )
    created_at = models.DateTimeField(auto_now_add=True) # 등록일

    class Meta:
        # 한 사용자가 같은 영양제를 중복해서 등록하지 못하도록 설정
        unique_together = ('user', 'pill')

    def __str__(self):
        return f"{self.user.username}의 영양제: {self.pill.PRDLST_NM}"
# -------------------------------------------------------------------

# ----------사용자가 직접 추가하는 영양제 ------------------------------
class CustomPill(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='custom_pills'
    )
    name = models.CharField(max_length=100)    # 제품명
    brand = models.CharField(max_length=100, blank=True) # 제조사
    memo = models.TextField(blank=True)        # 메모 (복용법 등)
    ingredients = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}의 커스텀 영양제: {self.name}"
# --------------------------------------------------------------------