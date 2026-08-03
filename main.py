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
# 2. 환경변수 검증 (TELEGRAM_BOT_TOKEN / TELEGRAM_TOKEN 둘 다 호환)
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
# 3. RSS 피드 수집 (requests 활용)
# ---------------------------------------------------------
RSS_SOURCES = {
    "AI 최신 모델 및 동향": "https://news.google.com/rss/search?q=AI+%EB%AA%A8%EB%8D%B8+%EC%B5%9C%EC%8B%A0&hl=ko&gl=KR&ceid=KR:ko",
    "데이터 사이언스": "https://news.google.com/rss/search?q=%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%82%AC%EC%9D%B4%EC%96%B8%EC%8A%A4&hl=ko&gl=KR&ceid=KR:ko",
    "주식시장 전망": "https://news.google.com/rss/search?q=%EC%A3%BC%EC%8B%9D%EC%8B%9C%EC%9E%A5+%EC%A0%84%EB%A1%9D&hl=ko&gl=KR&ceid=KR:ko",
    "한미반도체/대덕전자 및 이슈 종목": "https://news.google.com/rss/search?q=%ED%95%9C%EB%AF%B8%EB%B0%98%EB%8F%84%EC%B2%B4+OR+%EB%8C%80%EB%8D%95%EC%A0%84%EC%9E%90&hl=ko&gl=KR&ceid=KR:ko"
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
            entries = feed.entries[:5]  # 카테고리당 상위 5개 추출

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
# 4. Gemini API 기반 뉴스 요약 및 인사이트 생성 (requests 활용)
# ---------------------------------------------------------
def generate_summary_with_gemini(raw_news):
    if not raw_news:
        return "<b>[알림]</b> 오늘 수집된 신규 뉴스가 없습니다."

    news_text_list = []
    for idx, item in enumerate(raw_news, 1):
        news_text_list.append(f"{idx}. [{item['category']}] {item['title']}\n   링크: {item['link']}")
    
    news_context = "\n".join(news_text_list)

    prompt = f"""
당신은 AI 및 주식 전문 수석 아날리스트입니다. 아래 제공된 최신 뉴스 소식들을 바탕으로 매일 아침 텔레그램으로 브리핑할 일일 보고서를 작성해주세요.

[뉴스 데이터 목록]
{news_context}

[작성 가이드라인]
1. 텔레그램 메시지용 HTML 포맷을 반드시 준수하세요. (허용 태그: <b>, <i>, <a>, <code>)
2. 구분이 명확하도록 볼드와 가독성 높은 이모지를 적절히 사용해 강조하세요.
3. 원본 뉴스를 볼 수 있는 <a> 태그(예: <a href="링크">▶ 원본 뉴스 보기</a>)를 각 뉴스 요약 끝에 반드시 포함하세요.
4. 내용 구성 순서:
   - <b>📌 오늘의 인사이트 (공통)</b>: 전체적인 기술/시장 트렌드를 관통하는 핵심 요약 (3~4줄)
   - <b>🤖 [AI 분야]</b>
     - AI 카테고리 인사이트 (2줄)
     - 최신 AI 동향 & 데이터사이언스 주요 뉴스 3개 요약 (핵심 내용 + ▶ 원본 뉴스 보기)
   - <b>📈 [주식 분야]</b>
     - 주식 카테고리 인사이트 (2줄)
     - 증시 전망 & 주요 개별종목(한미반도체/대덕전자 등) 주요 뉴스 3개 요약 (핵심 내용 + ▶ 원본 뉴스 보기)

HTML 태그 문법 오류가 없도록 닫는 태그를 정확히 작성해주세요.
"""

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2540}
    }

    try:
        logger.info("Gemini API 호출 중...")
        res = requests.post(gemini_url, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        
        candidates = data.get("candidates", [])
        if candidates:
            return candidates[0]["content"]["parts"][0]["text"]
        else:
            logger.warning("Gemini 응답에 내용이 없습니다.")
            return build_fallback_summary(raw_news)
    except Exception as e:
        logger.error(f"Gemini API 호출 오류: {e}")
        return build_fallback_summary(raw_news)

def build_fallback_summary(raw_news):
    """Gemini API 실패 시 원본 뉴스 리스트 기반 기본 메시지 생성"""
    lines = ["<b>📌 오늘의 주요 뉴스 브리핑 (기본 요약)</b>\n"]
    for item in raw_news[:8]:
        lines.append(f"• <b>[{item['category']}]</b> {item['title']}\n  <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>")
    return "\n\n".join(lines)

# ---------------------------------------------------------
# 5. 텔레그램 메시지 전송 (requests 활용 & 에러/길이 분할 처리)
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
        logger.info(f"수집된 총 뉴스 개수: {len(raw_news)}개")

        summary_report = generate_summary_with_gemini(raw_news)
        send_telegram_message(summary_report)
        logger.info("=== 텔레그램 일일 뉴스 서비스 성공적 완료 ===")

    except Exception as e:
        logger.critical(f"프로그램 실행 중 예외 발생: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
