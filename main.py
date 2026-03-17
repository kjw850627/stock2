import requests
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import time
from datetime import datetime
import os
from io import BytesIO

# ==========================================
# 1. 사용자 설정 (반드시 수정하세요)
# ==========================================
TELEGRAM_TOKEN = '8731197230:AAEOSo0tGJY_qIDfFgfkMFz0xtyQt3KCa_k'
CHAT_ID = '1579761680'
# 깃허브에 올린 폰트의 'Raw' 주소를 입력하세요.
FONT_URL = "https://github.com/kjw850627/stock2/blob/main/NanumGothic-Regular.ttf"
# ==========================================

# 전역 변수: 직전 데이터를 저장
prev_df = None

def setup_font():
    """폰트가 없으면 다운로드하고 matplotlib에 등록합니다."""
    font_path = "NanumGothic-Regular.ttf"
    if not os.path.exists(font_path):
        print(">>> 폰트 다운로드 중...")
        try:
            res = requests.get(FONT_URL)
            res.raise_for_status()
            with open(font_path, 'wb') as f:
                f.write(res.content)
            print(">>> 폰트 다운로드 완료.")
        except Exception as e:
            print(f"❌ 폰트 다운로드 실패: {e}")
            return False
    
    fm.fontManager.addfont(font_path)
    prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = prop.get_name()
    plt.rcParams['axes.unicode_minus'] = False
    print(f">>> 폰트 설정 완료: {prop.get_name()}")
    return True

def get_current_market_data():
    """네이버 증권에서 현재 업종별 데이터를 가져옵니다."""
    url = "https://finance.naver.com/sise/sise_group.naver?type=upjong"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content.decode('euc-kr', 'replace'), 'html.parser')
        rows = soup.select('table.type_1 tr')
        
        data = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                name = cols[0].get_text(strip=True)
                rate = cols[1].get_text(strip=True).replace('%', '')
                vol = cols[5].get_text(strip=True).replace(',', '')
                if name and vol.isdigit():
                    data.append({
                        '업종명': name,
                        '등락률': float(rate) if rate else 0.0,
                        '거래대금': int(vol)
                    })
        return pd.DataFrame(data).set_index('업종명')
    except Exception as e:
        print(f"❌ 데이터 수집 중 오류: {e}")
        return None

def send_telegram_report(image_path, caption):
    """분석된 이미지와 글을 텔레그램으로 전송합니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(image_path, 'rb') as photo:
            payload = {'chat_id': CHAT_ID, 'caption': caption}
            files = {'photo': photo}
            requests.post(url, data=payload, files=files)
        print(">>> 텔레그램 리포트 전송 성공!")
    except Exception as e:
        print(f"❌ 텔레그램 전송 실패: {e}")

def analyze_and_report():
    """자금 유입을 분석하고 차트를 생성하여 전송합니다."""
    global prev_df
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M')
    
    print(f"\n[{now_str}] 실시간 데이터 분석 중...")
    curr_df = get_current_market_data()
    
    if curr_df is None: return

    # 직전 데이터가 있을 때만 자금 이동(증분) 분석
    if prev_df is not None:
        flow_df = curr_df.copy()
        # 현재 누적 거래대금 - 직전 누적 거래대금 = 최근 1시간 유입액
        flow_df['자금유입'] = curr_df['거래대금'] - prev_df['거래대금']
        
        # 유입액이 0보다 큰 상위 15개 섹터만 추출
        flow_df = flow_df[flow_df['자금유입'] > 0].sort_values('자금유입', ascending=True).tail(15)

        if not flow_df.empty:
            # 시각화 설정
            plt.figure(figsize=(12, 10))
            # 등락률에 따라 빨강/파랑 색상 지정
            colors = ['#ff4d4d' if x > 0 else '#4d94ff' if x < 0 else '#cccccc' for x in flow_df['등락률']]
            
            bars = plt.barh(flow_df.index, flow_df['자금유입'], color=colors, edgecolor='black', alpha=0.8)
            
            # 레이블 표시 (유입 금액 + 현재 등락률)
            max_val = flow_df['자금유입'].max()
            for bar, rate in zip(bars, flow_df['등락률']):
                val = bar.get_width()
                label = f" +{int(val/100):,}억 ({'+' if rate > 0 else ''}{rate}%)"
                plt.text(val + (max_val * 0.01), bar.get_y() + bar.get_height()/2, 
                         label, va='center', fontsize=10, fontweight='bold')

            plt.title(f'최근 1시간 섹터별 자금 유입 TOP 15\n({now_str})', fontsize=18, pad=30)
            plt.xlabel('신규 유입 거래대금 (단위: 백만원)', fontsize=12)
            plt.grid(axis='x', linestyle='--', alpha=0.3)
            plt.tight_layout()

            # 이미지 저장 및 전송
            img_path = "fund_flow_report.png"
            plt.savefig(img_path, dpi=300)
            plt.close()

            top_sector = flow_df.index[-1]
            caption = f"📊 {now_str} 자금 흐름 보고서\n\n🔥 최근 1시간 가장 뜨거운 섹터: [{top_sector}]\n\n※ 빨간색: 상승 섹터 / 파란색: 하락 섹터"
            send_telegram_report(img_path, caption)
        else:
            print(">>> 변경된 자금 유입 데이터가 없습니다. (장 종료 후 등)")
    else:
        print(">>> 첫 번째 데이터를 수집했습니다. 1시간 뒤부터 분석 결과가 발송됩니다.")
    
    # 현재 데이터를 다음 비교를 위해 저장
    prev_df = curr_df.copy()

# ==========================================
# 메인 실행 루프
# ==========================================
if __name__ == "__main__":
    print("------------------------------------------")
    print("  KOSPI/KOSDAQ 섹터 자금 이동 추적 봇 가동")
    print("------------------------------------------")
    
    if setup_font():
        while True:
            # 장 운영 시간(09:00 ~ 16:00)에만 세밀하게 보고 싶다면 아래 조건문을 활용하세요.
            # if 9 <= datetime.now().hour <= 16:
            analyze_and_report()
            
            print(f">>> 다음 분석까지 1시간 대기합니다...")
            time.sleep(3600) # 1시간(3600초) 대기
    else:
        print("❌ 폰트 설정 실패로 프로그램을 종료합니다.")
