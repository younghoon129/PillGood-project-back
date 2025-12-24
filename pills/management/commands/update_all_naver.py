# 이미지 -1 이거나 NULL 인 것들 다시 찾음, 이미지 주소 없으면 -1 표시

from django.core.management.base import BaseCommand
from pills.models import Pill
from pills.utils import get_purchase_link
import time

class Command(BaseCommand):
    help = '모든 영양제의 이미지와 구매 링크를 네이버 API로 업데이트합니다.'

    def handle(self, *args, **kwargs):
        # 이미지가 없거나(-1) 링크가 없는 제품들만 골라서 작업
        pills = Pill.objects.filter(purchase_url__isnull=True) | Pill.objects.filter(purchase_url='')
        
        total = pills.count()
        print(f"총 {total}개의 제품 업데이트를 시작합니다...")

        for idx, pill in enumerate(pills):
            try:
                print(f"[{idx+1}/{total}] {pill.PRDLST_NM} 검색 중...", end='')
                
                # utils.py의 함수 사용
                data = get_purchase_link(pill.PRDLST_NM, pill.BSSH_NM)
                
                if data:
                    pill.purchase_url = data.get('link')
                    pill.price = data.get('price')
                    pill.mall_name = data.get('mall')
                    pill.cover = data.get('image') # 이미지 저장!
                    pill.save()
                    print(" ✅ 성공")
                else:
                    print(" ❌ 실패 (검색 결과 없음)")
                    pill.price = -1 # 실패 표시
                    pill.save()
                
                # 네이버 API 제한(초당 10회) 방지를 위해 약간 대기
                time.sleep(0.1) 
                
            except Exception as e:
                print(f" ⚠️ 에러 발생: {e}")

        print("모든 작업이 완료되었습니다.")