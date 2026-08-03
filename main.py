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
# 3. RSS 피드 수집 (카테고리 및 세부 주제별 수집)
# ---------------------------------------------------------
RSS_SOURCES = {
    "AI 최신 모델 및 전망": "https://news.google.com/rss/search?q=AI+%EB%AA%A8%EB%8D%B8+%EC%B5%9C%EC%8B%A0+OR+AI+%EC%A0%84%EB%A1%9D&hl=ko&gl=KR&ceid=KR:ko",
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
            entries = feed.entries[:4]  # 각 소스별 4개씩 수집

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
# 4. Gemini API 분석 및 요약 리포트 생성 (추가 요구사항 1~4번 전면 반영)
# ---------------------------------------------------------
def generate_summary_with_gemini(raw_news):
    if not raw_news:
        return "<b>[알림]</b> 오늘 수집된 신규 뉴스가 없습니다."

    news_text_list = []
    for idx, item in enumerate(raw_news, 1):
        news_text_list.append(f"{idx}. [{item['category']}] {item['title']}\n   링크: {item['link']}")
    
    news_context = "\n".join(news_text_list)

    prompt = f"""
당신은 AI 및 주식 분야 전문 수석 아날리스트입니다. 제공된 뉴스 데이터를 바탕으로 바쁜 현대인을 위해 최적화된 텔레그램 뉴스 브리핑 보고서를 작성하세요.

[뉴스 데이터 목록]
{news_context}

[필수 작성 및 구성 조건]
1. 전체 메시지는 텔레그램 전용 HTML 태그(<b>, <i>, <a>, <code>)만 사용하세요.
2. 카테고리는 아래 2개 구조로만 구성하세요:
   - <b>🤖 1. AI 최신 모델 및 전망</b>
   - <b>📈 2. 주식시장 전망</b>
3. '2. 주식시장 전망' 내부에는 반드시 아래 2개 세부 주제를 포함하세요:
   - <b>[가. 미국시장, 한국시장 주식시장 예측]</b>
   - <b>[나. 한미반도체, 대덕전자 관련 주요 뉴스]</b>
4. [핵심 조건] 각 2개 카테고리 상단에는 바쁜 사용자가 이것만 읽고 가도 주요 동향을 파악할 수 있도록 <b>'3~5줄 내외의 밀도 높은 인사이트'</b>를 작성하세요.
5. [핵심 조건] 리포트 전체에 포함되는 뉴스는 <b>총 5~7개를 넘지 않도록 제한</b>하고, <b>중요성과 파급력이 높은 뉴스를 맨 위에 배치</b>하세요.
6. 각 뉴스 요약 끝에는 반드시 원본 링크(<a href="링크">▶ 원본 뉴스 보기</a>)를 붙여주세요.

[출력 양식 예시]
<b>📌 오늘의 인사이트 (공통)</b>
(전체 시장/기술을 관통하는 총평 2~3줄)

<b>🤖 1. AI 최신 모델 및 전망</b>
💡 <b>AI 핵심 인사이트 (3~5줄)</b>: 
(시간이 없을 때 이것만 보고 이해할 수 있도록 3~5줄 내외로 자세히 작성)

• <b>뉴스 제목</b>: 핵심 내용 요약 <a href="링크">▶ 원본 뉴스 보기</a>

<b>📈 2. 주식시장 전망</b>
💡 <b>주식 핵심 인사이트 (3~5줄)</b>: 
(시간이 없을 때 이것만 보고 이해할 수 있도록 3~5줄 내외로 자세히 작성)

<b>[가. 미국시장, 한국시장 주식시장 예측]</b>
• <b>뉴스 제목</b>: 핵심 내용 요약 <a href="링크">▶ 원본 뉴스 보기</a>

<b>[나. 한미반도체, 대덕전자 관련 주요 뉴스]</b>
• <b>뉴스 제목</b>: 핵심 내용 요약 <a href="링크">▶ 원본 뉴스 보기</a>

HTML 닫는 태그(</b>, </a>) 문법 오류가 생기지 않도록 깔끔하게 검수하여 출력하세요.
"""

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2540}
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
            logger.warning("Gemini 응답 내용 없음.")
            return build_fallback_summary(raw_news)
    except Exception as e:
        logger.error(f"Gemini API 호출 오류: {e}")
        return build_fallback_summary(raw_news)

def build_fallback_summary(raw_news):
    """Gemini API 오류 시 5~7개 제한 기본 메시지 생성"""
    lines = ["<b>📌 오늘의 주요 뉴스 브리핑 (기본 요약)</b>\n"]
    for item in raw_news[:6]:
        lines.append(f"• <b>[{item['category']}]</b> {item['title']}\n  <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>")
    return "\n\n".join(lines)

# ---------------------------------------------------------
# 5. 텔레그램 메시지 전송 (4000자 분할 & HTML 오류 대처)
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
