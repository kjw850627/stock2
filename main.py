import requests
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
import time
from datetime import datetime
import os
from io import BytesIO

# --- 설정 정보 (본인의 정보로 수정하세요) ---
TELEGRAM_TOKEN = '8731197230:AAEOSo0tGJY_qIDfFgfkMFz0xtyQt3KCa_k'
CHAT_ID = '1579761680'
# ---------------------------------------

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

prev_df = None # 직전 데이터를 저장할 변수

def get_sector_data():
    url = "https://finance.naver.com/sise/sise_group.naver?type=upjong"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.content.decode('euc-kr', 'replace'), 'html.parser')
        rows = soup.select('table.type_1 tr')
        
        data = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                name = cols[0].get_text(strip=True)
                rate = cols[1].get_text(strip=True).replace('%', '')
                vol = cols[5].get_text(strip=True).replace(',', '')
                if name and vol.isdigit():
                    data.append({'업종명': name, '등락률': float(rate), '거래대금': int(vol)})
        return pd.DataFrame(data).set_index('업종명')
    except Exception as e:
        print(f"데이터 수집 에러: {e}")
        return None

def send_telegram_image(image_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(image_path, 'rb') as photo:
            payload = {'chat_id': CHAT_ID, 'caption': caption}
            files = {'photo': photo}
            requests.post(url, data=payload, files=files)
        print(">>> 텔레그램 전송 완료!")
    except Exception as e:
        print(f"텔레그램 전송 에러: {e}")

def run_analysis():
    global prev_df
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"\n[{now_str}] 분석 시작...")
    
    curr_df = get_sector_data()
    if curr_df is None: return

    if prev_df is not None:
        # 1. 자금 이동 계산 (현재 거래대금 - 직전 거래대금)
        flow_df = curr_df.copy()
        flow_df['자금유입'] = curr_df['거래대금'] - prev_df['거래대금']
        
        # 유입량이 많은 상위 15개 선정 (데이터가 0보다 큰 경우만)
        flow_df = flow_df[flow_df['자금유입'] > 0].sort_values('자금유입', ascending=True).tail(15)

        if not flow_df.empty:
            # 2. 차트 생성
            plt.figure(figsize=(11, 9))
            colors = ['#ff4d4d' if x > 0 else '#4d94ff' for x in flow_df['등락률']]
            bars = plt.barh(flow_df.index, flow_df['자금유입'], color=colors, alpha=0.8)
            
            for bar, rate in zip(bars, flow_df['등락률']):
                val = bar.get_width()
                plt.text(val, bar.get_y() + bar.get_height()/2, 
                         f" +{int(val/100):,}억 ({rate}%)", va='center', fontweight='bold')

            plt.title(f"최근 1시간 자금 유입 TOP 15\n({now_str})", fontsize=16, pad=20)
            plt.xlabel("추가 유입 금액 (단위: 백만원)")
            plt.tight_layout()
            
            # 3. 이미지 저장 및 전송
            img_path = "current_flow.png"
            plt.savefig(img_path, dpi=300)
            plt.close()
            
            caption = f"📊 {now_str} 자금 이동 리포트\n지난 1시간 동안 돈이 가장 많이 쏠린 섹터 순위입니다."
            send_telegram_image(img_path, caption)
        else:
            print(">>> 거래대금 변화가 없습니다 (장 폐쇄 시간 등).")
    else:
        print(">>> 첫 데이터 수집 완료. 1시간 뒤부터 분석 리포트가 전송됩니다.")
    
    prev_df = curr_df.copy()

# 메인 루프
if __name__ == "__main__":
    print("🚀 자금 이동 추적 봇 가동 시작!")
    while True:
        # 장 중(오전 9시 ~ 오후 4시)에만 실행하고 싶다면 아래 주석을 해제하세요.
        # now_hour = datetime.now().hour
        # if 9 <= now_hour <= 16:
        run_analysis()
        
        time.sleep(3600) # 1시간 대기   
