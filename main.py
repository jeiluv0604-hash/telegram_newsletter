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
# 2. 환경변수 검증 (TELEGRAM_BOT_TOKEN / TELEGRAM_TOKEN 호환)
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
# 3. RSS 피드 수집 (모든 카테고리별 균등 수집: 각 2개씩 총 6개 고정)
# ---------------------------------------------------------
RSS_SOURCES = {
    "AI 최신 모델 및 전망": "https://news.google.com/rss/search?q=AI+%EB%AA%A8%EB%8D%B8+%EC%B5%9C%EC%8B%A0+OR+AI+%EA%B8%B0%EC%88%A0+%EC%A0%84%EB%A1%9D&hl=ko&gl=KR&ceid=KR:ko",
    "미국/한국 주식시장 예측": "https://news.google.com/rss/search?q=%EB%AF%B8%EA%B5%AD+%EC%A3%BC%EC%8B%9D%EC%8B%9C%EC%9E%A5+%EC%A0%84%EB%A1%9D+OR+%ED%95%9C%EA%B5%AD+%EC%A3%BC%EC%8B%9D%EC%8B%9C%EC%9E%A5+%EC%A0%84%EB%A1%9D&hl=ko&gl=KR&ceid=KR:ko",
    "한미반도체/대덕전자 뉴스": "https://news.google.com/rss/search?q=%ED%95%9C%EB%AF%B8%EB%B0%98%EB%8F%84%EC%B2%B4+OR+%EB%8C%80%EB%8D%95%EC%A0%84%EC%9E%90&hl=ko&gl=KR&ceid=KR:ko"
}

def fetch_rss_news():
    news_data = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for category, url in RSS_SOURCES.items():
        try:
            logger.info(f"RSS 피드 수집 중: {category}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            feed = feedparser.parse(response.content)
            # 카테고리 편중 방지를 위해 각 카테고리당 정확히 상위 2개씩 선택
            entries = feed.entries[:2]

            for entry in entries:
                news_data.append({
                    "category": category,
                    "title": entry.get("title", "제목 없음"),
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", "")
                })
        except Exception as e:
            logger.error(f"RSS 피드 수집 오류 [{category}]: {e}")
            continue

    return news_data

# ---------------------------------------------------------
# 4. Gemini API 분석 및 요약 리포트 생성 (인사이트 필수 + 균등 노출)
# ---------------------------------------------------------
def generate_summary_with_gemini(raw_news):
    if not raw_news:
        return "<b>[알림]</b> 오늘 수집된 신규 뉴스가 없습니다."

    news_text_list = []
    for idx, item in enumerate(raw_news, 1):
        news_text_list.append(f"{idx}. [{item['category']}] {item['title']}\n   링크: {item['link']}")
    
    news_context = "\n".join(news_text_list)

    prompt = f"""
당신은 대한민국 최고 수준의 AI/증시 수석 아날리스트입니다.
제공된 뉴스를 바탕으로 모든 카테고리의 주요 소식과 인사이트가 무조건 포함된 텔레그램 일일 보고서를 작성하세요.

[수집된 뉴스 데이터 목록]
{news_context}

[필수 요구조건 - 무조건 준수!]
1. 텔레그램 HTML 태그(<b>, <i>, <a>, <code>)만 사용하세요.
2. 아래 [출력 양식]의 💡 **인사이트 섹션 3개(공통 인사이트, AI 인사이트, 주식 인사이트)**를 절대로 생략하지 말고, 각각 3~5줄 이상 알차고 구체적으로 강제 작성하세요.
3. 특정 카테고리가 누락되지 않도록 뉴스 섹션에서 **[AI 최신 모델] 2개**, **[미국/한국 증시 예측] 2개**, **[한미반도체/대덕전자] 2개**의 뉴스를 균등하게 포함하여 작성하세요 (총 6개 뉴스).
4. 뉴스 요약 끝에는 반드시 <a href="링크">▶ 원본 뉴스 보기</a> 링크를 포함하세요.

[출력 양식]
<b>📌 오늘의 인사이트 (공통)</b>
(전체 AI 발전과 증시 흐름을 아우르는 통찰력 있는 총평 3줄 필수 작성)

<b>🤖 1. AI 최신 모델 및 전망</b>
💡 <b>AI 핵심 인사이트 (3~5줄)</b>:
(최신 AI 모델, 기술 동향 및 향후 산업 영향에 대한 3~5줄 상세 분석 필수 작성)

• <b>[AI 뉴스 1 제목]</b>: 요약 내용 <a href="링크">▶ 원본 뉴스 보기</a>
• <b>[AI 뉴스 2 제목]</b>: 요약 내용 <a href="링크">▶ 원본 뉴스 보기</a>

<b>📈 2. 주식시장 전망</b>
💡 <b>주식 핵심 인사이트 (3~5줄)</b>:
(미국/한국 증시 전망 및 반도체/전자 산업에 대한 3~5줄 상세 분석 필수 작성)

<b>[가. 미국시장, 한국시장 주식시장 예측]</b>
• <b>[증시 예측 뉴스 1 제목]</b>: 요약 내용 <a href="링크">▶ 원본 뉴스 보기</a>
• <b>[증시 예측 뉴스 2 제목]</b>: 요약 내용 <a href="링크">▶ 원본 뉴스 보기</a>

<b>[나. 한미반도체, 대덕전자 관련 주요 뉴스]</b>
• <b>[개별종목 뉴스 1 제목]</b>: 요약 내용 <a href="링크">▶ 원본 뉴스 보기</a>
• <b>[개별종목 뉴스 2 제목]</b>: 요약 내용 <a href="링크">▶ 원본 뉴스 보기</a>
"""

    gemini_urls = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    ]
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2540}
    }

    for gemini_url in gemini_urls:
        try:
            logger.info("Gemini API 호출 중...")
            res = requests.post(gemini_url, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json()
            
            candidates = data.get("candidates", [])
            if candidates and "parts" in candidates[0]["content"]:
                result_text = candidates[0]["content"]["parts"][0]["text"]
                logger.info("Gemini API 분석 완료 (인사이트 및 균등 뉴스 생성됨)")
                return result_text
        except Exception as e:
            logger.warning(f"Gemini API ({gemini_url.split('/')[-1]}) 호출 오류: {e}")
            continue

    logger.error("Gemini API 호출 실패로 기본 균등 Fallback 메시지 생성")
    return build_fallback_summary(raw_news)

def build_fallback_summary(raw_news):
    """Fallback 발생 시에도 각 카테고리별 균등하게 6개 뉴스 표시"""
    lines = [
        "<b>📌 오늘의 주요 뉴스 브리핑</b>\n",
        "💡 <b>[알림]</b> AI 인사이트 생성이 제한되어 각 카테고리별 주요 뉴스를 2개씩 균등하게 전달합니다.\n"
    ]
    for item in raw_news:
        lines.append(f"• <b>[{item['category']}]</b> {item['title']}\n  <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>")
    return "\n\n".join(lines)

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
        raw_news = fetch_rss_news()
        logger.info(f"수집된 총 뉴스 개수: {len(raw_news)}개 (카테고리당 2개씩 균등 수집)")

        summary_report = generate_summary_with_gemini(raw_news)
        send_telegram_message(summary_report)
        logger.info("=== 텔레그램 일일 뉴스 서비스 성공적 완료 ===")

    except Exception as e:
        logger.critical(f"프로그램 실행 중 예외 발생: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
