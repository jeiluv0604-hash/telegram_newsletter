import os
import sys
import logging
import requests
import feedparser
from google import genai

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
# 3. RSS 피드 수집 (주식 분야 언론사 전용 피드로 교체하여 누락 방지)
# ---------------------------------------------------------
RSS_SOURCES = {
    "AI 관련 뉴스": "https://news.google.com/rss/search?q=AI&hl=ko&gl=KR&ceid=KR:ko",
    "주식시장 전망": "https://www.mk.co.kr/rss/50200011/",
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
            logger.info(f"[{category}] 수집된 뉴스 개수: {len(items)}개")
        except Exception as e:
            logger.error(f"RSS 피드 수집 오류 [{category}]: {e}")
            news_by_category[category] = []

    return news_by_category

# ---------------------------------------------------------
# 4. Gemini SDK 기반 뉴스 요약 리포트 생성
# ---------------------------------------------------------
def generate_summary_with_gemini(news_by_category):
    formatted_context = ""
    for cat_name, items in news_by_category.items():
        formatted_context += f"\n[{cat_name}]\n"
        if not items:
            formatted_context += " 수집된 뉴스가 없습니다.\n"
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
3. [주식시장 전망] 인사이트는 반드시 '📉 어제 증시 분석'과 '📈 오늘 증시 전망'으로 분리하여 작성하세요.
4. **[핵심] 수집 데이터에 제시된 모든 카테고리의 뉴스 제목과 링크는 하나도 빠짐없이 📰 주요 뉴스 목록에 포함**해 주세요.
5. 뉴스 항목과 뉴스 항목 사이에 빈 줄(한 줄 띄움)을 반드시 삽입하여 시원한 여백을 확보하세요.

[출력 양식 예시]
<b>📢 [오늘의 주요 뉴스 브리핑]</b>
───────────────────

<b>1. AI 관련 뉴스</b>

가. 💡 <b>인사이트</b>
(AI 기술 동향 3~5줄 내외 상세 분석)

나. 📰 <b>주요 뉴스</b>

• <b>뉴스 제목 1</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

• <b>뉴스 제목 2</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

───────────────────

<b>2. 주식시장 전망</b>

가. 💡 <b>인사이트</b>
📉 <b>[어제 증시 분석]</b> 어제 미/한 증시 동향 (2줄)

📈 <b>[오늘 증시 전망]</b> 오늘 증시 예상 및 포인트 (2~3줄)

나. 📰 <b>주요 뉴스</b>

• <b>뉴스 제목 1</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

• <b>뉴스 제목 2</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

───────────────────

<b>3. 개별종목 분석 (대덕전자, 한미반도체)</b>

가. 💡 <b>인사이트</b>
(종목 및 반도체/전자 동향 3~5줄 상세 분석)

나. 📰 <b>주요 뉴스</b>

• <b>뉴스 제목 1</b>
  <a href="링크">▶ 원본 뉴스 보기</a>
"""

    try:
        logger.info("Gemini SDK를 통해 뉴스를 요약 중...")
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        if response.text:
            logger.info("Gemini API 분석 및 줄간격 적용 완료")
            return response.text
            
    except Exception as e:
        logger.warning(f"Gemini API 호출 예외 발생: {e}")

    logger.error("Gemini API 호출 실패로 Fallback 메시지 생성")
    return build_fallback_summary(news_by_category)

def build_fallback_summary(news_by_category):
    """Fallback 발생 시에도 각 뉴스 항목 사이 빈 줄 적용"""
    output = [
        "<b>📢 [오늘의 주요 뉴스 브리핑]</b>",
        "───────────────────\n",
        
        "<b>1. AI 관련 뉴스</b>\n",
        "가. 💡 <b>인사이트</b>",
        "글로벌 AI 시장은 차세대 멀티모달 모델 도입과 생성형 AI의 산업 현장 적용이 가속화되고 있습니다.\n",
        "나. 📰 <b>주요 뉴스\n</b>"
    ]
    
    ai_items = news_by_category.get("AI 관련 뉴스", [])
    for item in ai_items:
        output.append(f"• <b>{item['title']}</b>\n  <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>\n")
    
    output.extend([
        "───────────────────\n",
        "<b>2. 주식시장 전망</b>\n",
        "가. 💡 <b>인사이트</b>\n",
        "📉 <b>[어제 증시 분석]</b> 주요 지수는 상단이 제한된 관망세 흐름을 보였습니다.\n",
        "📈 <b>[오늘 증시 전망]</b> 반도체 및 핵심주 위주의 기술적 반등 여부가 관전 포인트입니다.\n",
        "나. 📰 <b>주요 뉴스\n</b>"
    ])
    
    stock_items = news_by_category.get("주식시장 전망", [])
    for item in stock_items:
        output.append(f"• <b>{item['title']}</b>\n  <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>\n")

    output.extend([
        "───────────────────\n",
        "<b>3. 개별종목 분석 (대덕전자, 한미반도체)</b>\n",
        "가. 💡 <b>인사이트</b>",
        "한미반도체와 대덕전자는 AI 반도체 생태계의 핵심 수혜주로서 기술적 모멘텀이 이어지고 있습니다.\n",
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
