# 4만개짜리 데이터 로드하는 거

import time
import concurrent.futures
from django.core.management.base import BaseCommand
from django.db import connection
from pills.models import Pill
from pills.utils import get_purchase_link

class Command(BaseCommand):
    help = '멀티스레딩을 이용해 네이버 쇼핑 API를 초고속으로 조회합니다.'

    def handle(self, *args, **options):
        # 1. 검사 대상 가져오기 (가격 정보가 없는 것들)
        # 쿼리 최적화를 위해 필요한 필드만 가져옵니다
        targets = Pill.objects.filter(price__isnull=True).only('id', 'PRDLST_NM', 'BSSH_NM')
        total = targets.count()
        
        self.stdout.write(self.style.SUCCESS(f"🚀 총 {total}개의 데이터 고속 처리를 시작합니다..."))
        self.stdout.write(self.style.WARNING(f"⚠️ 네이버 API 하루 제한(25,000건)에 주의하세요!"))

        # 2. 멀티스레딩 설정
        MAX_WORKERS = 8 
        
        success_count = 0
        fail_count = 0
        processed_count = 0
        
        start_time = time.time()

        # 실제 검색을 수행하는 함수 (일꾼이 할 일)
        def process_pill(pill):
            try:
                # 검색 및 검증 로직 실행
                link_data = get_purchase_link(pill.PRDLST_NM, pill.BSSH_NM)
                
                if link_data:
                    pill.purchase_url = link_data['link']
                    pill.price = link_data['price']
                    pill.mall_name = link_data['mall']
                    
                    # 👇 [추가됨] 수량(amount)과 단위(unit_type) 저장 로직
                    # utils.py에서 넘어온 데이터에 'amount'가 있고 0보다 크면 저장
                    if 'amount' in link_data and link_data['amount'] > 0:
                        pill.amount = link_data['amount']
                        
                        # models.py에 unit_type 필드를 만드셨다면 아래 주석을 풀어주세요!
                        # 만약 models.py에 unit_type이 없다면 이 줄은 지우거나 주석 처리하세요.
                        if 'unit_type' in link_data:
                            pill.unit_type = link_data['unit_type']

                    pill.save()
                    return "found"
                else:
                    pill.price = -1
                    pill.purchase_url = ""
                    pill.save()
                    return "missing"
                    
            except Exception as e:
                return f"error: {e}"
            finally:
                # 스레드별 DB 커넥션 정리
                connection.close()

        # 3. ThreadPoolExecutor로 병렬 실행
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_pill = {executor.submit(process_pill, pill): pill for pill in targets}
            
            for future in concurrent.futures.as_completed(future_to_pill):
                processed_count += 1
                result = future.result()
                
                if result == "found":
                    success_count += 1
                elif result == "missing":
                    fail_count += 1
                
                # 100개마다 진행 상황 로그 출력
                if processed_count % 50 == 0:
                    elapsed = time.time() - start_time
                    speed = processed_count / elapsed if elapsed > 0 else 0
                    remaining = (total - processed_count) / speed / 60 if speed > 0 else 0
                    
                    self.stdout.write(
                        f"[{processed_count}/{total}] 성공:{success_count} 실패:{fail_count} "
                        f"| 속도: {speed:.1f}개/초 | 남은시간: 약 {remaining:.1f}분"
                    )

        self.stdout.write(self.style.SUCCESS(f"\n✨ 작업 완료! (총 {processed_count}건 처리)"))