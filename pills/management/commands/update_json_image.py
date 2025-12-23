# 네이버 정보 넣는거

import json
import os
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from pills.utils import get_purchase_link  # utils.py에서 함수 가져오기

class Command(BaseCommand):
    help = 'JSON 파일을 읽어 이미지를 채운 뒤 새로운 JSON으로 저장합니다.'

    def handle(self, *args, **kwargs):
        # 1. 파일 경로 설정
        # (기존 파일) 읽을 파일
        input_file_path = os.path.join(settings.BASE_DIR, 'pills', 'fixtures', 'pills_lite_final.json')
        # (새 파일) 저장할 파일 이름
        output_file_path = os.path.join(settings.BASE_DIR, 'pills', 'fixtures', 'pills_final_with_images.json')

        # 2. JSON 파일 로드
        try:
            with open(input_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"📂 '{input_file_path}' 로드 완료! (총 {len(data)}개)")
        except FileNotFoundError:
            print(f"❌ 파일을 찾을 수 없습니다: {input_file_path}")
            return

        # 3. 데이터 순회하며 API 호출
        success_count = 0
        total_count = len(data)

        print("🚀 이미지 및 상세 정보 업데이트 시작...\n")

        for idx, item in enumerate(data):
            fields = item['fields']
            
            # 이미지가 없거나(None), 구매 링크가 없는 경우 업데이트 시도
            # (혹은 무조건 업데이트하려면 if문을 빼셔도 됩니다)
            if not fields.get('cover') or not fields.get('purchase_url'):
                
                prod_name = fields.get('PRDLST_NM')
                comp_name = fields.get('BSSH_NM')

                print(f"[{idx+1}/{total_count}] {prod_name} 검색 중...", end='')

                # utils.py의 함수 호출
                api_result = get_purchase_link(prod_name, comp_name)

                if api_result:
                    # 4. JSON 필드 업데이트 (API 결과 -> JSON 필드 매핑)
                    fields['cover'] = api_result.get('image')         # 이미지
                    fields['purchase_url'] = api_result.get('link')   # 구매링크
                    fields['price'] = api_result.get('price')         # 가격
                    fields['mall_name'] = api_result.get('mall')      # 판매처
                    
                    # 수량/단위 정보도 API 결과에 있다면 업데이트
                    if api_result.get('amount'):
                        fields['amount'] = api_result.get('amount')
                    if api_result.get('unit_type'):
                        fields['unit_type'] = api_result.get('unit_type')

                    print(" ✅ 업데이트 완료")
                    success_count += 1
                else:
                    print(" ❌ 검색 실패 (기존 유지)")
                    # 실패 시 가격 -1 처리 등으로 표시할 수도 있음
                    if not fields.get('price'): 
                        fields['price'] = -1
                
                # API 호출 제한 방지 (0.1초 대기)
                time.sleep(0.1)
            else:
                print(f"[{idx+1}/{total_count}] {fields.get('PRDLST_NM')} (이미 데이터 있음 - 패스)")

        # 5. 새로운 JSON 파일로 저장
        print(f"\n💾 새로운 파일로 저장 중... -> {output_file_path}")
        with open(output_file_path, 'w', encoding='utf-8') as outfile:
            # ensure_ascii=False를 해야 한글이 깨지지 않음
            json.dump(data, outfile, indent=2, ensure_ascii=False)

        print(f"🎉 작업 완료! 총 {success_count}개의 정보가 업데이트되었습니다.")