import json
import requests
import random

# ==========================================
# 1. 설정 (SSAFY GMS API)
# ==========================================
GMS_KEY = "S14P02AR07-4c958e60-790d-49bd-9400-9fc7ccfe5776"  # SSAFY에서 발급받은 GMS 키를 입력하세요
BASE_URL = "https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
DATA_FILE = "C:\\Users\\SSAFY\\Desktop\\PillGood_back\\PillGood-project-back\\pills\\fixtures\\pills_lite_final.json"

# ==========================================
# 2. 데이터 로드
# ==========================================
def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 오류: '{DATA_FILE}' 파일이 없습니다. 같은 폴더에 넣어주세요.")
        return []

# ==========================================
# 3. 매핑 없는 스마트 검색 (데이터 기반 검색)
# ==========================================
def search_relevant_products(data, user_input):
    """
    별도의 매핑 테이블 없이, 사용자의 입력 문장이
    제품의 '기능성'이나 '제품명'에 포함되는지 직접 검사하여 후보를 추립니다.
    """
    candidates = []
    user_keywords = user_input.split() # 공백 기준으로 단어 분리

    for item in data:
        fields = item.get('fields', {})
        name = fields.get('PRDLST_NM', '')
        function = fields.get('PRIMARY_FNCLTY', '')
        shape = fields.get('PRDT_SHAP_CD_NM', '') # 제형 (분말, 캡슐 등)
        appearance = fields.get('DISPOS', '')     # 성상 (흰색의 장방형 등)
        
        # 점수 계산: 사용자 입력 단어가 기능성 설명에 많이 포함될수록 높은 점수
        score = 0
        for word in user_keywords:
            # 2글자 이상인 단어만 검색 (조사 제외 등 간단한 필터링 효과)
            if len(word) >= 2: 
                if word in function: score += 2
                if word in name: score += 1
        
        # 하나라도 매칭되거나, 무조건 랜덤으로 몇 개 섞어서 AI에게 판단 맡기기 위해
        # 점수가 0이라도 후보군에는 넣되 정렬에서 밀리게 함
        candidates.append({
            "name": name,
            "function": function,
            "shape_info": f"{shape} ({appearance})",
            "usage": fields.get('NTK_MTHD', ''),
            "score": score
        })
    
    # 점수 높은 순으로 정렬 후 상위 5개 추출
    # (점수가 같으면 랜덤 섞기 효과를 위해 sort 안정성 활용 안 함)
    random.shuffle(candidates) 
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    return candidates[:5]

# ==========================================
# 4. AI 답변 생성 (성분, 형태, 편지 포함)
# ==========================================
def generate_detailed_recommendation(user_input, products):
    """
    AI에게 후보 제품들의 상세 스펙을 주고, 가장 적절한 하나를 골라
    성분, 형태, 이유, 편지를 작성하게 합니다.
    """
    if not products:
        return "데이터에서 적절한 제품을 찾지 못했습니다."

    # AI에게 보낼 제품 정보 구성
    product_context = ""
    for idx, p in enumerate(products):
        product_context += f"""
        [후보 {idx+1}]
        - 제품명: {p['name']}
        - 제형/성상: {p['shape_info']}
        - 주요기능성(성분포함): {p['function']}
        - 섭취방법: {p['usage']}
        """

    system_prompt = f"""
    당신은 영양제 데이터 분석 전문가이자 센스 있는 선물 컨시어지입니다.
    사용자는 **"{user_input}"**라는 상황으로 선물을 찾고 있습니다.
    
    아래 [후보 제품 목록]을 분석하여, 사용자의 상황에 가장 적합한 **단 하나의 제품**을 추천해주세요.
    특히, 사용자가 궁금해하는 **'어떤 성분이 들어있는지'**와 **'어떻게 생겼는지(형태)'**를 명확하게 설명해야 합니다.

    [후보 제품 목록]
    {product_context}

    [필수 출력 형식]
    🎁 **추천 제품**: [제품명]
    
    🧪 **주요 성분**: 
    [기능성 텍스트에서 핵심 영양소(예: 비타민D, 밀크씨슬 등)를 추출하여 설명]
    
    💊 **형태 및 생김새**: 
    [제형/성상 정보를 바탕으로 설명 (예: 흰색의 길쭉한 알약, 노란색 가루 등)]
    
    💡 **이 제품을 선택한 이유**:
    [사용자의 상황("{user_input}")과 제품의 기능을 연결하여 논리적으로 설명]
    
    💌 **메시지 카드**:
    [선물 받는 사람에게 보낼 감동적이고 센스 있는 짧은 편지]
    """

    # API 호출
    headers = {"Content-Type": "application/json"}
    url = f"{BASE_URL}?key={GMS_KEY}"
    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"API 호출 오류: {response.text}"
    except Exception as e:
        return f"오류 발생: {e}"

# ==========================================
# 5. 메인 실행
# ==========================================
if __name__ == "__main__":
    print("🎁 스마트 AI 선물 추천 (데이터 기반 분석 모드)")
    print("--------------------------------------------------")
    print("특정 대상을 지정하거나(예: 우리 아빠), 증상을 말해보세요(예: 눈이 침침해).")
    print("AI가 데이터에 있는 '성분'과 '형태'를 분석해 추천해줍니다.")
    print("--------------------------------------------------")
    
    all_data = load_data()
    
    if all_data:
        while True:
            user_input = input("\n👤 상황을 입력하세요 (종료: q): ")
            if user_input.lower() in ['q', 'quit']:
                break
            
            print(f"🔍 '{user_input}'와 관련된 데이터를 분석 중...")
            
            # 1. 데이터에서 관련성 있는 후보 찾기 (매핑 없음, 텍스트 매칭)
            candidates = search_relevant_products(all_data, user_input)
            
            # 2. AI가 상세 분석 후 추천
            print("🤖 AI가 성분과 형태를 확인하고 있습니다...")
            result = generate_detailed_recommendation(user_input, candidates)
            
            print("\n" + "="*60)
            print(result)
            print("="*60)