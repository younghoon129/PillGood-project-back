# 판매처 없는 영양제들은 안보이게(-1로) 해뒀는데, 이 파일 실행시 None으로 되돌려줌

# pills/management/commands/reset_failed_pills.py
from django.core.management.base import BaseCommand
from pills.models import Pill
from django.utils import timezone
import datetime

class Command(BaseCommand):
    help = '판매처 없음(-1)으로 처리된 영양제들을 다시 검색 대상(None)으로 리셋합니다.'

    def handle(self, *args, **options):
        # 예: 업데이트된 지 30일이 지난 -1 제품들만 리셋 (너무 자주 하면 비효율적)
        # 지금은 테스트를 위해 모든 -1 제품을 리셋하는 코드로 작성합니다.
        
        failed_pills = Pill.objects.filter(price=-1)
        count = failed_pills.count()

        if count > 0:
            # 가격을 다시 None으로, URL도 초기화
            failed_pills.update(price=None, purchase_url=None, mall_name=None)
            self.stdout.write(self.style.SUCCESS(f'총 {count}개의 판매 중지 상품을 재검색 대기 상태로 되살렸습니다! 🧟'))
        else:
            self.stdout.write(self.style.SUCCESS('되살릴 상품이 없습니다.'))