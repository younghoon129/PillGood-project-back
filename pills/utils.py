import requests
import re
from django.conf import settings

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
        "amount": amt,      # 숫자 (예: 120)
        "unit_type": unit   # 단위 (예: 'C' 또는 'D')
    }