import json
import os

# 파일명 설정
SOURCE_FILE = 'C:\\Users\\SSAFY\\Desktop\\LastProject\\PillGood-project-back\\pills\\fixtures\\pills_final_with_images.json'
BASE_DATA_FILE = '01_base_data.json'
PILLS_MAIN_FILE = '02_pills_main.json'
PILLS_DETAILS_FILE = '03_pills_details.json'

def safe_convert():
    if not os.path.exists(SOURCE_FILE):
        print(f"❌ 에러: {SOURCE_FILE} 파일이 없습니다.")
        return

    with open(SOURCE_FILE, 'r', encoding='utf-8') as f:
        try:
            original_data = json.load(f)
        except json.JSONDecodeError:
            print("❌ 에러: JSON 파일 형식이 올바르지 않습니다.")
            return

    # 데이터 저장용 컨테이너
    categories_set = set()
    substances_map = {} # 이름 -> PK 매핑
    pills = []
    nutrients = []
    allergens = []

    substance_pk_gen = 1
    nutrient_pk_gen = 1
    allergen_pk_gen = 1

    print(f"🚀 변환 시작: 총 {len(original_data)}개 데이터")

    for entry in original_data:
        pill_pk = entry.get('pk')
        fields = entry.get('fields', {})
        
        # 1. Category 수집 (Pill에 적힌 ID 기준)
        cat_id = fields.get('category')
        if cat_id is not None:
            categories_set.add(cat_id)

        # 2. Nutrients 처리 (Substance와 연결)
        raw_nutrients = fields.pop('nutrients', {})
        seen_substances_in_pill = set() # 한 Pill 내 중복 성분 방지

        for s_name, detail in raw_nutrients.items():
            s_name = s_name.strip()
            if not s_name: continue

            # Substance 마스터 등록 (없을 때만)
            if s_name not in substances_map:
                substances_map[s_name] = substance_pk_gen
                substance_pk_gen += 1
            
            s_pk = substances_map[s_name]

            # Unique 제약 조건 체크 (Pill + Substance 중복 방지)
            if s_pk in seen_substances_in_pill:
                continue
            seen_substances_in_pill.add(s_pk)

            nutrients.append({
                "model": "pills.nutrient",
                "pk": nutrient_pk_gen,
                "fields": {
                    "pill": pill_pk,
                    "substance": s_pk,
                    "substance_name": s_name,
                    "value": detail.get('value', 0.0),
                    "unit": detail.get('unit', '')[:50] # max_length 준수
                }
            })
            nutrient_pk_gen += 1

        # 3. Allergens 처리
        raw_allergens = fields.pop('allergens', [])
        seen_allergens_in_pill = set()
        for a_name in raw_allergens:
            a_name = a_name.strip()
            if not a_name or a_name in seen_allergens_in_pill: continue
            seen_allergens_in_pill.add(a_name)

            allergens.append({
                "model": "pills.allergen",
                "pk": allergen_pk_gen,
                "fields": {
                    "pill": pill_pk,
                    "name": a_name[:100] # max_length 준수
                }
            })
            allergen_pk_gen += 1

        # 4. Pill 저장
        pills.append({
            "model": "pills.pill",
            "pk": pill_pk,
            "fields": fields
        })

    # 파일 쓰기
    # 01. Base Data (Category + Substance)
    base_data = []
    for c_id in sorted(list(categories_set)):
        base_data.append({
            "model": "pills.category",
            "pk": c_id,
            "fields": {"name": f"카테고리_{c_id}"}
        })
    for s_name, s_pk in substances_map.items():
        base_data.append({
            "model": "pills.substance",
            "pk": s_pk,
            "fields": {
                "name": s_name,
                "efficacy": "데이터 설명",
                "side_effects": "데이터 설명",
                "recommended_intake": "데이터 설명"
            }
        })
    
    with open(BASE_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(base_data, f, ensure_ascii=False, indent=2)

    # 02. Pills Main
    with open(PILLS_MAIN_FILE, 'w', encoding='utf-8') as f:
        json.dump(pills, f, ensure_ascii=False, indent=2)

    # 03. Pills Details
    with open(PILLS_DETAILS_FILE, 'w', encoding='utf-8') as f:
        json.dump(nutrients + allergens, f, ensure_ascii=False, indent=2)

    print(f"✅ 변환 완료!")
    print(f" - 기초 데이터: {len(base_data)}개")
    print(f" - 제품 데이터: {len(pills)}개")
    print(f" - 상세/알러지: {len(nutrients + allergens)}개")

if __name__ == "__main__":
    safe_convert()