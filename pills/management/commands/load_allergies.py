import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from accounts.models import Allergy  # Allergy 모델 위치 확인

class Command(BaseCommand):
    help = 'fixtures/allergies.json 파일을 읽어 Allergy 모델에 데이터를 저장합니다.'

    def handle(self, *args, **options):
        # 🚩 사진의 구조에 맞춰 경로 설정 (프로젝트 루트의 fixtures 폴더)
        json_file_path = 'pills/fixtures/allergies.json' 

        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                allergy_data = json.load(f)

            success_count = 0
            for item in allergy_data:
                name = item.get('name')
                # get_or_create로 중복 방지
                obj, created = Allergy.objects.get_or_create(name=name)
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f"✅ 신규 등록: {name}"))
                    success_count += 1
                else:
                    self.stdout.write(self.style.WARNING(f"ℹ️ 이미 존재: {name}"))

            self.stdout.write(self.style.SUCCESS(f"\n✨ 총 {success_count}개의 데이터가 추가되었습니다."))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"❌ 파일을 찾을 수 없습니다: {json_file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 오류 발생: {str(e)}"))