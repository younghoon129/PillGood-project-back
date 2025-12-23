import requests
import re
from django.conf import settings
import json
import random
import urllib3
import os
from dotenv import load_dotenv
load_dotenv()

def clean_text(text):
    """
    텍스트 정규화: 
    1. 괄호 안의 내용((포도맛) 등)은 제거
    2. 특수문자 제거
    """
    if not text: return ""
    text = re.sub(r'\(.*?\)', '', text) 
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'(주식회사|유한회사|농업회사법인)', '', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    return text.strip()

def extract_amount(text):
    """
    [추가됨] 텍스트에서 수량과 단위를 추출
    Return: (숫자, 단위타입)
    - 단위타입: 'C' (Count, 갯수), 'D' (Day, 기간), '' (없음)
    """
    if not text: return (0, "")
    
    # 대소문자 무시 (ea, T, Month 등 처리를 위해)
    text = text.lower()
    
    # -----------------------------------------------------
    # 1. 갯수 (Count) 찾기 -> 타입 'C'
    # 정, 캡슐, 알, 개, 포, 병, 스틱, 매 + ea, t(타블렛), c(캡슐)
    # -----------------------------------------------------
    pattern_units = r'(정|캡슐|알|개|포|병|스틱|매|ea|t|c)\b'
    
    # 1-1. "120정", "30ea" 패턴
    match_count = re.search(r'(\d+)\s*' + pattern_units, text)
    if match_count:
        return (int(match_count.group(1)), "C")

    # 1-2. 곱하기 패턴 ("300mg x 120캡슐") -> 뒤에꺼 가져옴
    match_mul = re.search(r'x\s*(\d+)\s*' + pattern_units, text)
    if match_mul:
        return (int(match_mul.group(1)), "C")
    
    # -----------------------------------------------------
    # 2. 기간 (Day) 찾기 -> 타입 'D' (날짜로 환산)
    # -----------------------------------------------------
    
    # 2-1. "개월" (1개월 = 30일)
    match_month = re.search(r'(\d+)\s*(개월|달|month)', text)
    if match_month:
        return (int(match_month.group(1)) * 30, "D")
        
    # 2-2. "주" (1주 = 7일)
    match_week = re.search(r'(\d+)\s*(주|week)', text)
    if match_week:
        return (int(match_week.group(1)) * 7, "D")

    # 못 찾으면 0 반환
    return (0, "")

def is_exact_match(db_name, api_title):
    """[초엄격 검사] 띄어쓰기 무시 후 완전 일치 확인"""
    s1 = clean_text(db_name)
    s2 = clean_text(api_title)
    
    s1_nospace = s1.replace(" ", "")
    s2_nospace = s2.replace(" ", "")
    
    if not s1_nospace: return False

    if s1_nospace in s2_nospace:
        return True
        
    # print(f"   ❌ 엄격 불일치 탈락 (DB: {s1_nospace} vs API: {s2_nospace})")
    return False

def is_valid_match(db_company, db_product, api_item):
    """제조사 검증 + 초엄격 제품명 검증"""
    clean_db_company = clean_text(db_company)
    api_full_text = f"{api_item.get('title', '')} {api_item.get('brand', '')} {api_item.get('maker', '')}"
    clean_api_text = clean_text(api_full_text)
    
    company_match = False
    if len(clean_db_company) < 2:
        company_match = True
    elif clean_db_company in clean_api_text:
        company_match = True
    else:
        parts = clean_db_company.split()
        if len(parts) >= 2 and "".join(parts[:2]) in clean_api_text.replace(" ", ""):
            company_match = True
            
    if not company_match:
        return False 

    return is_exact_match(db_product, api_item.get('title', ''))

def get_purchase_link(product_name, company_name):
    clean_prod = clean_text(product_name)
    clean_comp = clean_text(company_name)
    
    # 1차 검색
    query = f"{clean_comp} {clean_prod}"
    item = search_naver_shopping(query)
    
    if item and is_valid_match(company_name, product_name, item):
        return format_result(item)
    
    # 2차 검색
    item = search_naver_shopping(clean_prod)
    
    if item and is_valid_match(company_name, product_name, item):
        return format_result(item)
            
    return None

def search_naver_shopping(query):
    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {
        "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": settings.NAVER_SECRET_KEY # settings 변수명 확인 필요
    }
    params = {"query": query, "display": 1, "sort": "sim"}
    
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            data = res.json()
            if data['items']: return data['items'][0]
    except:
        pass
    return None

def format_result(item):
    """
    [수정됨] 수량(amount)과 단위(unit_type)까지 추출해서 반환
    """
    amt, unit = extract_amount(item['title']) # 튜플 분해 (숫자, 단위)
    
    return {
        "link": item['link'],
        "price": int(item['lprice']),
        "mall": item['mallName'],
        "image": item['image'],
        "amount": amt,      # 숫자 (예: 120)
        "unit_type": unit   # 단위 (예: 'C' 또는 'D')
    }

# ---------------------------- AI 영양제 추천 서비스 -----------------------------------------------------------
# SSL 인증서 경고 제어
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. 설정 (SSAFY GMS API)
# ==========================================
GMS_KEY = os.getenv("GMS_KEY")
BASE_URL = "https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"

# 장고 프로젝트 상대 경로로 수정 
DATA_FILE = os.path.join(settings.BASE_DIR, 'pills', 'fixtures', 'pills_lite_final.json')

# ==========================================
# 2. 데이터 로드
# ==========================================
def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 오류: '{DATA_FILE}' 파일이 없습니다.")
        return []

# ==========================================
# 3.  스마트 검색 (데이터 기반 검색)
# ==========================================
def search_relevant_products(data, user_input):
    candidates = []
    user_keywords = user_input.split()

    for item in data:
        fields = item.get('fields', {})
        name = fields.get('PRDLST_NM', '')
        function = fields.get('PRIMARY_FNCLTY', '')
        shape = fields.get('PRDT_SHAP_CD_NM', '')
        appearance = fields.get('DISPOS', '')
        
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
    
    random.shuffle(candidates) 
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    return candidates[:5]

# ==========================================
# 4. AI 답변 생성 
# ==========================================
def generate_detailed_recommendation(user_input, products):
    if not products:
        return "죄송합니다. 데이터에서 적합한 제품을 찾기 어렵습니다. 조금 더 구체적으로 말씀해 주시겠어요?"

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

    headers = {"Content-Type": "application/json"}
    url = f"{BASE_URL}?key={GMS_KEY}"
    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=10)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"API 호출 오류: {response.text}"
    except Exception as e:
        return f"오류 발생: {e}"

# ==========================================
# 5. [추가] 뷰에서 호출할 통합 인터페이스
# ==========================================
def get_pill_recommendation(user_input):
    data = load_data()
    if not data:
        return "영양제 데이터를 불러올 수 없습니다."
    
    candidates = search_relevant_products(data, user_input)
    return generate_detailed_recommendation(user_input, candidates)
# ----------------------------------------------------------------------------------------------------------