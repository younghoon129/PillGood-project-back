import json
import requests
import random
import urllib3 # SSL 경고 제어를 위해 추가

import os
from dotenv import load_dotenv
load_dotenv()

# ==========================================
# 1. 설정 (SSAFY GMS API)
# ==========================================
GMS_KEY = os.getenv("GMS_KEY")  # SSAFY에서 발급받은 GMS 키를 입력하세요
BASE_URL = "https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
DATA_FILE = "C:\\Users\\Administrator\Desktop\\back\\PillGood-project-back\\pills\\fixtures\\pills_lite_final.json"

# SSL 인증서 검증 실패 시 경고 메시지 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    사용자의 입력(증상, 대상, 상황 등)을 분석하여
    데이터에서 가장 연관성 높은 제품 후보를 추립니다.
    """
    candidates = []
    user_keywords = user_input.split() # 공백 기준으로 단어 분리

    for item in data:
        fields = item.get('fields', {})
        name = fields.get('PRDLST_NM', '')
        function = fields.get('PRIMARY_FNCLTY', '')
        shape = fields.get('PRDT_SHAP_CD_NM', '')
        appearance = fields.get('DISPOS', '')
        
        # 점수 계산: 사용자 키워드가 기능성이나 이름에 포함되면 점수 부여
        score = 0
        for word in user_keywords:
            if len(word) >= 2: 
                if word in function: score += 2
                if word in name: score += 1
        
        candidates.append({
            "name": name,
            "function": function,
            "shape_info": f"{shape} ({appearance})",
            "usage": fields.get('NTK_MTHD', ''),
            "score": score
        })
    
    # 점수 높은 순으로 정렬 후 상위 5개 추출
    random.shuffle(candidates) 
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    return candidates[:5]

# ==========================================
# 4. AI 답변 생성 (PillGood 종합 추천)
# ==========================================
def generate_detailed_recommendation(user_input, products):
    """
    AI가 후보 제품을 분석하여, 선물용/개인용/건강관리용 등
    상황에 맞춰 유연하게 추천 멘트를 작성합니다.
    """
    if not products:
        return "죄송합니다. 데이터에서 적합한 제품을 찾기 어렵습니다. 조금 더 구체적으로 말씀해 주시겠어요?"

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
    당신은 사용자의 건강을 생각하는 헬스케어 멘토 **'PillGood(필굿)'**입니다.
    사용자는 **"{user_input}"**라는 고민이나 상황을 가지고 있습니다. (본인의 증상일 수도 있고, 누군가를 위한 선물일 수도 있습니다.)
    
    고객을 존중하는 정중한 태도(존댓말)를 유지하되, **핵심만 명확하게 전달**하는 전문가의 모습을 보여주세요.

    위 [후보 제품 목록] 중 사용자의 상황 해결에 가장 적합한 **단 하나의 제품**을 추천해 주세요.

    [작성 가이드 - 엄격 준수]
    1. **볼드체(**) 사용 금지**: 모든 텍스트는 일반 폰트로 깔끔하게 출력하세요.
    2. **다목적 추천**: 선물이면 선물하기 좋은 이유를, 본인이 먹는 것이면 증상 개선에 초점을 맞춰 설명하세요.
    3. **의학적 신중함**: 질병의 치료제가 아님을 유의하고, "~에 도움을 줄 수 있습니다"와 같이 표현하세요.
    4. **가독성**: 문단 사이를 띄워 읽기 편하게 하고, 선택 이유는 번호를 매겨 설명하세요.

    [출력 양식]
    🎁 추천 제품: (제품명)

    🧪 주요 성분 및 효능
    (핵심 성분명과 그 성분이 우리 몸에서 하는 역할을 요약)

    💊 형태 및 생김새
    (섭취 편의성을 고려하여 제형 정보를 설명)

    💡 PillGood의 선택 이유
    1. (사용자의 상황 "{user_input}"과 성분의 효능을 연결하여 설명)
    2. (제형의 장점이나 섭취 방법의 용이성, 혹은 라이프스타일 적합성 언급)

    ⚠️ 건강 안내
    본 추천은 건강기능식품에 대한 정보 제공을 목적으로 하며, 의학적 진단이나 치료를 대신할 수 없습니다. 증상이 심하거나 지속될 경우 반드시 병원을 방문하여 전문가의 진료를 받으시기 바랍니다.
    """

    # API 호출
    headers = {"Content-Type": "application/json"}
    url = f"{BASE_URL}?key={GMS_KEY}"
    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}]
    }

    try:
        # SSL 검증 건너뛰기
        response = requests.post(url, headers=headers, json=payload, verify=False)
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
    print("==================================================")
    print("  💊 안녕하세요, PillGood 입니다.")
    print("  상황이나 증상을 입력하시면 딱 맞는 영양제를 추천해드려요!")
    print("==================================================")
    print("  예시) '요즘 눈이 너무 침침해', '우리 아빠 생신 선물', '다이어트 중인데 변비가 심해'")
    
    all_data = load_data()
    
    if all_data:
        while True:
            user_input = input("\n👤 입력해주세요 (종료: q, quit, 종료, ㅂㅂ, 나가기): ")
            if user_input.lower() in ['q', 'quit', '종료', 'ㅂㅂ', '나가기']:
                print("\nPillGood을 이용해 주셔서 감사합니다. 건강한 하루 보내세요! 🌿")
                break
            
            print(f"🔍 '{user_input}'에 맞는 해결방법을 찾고 있어요! 조금만 기다려주세요!")
            
            # 1. 데이터 후보군 검색
            candidates = search_relevant_products(all_data, user_input)
            
            # 2. AI 상세 분석
            print("🤖 PillGood 전문가가 데이터를 분석하고 있습니다...")
            result = generate_detailed_recommendation(user_input, candidates)
            
            print("\n" + "-"*60)
            print(result)
            print("-"*60)