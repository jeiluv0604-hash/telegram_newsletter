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
# 4. Gemini SDK 기반 뉴스 요약 및 심층 인사이트 리포트 생성
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
당신은 대한민국 최고 수준의 AI/증시 수석 아날리스트입니다.
아래 수집된 오늘 자 실시간 뉴스 헤드라인 데이터만을 바탕으로, 각 카테고리별 깊이 있는 심층 분석 인사이트와 뉴스 브리핑을 작성해주세요.

[수집 데이터]
{formatted_context}

[작성 지침 및 분석 가이드]
1. **💡 인사이트 작성 규칙 (매일 가변적·세부적 분석 필수)**:
   - 일반적이고 상투적인 문구(예: "멀티모달 가속화", "관망세 지속")를 절대 반복 사용하지 마세요.
   - [수집 데이터]에 제공된 뉴스 제목들 간의 연관성을 분석하여, 오늘 뉴스들이 시사하는 **구체적인 기술 트렌드, 시장 수급 변화, 기업 실적 및 산업 파급효과**를 3~5줄 내외로 논리적으로 추론 및 분석하세요.
   - [주식시장 전망] 카테고리의 인사이트는 반드시 **'📉 어제 증시 분석'**과 **'📈 오늘 증시 전망'**으로 구체적 기사 맥락을 담아 분리 작성하세요.

2. **가독성 및 출력 규칙**:
   - 텔레그램 지원 HTML 태그만 사용 (<b>, <i>, <a>, <code>).
   - 카테고리 구분선(───────────────────)을 활용하세요.
   - 제공된 모든 뉴스의 제목과 링크는 하나도 빠짐없이 📰 주요 뉴스 목록에 포함하세요.
   - 개별 뉴스 항목 사이에는 빈 줄(한 줄 띄움)을 반드시 넣어 여백을 확보하세요.

[출력 양식]
<b>📢 [오늘의 주요 뉴스 브리핑]</b>
───────────────────

<b>1. AI 관련 뉴스</b>

가. 💡 <b>인사이트</b>
(오늘 수집된 AI 뉴스를 종합 분석한 구체적 심층 인사이트 3~5줄)

나. 📰 <b>주요 뉴스</b>

• <b>뉴스 제목 1</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

• <b>뉴스 제목 2</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

───────────────────

<b>2. 주식시장 전망</b>

가. 💡 <b>인사이트</b>
📉 <b>[어제 증시 분석]</b> (뉴스 기사 기반 어제 시장 특징 2줄)

📈 <b>[오늘 증시 전망]</b> (뉴스 기사 기반 오늘 시장 대응 전략 2~3줄)

나. 📰 <b>주요 뉴스</b>

• <b>뉴스 제목 1</b>
  <a href="링크">▶ 원본 뉴스 보기</a>

───────────────────

<b>3. 개별종목 분석 (대덕전자, 한미반도체)</b>

가. 💡 <b>인사이트</b>
(한미반도체/대덕전자 관련 최신 뉴스 종합 심층 분석 3~5줄)

나. 📰 <b>주요 뉴스</b>

• <b>뉴스 제목 1</b>
  <a href="링크">▶ 원본 뉴스 보기</a>
"""

    try:
        logger.info("Gemini SDK를 통해 심층 인사이트 뉴스 요약을 생성 중...")
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        if response.text:
            logger.info("Gemini API 심층 분석 완료")
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
        "가. 💡 <b>인사이트</b>\n",
        "최신 글로벌 AI 시장 트렌드와 기업들의 기술 도입 속도가 한층 가속화되고 있습니다.\n",
        "나. 📰 <b>주요 뉴스\n</b>"
    ]
    
    ai_items = news_by_category.get("AI 관련 뉴스", [])
    for item in ai_items:
        output.append(f"• <b>{item['title']}</b>\n  <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>\n")
    
    output.extend([
        "───────────────────\n",
        "<b>2. 주식시장 전망</b>\n",
        "가. 💡 <b>인사이트</b>\n",
        "📉 <b>[어제 증시 분석]</b> 주요 지수는 개별 모멘텀에 따라 차별화된 흐름을 보였습니다.\n",
        "📈 <b>[오늘 증시 전망]</b> 핵심 반도체 및 주력 섹터의 수급 유입 여부가 주요 관전 포인트입니다.\n",
        "나. 📰 <b>주요 뉴스\n</b>"
    ])
    
    stock_items = news_by_category.get("주식시장 전망", [])
    for item in stock_items:
        output.append(f"• <b>{item['title']}</b>\n  <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>\n")

    output.extend([
        "───────────────────\n",
        "<b>3. 개별종목 분석 (대덕전자, 한미반도체)</b>\n",
        "가. 💡 <b>인사이트</b>\n",
        "한미반도체와 대덕전자는 글로벌 반도체 투자 동향과 실적 모멘텀에 직접적인 영향을 받고 있습니다.\n",
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
