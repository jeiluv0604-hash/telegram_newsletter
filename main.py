import os
import sys
import logging
import requests
import feedparser

# ---------------------------------------------------------
# 1. 로깅 설정
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 2. 환경변수 검증
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def validate_env_vars():
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN (또는 TELEGRAM_TOKEN)")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    
    if missing:
        err_msg = f"[CRITICAL] 필수 환경변수가 설정되지 않았습니다: {', '.join(missing)}"
        logger.error(err_msg)
        raise ValueError(err_msg)

# ---------------------------------------------------------
# 3. RSS 피드 수집
# ---------------------------------------------------------
RSS_SOURCES = {
    "AI 관련 뉴스": "https://news.google.com/rss/search?q=AI+%EB%AA%A8%EB%8D%B8+%EC%B5%9C%EC%8B%A0+OR+AI+%EA%B8%B0%EC%88%A0&hl=ko&gl=KR&ceid=KR:ko",
    "주식시장 전망": "https://news.google.com/rss/search?q=%EB%AF%B8%EA%B5%AD+%EC%A3%BC%EC%8B%9D%EC%8B%9C%EC%9E%A5+%EC%A0%84%EB%A1%9D+OR+%ED%95%9C%EA%B5%AD+%EC%A3%BC%EC%8B%9D%EC%8B%9C%EC%9E%A5+%EC%A0%84%EB%A1%9D&hl=ko&gl=KR&ceid=KR:ko",
    "개별종목 분석(대덕전자, 한미반도체)": "https://news.google.com/rss/search?q=%ED%95%9C%EB%AF%B8%EB%B0%98%EB%8F%84%EC%B2%B4+OR+%EB%8C%80%EB%8D%95%EC%A0%84%EC%9E%90&hl=ko&gl=KR&ceid=KR:ko"
}

def fetch_rss_news():
    news_by_category = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for category, url in RSS_SOURCES.items():
        try:
            logger.info(f"RSS 피드 수집 중: {category}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            feed = feedparser.parse(response.content)
            entries = feed.entries[:3]

            items = []
            for entry in entries:
                items.append({
                    "title": entry.get("title", "제목 없음"),
                    "link": entry.get("link", "#")
                })
            news_by_category[category] = items
        except Exception as e:
            logger.error(f"RSS 피드 수집 오류 [{category}]: {e}")
            news_by_category[category] = []

    return news_by_category

# ---------------------------------------------------------
# 4. Gemini API 기반 뉴스별 줄간격 여백 극대화 리포트 생성
# ---------------------------------------------------------
def generate_summary_with_gemini(news_by_category):
    formatted_context = ""
    for cat_name, items in news_by_category.items():
        formatted_context += f"\n[{cat_name}]\n"
        for idx, item in enumerate(items, 1):
            formatted_context += f" {idx}. {item['title']} (링크: {item['link']})\n"

    prompt = f"""
당신은 대한민국 최고 수준의 AI/증시 아날리스트입니다.
아래 수집된 뉴스를 바탕으로 모바일(텔레그램) 화면에서 읽기 쉽도록 각 뉴스 항목 간 줄간격(여백)이 확보된 일일 뉴스레터를 작성해주세요.

[수집 데이터]
{formatted_context}

[가독성 & 줄간격 규칙]
1. 텔레그램 지원 HTML 태그만 사용 (<b>, <i>, <a>, <code>).
2. 카테고리 구분선(───────────────────)을 활용하세요.
3. [주식시장 전망] 인사이트는 반드시 **'📉 어제 증시 분석'**과 **'📈 오늘 증시 전망'**으로 분리하여 작성하세요.
4. [핵심] 뉴스 항목과 뉴스 항목 사이에 빈 줄(한 줄 띄움)을 반드시 삽입하여 개별 뉴스 간에 시원한 여백을 확보하세요.

[출력 양식 예시]
<b>📢 [오늘의 주요 뉴스 브리핑]</b>
───────────────────

<b>1. AI 관련 뉴스</b>

가. 💡 <b>인사이트</b>
(AI 기술 동향 3~5줄 내외 상세 분석)

나. 📰 <b>주요 뉴스</b>

• <b>뉴스 제목 1 요약</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

• <b>뉴스 제목 2 요약</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

• <b>뉴스 제목 3 요약</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

───────────────────

<b>2. 주식시장 전망</b>

가. 💡 <b>인사이트</b>
📉 <b>[어제 증시 분석]</b> 어제 미/한 증시 동향 (2줄)

📈 <b>[오늘 증시 전망]</b> 오늘 증시 예상 및 포인트 (2~3줄)

나. 📰 <b>주요 뉴스</b>

• <b>뉴스 제목 1 요약</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

• <b>뉴스 제목 2 요약</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

• <b>뉴스 제목 3 요약</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

───────────────────

<b>3. 개별종목 분석 (대덕전자, 한미반도체)</b>

가. 💡 <b>인사이트</b>
(종목 및 반도체/전자 동향 3~5줄 상세 분석)

나. 📰 <b>주요 뉴스</b>

• <b>뉴스 제목 1 요약</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

• <b>뉴스 제목 2 요약</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

• <b>뉴스 제목 3 요약</b>
  <a href="링크">▶ 원본 뉴스 보기</a>
"""

    gemini_urls = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    ]
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2540}
    }

    for gemini_url in gemini_urls:
        try:
            logger.info(f"Gemini API 호출 시도 중... ({gemini_url.split('/')[-1].split(':')[0]})")
            res = requests.post(gemini_url, json=payload, timeout=30)
            
            if not res.ok:
                logger.warning(f"Gemini API 응답 오류 [{res.status_code}]: {res.text}")
                continue

            data = res.json()
            candidates = data.get("candidates", [])
            if candidates and "parts" in candidates[0]["content"]:
                result_text = candidates[0]["content"]["parts"][0]["text"]
                logger.info("Gemini API 분석 및 줄간격 적용 완료")
                return result_text
        except Exception as e:
            logger.warning(f"Gemini API 호출 예외: {e}")
            continue

    logger.error("Gemini API 호출 실패로 줄간격 강화 Fallback 메시지 생성")
    return build_fallback_summary(news_by_category)

def build_fallback_summary(news_by_category):
    """Fallback 발생 시에도 각 뉴스 항목 사이 빈 줄(줄간격) 적용"""
    output = [
        "<b>📢 [오늘의 주요 뉴스 브리핑]</b>",
        "───────────────────\n",
        
        "<b>1. AI 관련 뉴스</b>\n",
        "가. 💡 <b>인사이트</b>",
        "글로벌 AI 시장은 차세대 멀티모달 모델 도입과 생성형 AI의 산업 현장 적용이 가속화되고 있습니다. 주요 빅테크들의 독자 모델 개발 경쟁이 격화되는 가운데 서비스 상용화 속도가 기업 가치를 좌우할 핵심 요소로 떠오르고 있습니다.\n",
        "나. 📰 <b>주요 뉴스\n</b>"
    ]
    
    ai_items = news_by_category.get("AI 관련 뉴스", [])
    for item in ai_items:
        output.append(f"• <b>{item['title']}</b>\n  <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>\n")
    
    output.extend([
        "───────────────────\n",
        "<b>2. 주식시장 전망</b>\n",
        "가. 💡 <b>인사이트</b>\n",
        "📉 <b>[어제 증시 분석]</b> 미 연준의 금리 향방 발표를 앞두고 관망세가 짙어진 가운데, 기술주 중심의 이익 실현 매물이 출회되며 증시 상단이 제약되었습니다.\n",
        "📈 <b>[오늘 증시 전망]</b> 반도체 업종 중심의 실적 모멘텀이 유효한 만큼 하방 지지력이 형성될 전망이며, 기술주 수급 유입 여부가 오늘 지수 반등의 핵심 관전 포인트입니다.\n",
        "나. 📰 <b>주요 뉴스\n</b>"
    ])
    
    stock_items = news_by_category.get("주식시장 전망", [])
    for item in stock_items:
        output.append(f"• <b>{item['title']}</b>\n  <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>\n")

    output.extend([
        "───────────────────\n",
        "<b>3. 개별종목 분석 (대덕전자, 한미반도체)</b>\n",
        "가. 💡 <b>인사이트</b>",
        "HBM 필수 고성능 장비(TC 본더) 시장을 독점 공급하는 한미반도체와 AI 서버용 high-end 기판(FC-BGA) 공급을 늘리는 대덕전자는 차세대 반도체 패키징 시장 확대에 따라 중장기적 수혜 흐름을 이어나갈 것으로 예상됩니다.\n",
        "나. 📰 <b>주요 뉴스\n</b>"
    ])
    
    comp_items = news_by_category.get("개별종목 분석(대덕전자, 한미반도체)", [])
    for item in comp_items:
        output.append(f"• <b>{item['title']}</b>\n  <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>\n")

    return "\n".join(output)

# ---------------------------------------------------------
# 5. 텔레그램 메시지 전송
# ---------------------------------------------------------
def send_telegram_message(text):
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    CHUNK_SIZE = 4000
    chunks = [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

    for idx, chunk in enumerate(chunks):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            logger.info(f"텔레그램 메시지 전송 중 ({idx+1}/{len(chunks)})...")
            res = requests.post(telegram_url, json=payload, timeout=10)
            
            if not res.ok and "can't parse entities" in res.text:
                logger.warning("HTML 파싱 에러 발생. Plain Text로 재전송합니다.")
                payload["parse_mode"] = None
                res = requests.post(telegram_url, json=payload, timeout=10)
                
            res.raise_for_status()
            logger.info(f"텔레그램 메시지 전송 성공 ({idx+1}/{len(chunks)})")
        except Exception as e:
            logger.error(f"텔레그램 메시지 전송 실패: {e}")
            raise e

# ---------------------------------------------------------
# 6. 메인 실행 함수
# ---------------------------------------------------------
def main():
    logger.info("=== 텔레그램 일일 뉴스 서비스 실행 시작 ===")
    try:
        validate_env_vars()
        news_by_category = fetch_rss_news()

        summary_report = generate_summary_with_gemini(news_by_category)
        send_telegram_message(summary_report)
        logger.info("=== 텔레그램 일일 뉴스 서비스 성공적 완료 ===")

    except Exception as e:
        logger.critical(f"프로그램 실행 중 예외 발생: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
