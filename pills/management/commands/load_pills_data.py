
import json
import os
from django.core.management.base import BaseCommand, CommandError
from pills.models import Pill, Nutrient, Allergen, Category, Substance
from django.db import transaction

FIXTURE_PATH = 'pills/fixtures/pills_data.json' 

class Command(BaseCommand):
    help = 'JSON 파일에서 건강기능식품 데이터를 로드하여 Substance 기반으로 Category를 유추하고 저장합니다.'

    # 영양소와 카테고리 매핑 기준 정의 
    DATA_MAPPING = {
        # === 1. 주요 장기 (신규 추가) ===
        "간 건강 (피로/해독)": ["실리마린", "코엔자임Q10", "글루타치온(미백)", "비타민B1", "비타민B2", "비타민B6", "비타민B12", "셀레늄", "아연", "비타민C", "비타민E"],
        "위/소화기": ["양배추추출물", "감초추출물", "매실추출물", "효소", "알파아밀라아제(효소)", "프로테아제(효소)", "프로바이오틱스(유산균)", "알로에 전잎(장건강)"],
        "심장/혈압": ["오메가3(혈행)", "EPA(오메가3)", "DHA(오메가3)", "칼륨", "엽산(비타민B9)", "나토키나제(혈행)", "단신수(혈행)", "마그네슘"],
        "호흡기/구강": ["프로폴리스(항산화)", "플라보노이드(프로폴리스)", "아연", "비타민C", "배(도라지 등 혼합 가능성 있음)"],

        # === 2. 타겟별 분류 (신규 추가/수정) ===
        "유아/아동 (성장/면역)": ["아연", "비타민D", "칼슘", "해조칼슘(칼슘)", "프로바이오틱스(유산균)", "초유(데이터엔 없으나 일반적 매핑)", "철분"],
        "남성 건강": ["쏘팔메토", "로르산(쏘팔메토)", "야관문", "마카", "아르기닌(아미노산)", "아연", "옥타코사놀(지구력)", "비타민B1"],
        "여성 건강": ["대두이소플라본(뼈건강)", "감마리놀렌산(오메가6)", "철분", "엽산(비타민B9)", "히알루론산(피부보습)", "석류(엘라그산)"],

        # === 3. 기존 효능 분류 ===
        "뇌/신경/수면": ["포스파티딜세린(뇌건강)", "스핑고마이엘린(뇌건강)", "피브로인(기억력)", "테아닌(스트레스 완화)", "GABA(수면/스트레스)", "로즈마리산(레몬밤)", "락티움(수면)", "감태추출물(수면)", "미강주정추출물(수면)", "타트체리(수면)", "마그네슘", "비타민B6", "비타민B12"],
        "눈 건강": ["루테인(마리골드꽃)", "지아잔틴(마리골드꽃)", "아스타잔틴(헤마토코쿠스)", "안토시아노사이드(빌베리)", "레티놀(비타민A)", "베타카로틴(비타민A)", "비타민A", "오메가3(혈행)"],
        "혈관/혈액순환": ["오메가3(혈행)", "EPA(오메가3)", "DHA(오메가3)", "감마리놀렌산(오메가6)", "나토키나제(혈행)", "헤스페리딘(혈행)", "단신수(혈행)", "비타민K", "비타민E"],
        "관절/뼈": ["글루코사민(관절)", "N-아세틸글루코사민(관절)", "MSM(식이유황)", "콘드로이친(연골)", "뮤코다당단백(콘드로이친)", "보스웰릭산(보스웰리아)", "초록입홍합추출물", "로즈힙추출물", "칼슘", "구연산칼슘(칼슘)", "해조칼슘(칼슘)", "유청칼슘(칼슘)", "마그네슘", "비타민D", "비타민K"],
        "장 건강/배변": ["프로바이오틱스(유산균)", "비피더스균(유산균)", "락토바실러스(유산균)", "프리바이오틱스(유산균 먹이)", "프락토올리고당(프리바이오틱스)", "갈락토올리고당(프리바이오틱스)", "식이섬유", "차전자피(식이섬유)", "난소화성말토덱스트린(식이섬유)", "구아검(식이섬유)", "알로에 전잎(장건강)"],
        "피부/미용": ["히알루론산(피부보습)", "콜라겐(피부)", "세라마이드(피부장벽)", "엘라스틴(피부탄력)", "글루타치온(미백)", "알로에 전잎(장건강)", "스피루리나", "클로렐라(엽록소)", "비타민C", "비오틴(비타민B7)", "레티놀(비타민A)", "비타민E"],
        "면역/활력": ["홍삼(면역/피로)", "인삼(면역/피로)", "진세노사이드(홍삼/인삼)", "프로폴리스(항산화)", "베타글루칸(면역)", "락토페린(면역)", "폴리감마글루탐산(면역)", "알콕시글리세롤(상어간유)", "스쿠알렌(상어간유)", "코디세핀(동충하초)", "비타민C", "아연", "망간", "구리", "SOD(항산화효소)"],
        "다이어트 (체지방)": ["가르시니아(HCA)", "카테킨(녹차추출물)", "시서스(다이어트)", "풋사과추출물(다이어트)", "CLA(공액리놀렌산)", "잔티젠(다이어트)", "핑거루트(판두라틴)", "포스콜린(콜레우스)", "L-카르니틴(다이어트/운동)"],
        "근육/운동": ["단백질", "아미노산", "BCAA(아미노산)", "아르기닌(아미노산)", "크레아틴(근육)", "옥타코사놀(지구력)", "글루타민(아미노산)"]
    }
    
    @transaction.atomic
    def initialize_mapping(self):
        """ DATA_MAPPING을 기반으로 Category와 Substance, N:M 관계를 설정합니다. """
        self.stdout.write(self.style.NOTICE('데이터 매핑 기반 초기 Category/Substance N:M 관계 설정 시작...'))
        
        # 유추 실패 시 사용할 기본 카테고리 정의
        default_category, created = Category.objects.get_or_create(name="기타 건강식품", defaults={'pk': 99})
        if created:
             self.stdout.write(self.style.SUCCESS('기본 카테고리 (PK 99) 생성 완료.'))

        # 1. Category 및 Substance 생성 및 N:M 관계 설정
        for cat_name, substance_names in self.DATA_MAPPING.items():
            category, created = Category.objects.get_or_create(name=cat_name)
            
            for sub_name in substance_names:
                substance, _ = Substance.objects.get_or_create(name=sub_name)
                # Substance가 포함된 모든 Category에 N:M 연결 (다중 연결)
                category.substances.add(substance)

        self.stdout.write(self.style.SUCCESS('초기 매핑 완료: 모든 Substance는 관련된 모든 Category에 연결되었습니다.'))
        return default_category


    def handle(self, *args, **options):
        # 1. 파일 로드 및 초기 검증
        try:
            with open(FIXTURE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
             raise CommandError(f'File not found at {FIXTURE_PATH}. 경로를 확인해주세요.')
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON format in {FIXTURE_PATH}: {e}')

        self.stdout.write(self.style.NOTICE(f'총 {len(data)}개의 제품 데이터를 로드합니다...'))
        
        if not isinstance(data, list):
            data = [data] # 단일 객체일 경우 리스트로 변환

        # 0. 매핑 초기화 및 기본 카테고리 확보 (N:M 관계를 DB에 심습니다)
        default_category = self.initialize_mapping()

        created_count = 0
        total_items = len(data)
        
        def convert_date(date_str, report_no):
            """YYYYMMDD 형식 문자열을 datetime.date 객체로 변환"""
            if not date_str or not date_str.isdigit() or len(date_str) != 8:
                return date_str
            try:
                return date_str
            except ValueError:
                self.stdout.write(self.style.WARNING(f"경고: 날짜 변환 실패 - {date_str} for ID {report_no}. 원본 문자열 사용."))
                return date_str
                
        # 3. 데이터 로드 루프 시작
        with transaction.atomic():
            for item_index, fixture_item in enumerate(data):
                
                # 픽스처 형식에서 실제 데이터를 포함하는 'fields' 딕셔너리 추출
                if not isinstance(fixture_item, dict) or 'fields' not in fixture_item:
                    self.stdout.write(self.style.ERROR(
                        f"\n❌ 오류: 데이터 {item_index+1}/{total_items}번 항목이 유효한 픽스처 형식이 아닙니다. (fields 키 누락)"))
                    continue 
                
                item = fixture_item['fields'] # 실제 Pill 데이터는 item 변수에 저장
                
                # ID 추출 
                report_no = item.get('PRDLST_REPORT_NO', 'Unknown')
                
                # --- ▼ Category 자동 유추 및 Pill의 대표 Category 결정 로직 ▼ ---
                nutrients_data = item.get('nutrients', {})
                category_candidates = {}  # {Category 객체: 득표 수}
                substance_objects_to_process = []
                
                try:
                    # 1. Substance 확보 및 득표 수 카운트
                    for name in nutrients_data.keys():
                        substance, _ = Substance.objects.get_or_create(name=name)
                        substance_objects_to_process.append(substance)

                        # Substance가 연결된 Category 목록을 확인하여 득표합니다.
                        for cat in substance.categories.all(): 
                            category_candidates[cat] = category_candidates.get(cat, 0) + 1

                    # 2. Pill의 단일 대표 Category 결정 (최다 득표)
                    if category_candidates:
                        current_category = max(category_candidates.items(), key=lambda item: item[1])[0]
                    else:
                        current_category = default_category

                    # **Pill 객체 생성/업데이트**
                    pill, created = Pill.objects.update_or_create(
                        PRDLST_REPORT_NO=report_no,
                        defaults={
                            # ForeignKey는 단일 객체만 저장 가능
                            'category': current_category, 
                            'LCNS_NO': item.get('LCNS_NO', ''),
                            'BSSH_NM': item.get('BSSH_NM', ''),
                            'PRDLST_NM': item.get('PRDLST_NM', ''),
                            'PRMS_DT': item.get('PRMS_DT', ''), # CharField이므로 그대로 사용
                            'POG_DAYCNT': item.get('POG_DAYCNT', ''),
                            'DISPOS': item.get('DISPOS', ''),
                            'NTK_MTHD': item.get('NTK_MTHD', ''),
                            'PRIMARY_FNCLTY': item.get('PRIMARY_FNCLTY', ''),
                            'IFTKN_ATNT_MATR_CN': item.get('IFTKN_ATNT_MATR_CN', ''),
                            'CSTDY_MTHD': item.get('CSTDY_MTHD', ''),
                            'SHAP': item.get('SHAP', ''),
                            'STDR_STND': item.get('STDR_STND', ''),
                            'RAWMTRL_NM': item.get('RAWMTRL_NM', ''),
                            'CRET_DTM': item.get('CRET_DTM', ''), 
                            'LAST_UPDT_DTM': item.get('LAST_UPDT_DTM', ''), 
                            'PRDT_SHAP_CD_NM': item.get('PRDT_SHAP_CD_NM', ''),
                        }
                    )

                    if created:
                        created_count += 1
                        
                    # 3. Nutrient 객체 생성 (substance_name 필드에 성분명 저장)
                    Nutrient.objects.filter(pill=pill).delete()
                    for substance in substance_objects_to_process:
                        name = substance.name
                        details = nutrients_data.get(name, {})
                        
                        Nutrient.objects.create(
                            pill=pill,
                            substance=substance,
                            substance_name=name, # <--- 성분명 저장
                            value=details.get('value', 0.0),
                            unit=details.get('unit', ''),
                        )

                    # 4. Allergen 객체 생성
                    Allergen.objects.filter(pill=pill).delete()
                    allergens_list = item.get('allergens', [])
                    
                    for allergen_name in allergens_list:
                        Allergen.objects.create(
                            pill=pill,
                            name=allergen_name,
                        )
                    
                    self.stdout.write(self.style.NOTICE(f"성공적으로 처리됨: {report_no} -> Category: {current_category.name}"))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"\n❌ 오류 발생 - PRDLST_REPORT_NO {report_no}: {e}"))
                    continue

        self.stdout.write(self.style.SUCCESS('--- 데이터 로드 완료 ---'))
        self.stdout.write(self.style.SUCCESS(f'성공적으로 처리된 제품 수: {total_items - (total_items - created_count)}개'))
        self.stdout.write(self.style.SUCCESS(f'새로 생성된 제품 수: {created_count}개'))