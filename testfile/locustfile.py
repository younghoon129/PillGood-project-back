from locust import HttpUser, task, between
import random
class WebsiteUser(HttpUser):
    wait_time = between(1, 3)
    
    # 존재하는 ID를 담아둘 장바구니
    valid_ids = []

    def on_start(self):
        """
        테스트 시작 전, 딱 1번만 실행되는 함수입니다.
        서버에서 영양제 목록을 받아와서 '실제 존재하는 ID'만 골라냅니다.
        """
        print("📢 현재 존재하는 영양제 ID 목록을 가져옵니다...")
        
        # 1. 목록 API 호출 (페이지네이션이 있다면 1페이지만 가져옵니다)
        response = self.client.get("/pills/")
        
        if response.status_code == 200:
            data = response.json()
            
            # 2. Django REST Framework의 응답 구조 확인 ('results' 키가 있는지)
            # 보통 페이지네이션이 있으면 data['results'] 안에 리스트가 있습니다.
            if isinstance(data, dict) and 'results' in data:
                pill_list = data['results']
            elif isinstance(data, list):
                pill_list = data
            else:
                pill_list = []

            # 3. 리스트에서 'id' 값만 뽑아서 저장 [3, 4, 10, 15 ...]
            if pill_list:
                self.valid_ids = [pill['id'] for pill in pill_list]
                print(f"✅ ID 로드 완료! 총 {len(self.valid_ids)}개의 영양제를 테스트합니다.")
            else:
                print("⚠️ 가져온 영양제 데이터가 없습니다!")
        else:
            print("❌ 목록을 가져오는데 실패했습니다.")

    @task
    def view_pill_detail(self):
        """
        위에서 확보한 valid_ids 목록 중에서만 랜덤으로 뽑습니다.
        """
        if self.valid_ids:
            # 존재하는 ID 중 하나를 랜덤 선택 (random.choice)
            target_id = random.choice(self.valid_ids)
            self.client.get(f"/pills/{target_id}/")
        else:
            # ID를 못 가져왔을 경우를 대비해 안전장치 (예: 1번 시도)
            self.client.get("/pills/3/")