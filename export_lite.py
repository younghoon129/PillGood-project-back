# export_lite.py
# 4만개 데이터 중 가격 -1 아닌 것만 저장하기
import os
import django
from django.core.serializers import serialize

os.environ.setdefault("DJANGO_SETTINGS_MODULE", 'mypjt.settings')
django.setup()

from pills.models import Pill

# 가격이 있는(구매 가능한) 제품만 필터링!
print("📦 알짜배기 데이터(Price > 0) 추출 중...")
qs = Pill.objects.filter(price__gt=0)

# 가벼운 파일로 저장
with open("pills_lite.json", "w", encoding="utf-8") as f:
    f.write(serialize("json", qs, indent=4, ensure_ascii=False))

print(f"✅ 추출 완료! 'pills_lite.json' (개수: {qs.count()}개)")
# 이 파일을 Git에 올리거나 협업자에게 전달하세요.