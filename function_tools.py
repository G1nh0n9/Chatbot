"""
OpenAI Function Calling을 위한 도구들과 함수 정의
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
from typing import Dict, Any, List, Optional
import re

def search_pokemon_rankings() -> Dict[str, Any]:
    """웹에서 포켓몬 랭킹 정보를 가져옵니다"""

    try:
        headers ={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        # Pokemon Home으로부터 역공학된 주소
        url = "https://resource.pokemon-home.com/battledata/t_rankmatch.html"

        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            html_content = response.text
            return {
                    'content': f"[포켓몬 공식 통계 검색 결과 HTML]\n검색 URL: {url}\n\n{html_content}",
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            return {
                'content': '포켓몬 랭킹 데이터를 가져올 수 없습니다.',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    except Exception as e:
        return {
            'content': f"포켓몬 통계 오류: {str(e)}",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def search_web(query: str) -> Dict[str, Any]:
    """웹에서 정보를 검색합니다 - 원본 HTML을 그대로 반환해서 OpenAI가 분석하게 함"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Google 검색 수행
        search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}&hl=ko&gl=kr"
        
        try:
            response = requests.get(search_url, headers=headers, timeout=15)
            if response.status_code == 200:
                # 원본 HTML을 그대로 반환 (길이 제한)
                html_content = response.text
                
                # HTML이 너무 길면 일부만 자르기 (OpenAI 토큰 제한 고려)
                if len(html_content) > 8000:
                    html_content = html_content[:8000] + "\n\n[HTML 내용이 길어서 일부만 표시됨]"
                
                return {
                    'query': query,
                    'content': f"[Google 검색 결과 HTML]\n검색 쿼리: {query}\n검색 URL: {search_url}\n\n{html_content}",
                    'source_url': search_url,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
        except Exception as e:
            print(f"Google search error: {e}")
        
        # 백업: DuckDuckGo 검색 
        try:
            ddg_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
            response = requests.get(ddg_url, headers=headers, timeout=10)
            if response.status_code == 200:
                html_content = response.text
                
                # HTML 길이 제한
                if len(html_content) > 6000:
                    html_content = html_content[:6000] + "\n\n[HTML 내용이 길어서 일부만 표시됨]"
                
                return {
                    'query': query,
                    'content': f"[DuckDuckGo 검색 결과 HTML]\n검색 쿼리: {query}\n검색 URL: {ddg_url}\n\n{html_content}",
                    'source_url': ddg_url,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
        except Exception as e:
            print(f"DuckDuckGo search error: {e}")
        
        # 마지막 백업: 네이버 검색
        try:
            naver_url = f"https://search.naver.com/search.naver?query={requests.utils.quote(query)}"
            response = requests.get(naver_url, headers=headers, timeout=10)
            if response.status_code == 200:
                html_content = response.text
                
                # HTML 길이 제한  
                if len(html_content) > 6000:
                    html_content = html_content[:6000] + "\n\n[HTML 내용이 길어서 일부만 표시됨]"
                
                return {
                    'query': query,
                    'content': f"[네이버 검색 결과 HTML]\n검색 쿼리: {query}\n검색 URL: {naver_url}\n\n{html_content}",
                    'source_url': naver_url,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
        except Exception as e:
            print(f"Naver search error: {e}")
        
        return {
            'query': query,
            'content': f"'{query}'에 대한 웹 검색을 수행했지만 HTML 내용을 가져올 수 없었습니다. 네트워크 연결을 확인해주세요.",
            'source_url': "",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        return {
            'query': query,
            'content': f"웹 검색 중 오류가 발생했습니다: {str(e)}",
            'source_url': "",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def get_weather(city: str = "서울") -> Dict[str, Any]:
    """특정 도시의 현재 날씨 정보를 가져옵니다"""
    try:
        # wttr.in API 사용 (실제 날씨 데이터)
        city_encoded = requests.utils.quote(city)
        url = f"https://wttr.in/{city_encoded}?format=j1&lang=ko"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            current = data['current_condition'][0]
            
            temp_c = current['temp_C']
            desc = current['lang_ko'][0]['value'] if current.get('lang_ko') else current['weatherDesc'][0]['value']
            humidity = current['humidity']
            feels_like = current['FeelsLikeC']
            
            content = f"현재 {city}의 날씨: {temp_c}°C (체감온도 {feels_like}°C), {desc}, 습도 {humidity}%"
            
            return {
                'city': city,
                'content': content,
                'weather_data': {
                    'temperature': f"{temp_c}°C",
                    'feels_like': f"{feels_like}°C",
                    'description': desc,
                    'humidity': f"{humidity}%"
                },
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            # 백업: Google 날씨 스크래핑
            search_query = f"{city} weather"
            google_url = f"https://www.google.com/search?q={search_query}"
            
            response = requests.get(google_url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            weather_info = {}
            
            # 온도 정보
            temp_elem = soup.find('span', {'id': 'wob_tm'})
            if temp_elem:
                weather_info['temperature'] = temp_elem.text + '°C'
            
            # 날씨 상태  
            desc_elem = soup.find('span', {'id': 'wob_dc'})
            if desc_elem:
                weather_info['description'] = desc_elem.text
                
            # 습도
            humidity_elem = soup.find('span', {'id': 'wob_hm'})
            if humidity_elem:
                weather_info['humidity'] = humidity_elem.text
                
            if weather_info:
                content = f"현재 {city}의 날씨: " + ", ".join([f"{v}" for v in weather_info.values()])
                return {
                    'city': city,
                    'content': content,
                    'weather_data': weather_info,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                return {
                    'city': city,
                    'content': f"{city}의 날씨 정보를 가져올 수 없습니다.",
                    'weather_data': {},
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
        
    except Exception as e:
        return {
            'city': city,
            'content': f"{city} 날씨 정보를 가져오는 중 오류가 발생했습니다: {str(e)}",
            'weather_data': {},
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def get_news(topic: str = "기술") -> Dict[str, Any]:
    """특정 주제의 최신 뉴스를 가져옵니다"""
    try:
        # 네이버 뉴스 검색 (실제 스크래핑)
        from urllib.parse import quote
        
        query = f"{topic}"
        encoded_query = quote(query)
        search_url = f"https://search.naver.com/search.naver?where=news&sm=tab_jum&query={encoded_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        news_items = []
        
        # 네이버 뉴스 제목 추출 (여러 선택자 시도)
        selectors = [
            'a.news_tit',
            'a[class*="news_tit"]',  
            '.news_tit',
            '.news_area .news_tit',
            '.bx .news_tit'
        ]
        
        for selector in selectors:
            news_elements = soup.select(selector)
            if news_elements:
                for elem in news_elements[:5]:
                    title = elem.get('title') or elem.text.strip()
                    if title and len(title) > 5:
                        news_items.append(title)
                break
                
        # 백업: 일반적인 뉴스 링크 찾기
        if not news_items:
            all_links = soup.find_all('a')
            for link in all_links:
                title = link.get('title') or link.text.strip()
                if title and len(title) > 10 and any(word in title.lower() for word in ['뉴스', 'news', topic.lower()]):
                    news_items.append(title)
                    if len(news_items) >= 3:
                        break
        
        if news_items:
            # 중복 제거
            unique_news = []
            for item in news_items:
                if item not in unique_news and len(item) > 5:
                    unique_news.append(item)
            
            content = f"최신 {topic} 뉴스 ({len(unique_news)}건):\n" + "\n".join([f"• {item}" for item in unique_news[:5]])
        else:
            content = f"{topic} 관련 뉴스를 네이버에서 찾고 있지만 파싱에 어려움이 있습니다. 직접 네이버 뉴스에서 확인해주세요."
            
        return {
            'topic': topic,
            'content': content,
            'news_items': news_items[:5] if news_items else [],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        return {
            'topic': topic,
            'content': f"{topic} 뉴스 정보를 가져오는 중 오류가 발생했습니다: {str(e)}",
            'news_items': [],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def get_current_time(timezone: str = "KST") -> Dict[str, Any]:
    """현재 시간 정보를 가져옵니다"""
    try:
        current_time = datetime.now()
        
        content = f"현재 시간: {current_time.strftime('%Y년 %m월 %d일 %H시 %M분 %S초')} ({timezone})"
        
        return {
            'timezone': timezone,
            'content': content,
            'formatted_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        return {
            'timezone': timezone,
            'content': f"시간 정보를 가져오는 중 오류가 발생했습니다: {str(e)}",
            'formatted_time': "",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def get_stock_info(symbol: str) -> Dict[str, Any]:
    """주식이나 환율 정보를 가져옵니다"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 환율 정보
        if symbol.upper() in ['USD', 'DOLLAR', '달러']:
            # 네이버 환율 페이지에서 USD/KRW 정보 가져오기
            url = "https://finance.naver.com/marketindex/exchangeDetail.nhn?marketindexCd=FX_USDKRW"
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 환율 정보 추출
            rate_elem = soup.select_one('.head_info .blind')
            if rate_elem:
                rate = rate_elem.text.strip()
                content = f"USD/KRW 환율: {rate}원"
            else:
                content = "USD 환율 정보를 가져올 수 없습니다."
                
        elif symbol.upper() in ['EUR', '유로']:
            url = "https://finance.naver.com/marketindex/exchangeDetail.nhn?marketindexCd=FX_EURKRW"
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            rate_elem = soup.select_one('.head_info .blind')
            if rate_elem:
                rate = rate_elem.text.strip()
                content = f"EUR/KRW 환율: {rate}원"
            else:
                content = "EUR 환율 정보를 가져올 수 없습니다."
                
        elif symbol.upper() in ['JPY', '엔']:
            url = "https://finance.naver.com/marketindex/exchangeDetail.nhn?marketindexCd=FX_JPYKRW"  
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            rate_elem = soup.select_one('.head_info .blind')
            if rate_elem:
                rate = rate_elem.text.strip()
                content = f"JPY/KRW 환율: {rate}원 (100엔 기준)"
            else:
                content = "JPY 환율 정보를 가져올 수 없습니다."
                
        else:
            # 주식 정보 - Yahoo Finance에서 가져오기 시도
            try:
                # Yahoo Finance API (비공식)
                if symbol == '삼성전자':
                    symbol = '005930.KS'
                elif symbol == 'SK하이닉스':
                    symbol = '000660.KS'
                    
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'chart' in data and data['chart']['result']:
                        result = data['chart']['result'][0]
                        meta = result['meta']
                        current_price = meta.get('regularMarketPrice', 0)
                        prev_close = meta.get('previousClose', 0)
                        change = current_price - prev_close if current_price and prev_close else 0
                        
                        content = f"{symbol} 주가: ${current_price:.2f} (전일대비 {change:+.2f})"
                    else:
                        content = f"{symbol} 주식 정보를 찾을 수 없습니다."
                else:
                    content = f"{symbol} 주식 정보에 접근할 수 없습니다."
            except:
                content = f"{symbol}의 금융 정보를 가져올 수 없습니다. 정확한 심볼을 확인해주세요."
        
        return {
            'symbol': symbol,
            'content': content,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'content': f"{symbol} 금융 정보를 가져오는 중 오류가 발생했습니다: {str(e)}",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

# OpenAI Function Calling을 위한 함수 스키마 정의
# ✅ Responses API 호환: flat schema로 수정
FUNCTION_DEFINITIONS = [
    {
        "type": "function",
        "name": "search_pokemon_rankings",
        "description": "포켓몬 공식 랭킹 통계 정보를 가져옵니다. 포켓몬 랭킹, 사용률, 메타 관련 질문에 사용합니다.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "search_web",
        "description": "웹에서 정보를 검색합니다. 사용자가 특정 정보를 찾거나 검색을 요청할 때 사용합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 키워드나 질문"}
            },
            "required": ["query"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_weather",
        "description": "특정 도시의 현재 날씨 정보를 가져옵니다. 날씨, 기온, 온도 관련 질문에 사용합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "날씨 정보를 확인할 도시 이름 (기본값: 서울)"}
            },
            "required": [],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_news",
        "description": "특정 주제의 최신 뉴스를 가져옵니다. 뉴스, 최신 소식 관련 질문에 사용합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "뉴스 주제 (예: 기술, 경제, 정치, 스포츠 등)"}
            },
            "required": ["topic"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_current_time",
        "description": "현재 시간 정보를 가져옵니다. 현재 시간, 날짜 관련 질문에 사용합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {"type": "string", "description": "시간대 (기본값: KST)"}
            },
            "required": [],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_stock_info",
        "description": "주식이나 환율 정보를 가져옵니다. 주가, 환율 관련 질문에 사용합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "주식 심볼이나 통화 코드 (예: USD, AAPL, 삼성전자 등)"}
            },
            "required": ["symbol"],
            "additionalProperties": False
        }
    }
]


# 함수 이름과 실제 함수 매핑
FUNCTION_MAP = {
    "search_pokemon_rankings": search_pokemon_rankings,
    "search_web": search_web,
    "get_weather": get_weather,
    "get_news": get_news,
    "get_current_time": get_current_time,
    "get_stock_info": get_stock_info
}

if __name__ == "__main__":
    # 간단한 테스트
    print(search_web("Python 프로그래밍"))
    print(get_weather("부산"))
    print(get_news("경제"))
    print(get_current_time())
    print(get_stock_info("AAPL"))