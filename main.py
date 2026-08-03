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
# 3. 3개 카테고리별 RSS 피드 수집 (각 3~4개씩 균등 수집)
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
            entries = feed.entries[:3]  # 카테고리당 3개씩 정확히 수집

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
# 4. Gemini API 호출 및 뉴스레터 리포트 생성
# ---------------------------------------------------------
def generate_summary_with_gemini(news_by_category):
    # 뉴스 데이터를 텍스트로 변환
    formatted_context = ""
    for cat_name, items in news_by_category.items():
        formatted_context += f"\n[{cat_name}]\n"
        for idx, item in enumerate(items, 1):
            formatted_context += f" {idx}. {item['title']} (링크: {item['link']})\n"

    prompt = f"""
당신은 대한민국 최고 수준의 AI/증시 아날리스트입니다.
아래 수집된 뉴스를 바탕으로 요구된 양식을 정확히 지켜 텔레그램 뉴스레터를 작성하세요.

[수집 데이터]
{formatted_context}

[필수 요구 형식 및 작성 규칙]
1. 텔레그램 HTML 태그(<b>, <i>, <a>, <code>)만 사용할 것.
2. 아래 3개 카테고리 구조를 절대 변경하지 말 것.
3. 각 카테고리의 '가. 인사이트'는 바쁜 현대인이 이것만 봐도 완벽 이해할 수 있도록 3~5줄 내외로 깊이 있게 분석 작성할 것 (절대 생략 금지!).
4. 각 뉴스 끝에는 <a href="링크">▶ 원본 뉴스 보기</a> 포함할 것.

[출력 양식]
<b>[오늘의 주요 뉴스]</b>

<b>1. AI 관련 뉴스</b>
가. 💡 <b>인사이트</b>:
(AI 기술 동향 및 모델 발전에 대한 3~5줄 내외의 상세 분석)
나. 📰 <b>주요 뉴스</b>
• 뉴스 제목 요약 <a href="링크">▶ 원본 뉴스 보기</a>
• 뉴스 제목 요약 <a href="링크">▶ 원본 뉴스 보기</a>
• 뉴스 제목 요약 <a href="링크">▶ 원본 뉴스 보기</a>

<b>2. 주식시장 전망</b>
가. 💡 <b>인사이트</b>:
(미국 및 한국 주식시장 전망에 대한 3~5줄 내외의 상세 분석)
나. 📰 <b>주요 뉴스</b>
• 뉴스 제목 요약 <a href="링크">▶ 원본 뉴스 보기</a>
• 뉴스 제목 요약 <a href="링크">▶ 원본 뉴스 보기</a>
• 뉴스 제목 요약 <a href="링크">▶ 원본 뉴스 보기</a>

<b>3. 개별종목 분석(대덕전자, 한미반도체)</b>
가. 💡 <b>인사이트</b>:
(한미반도체, 대덕전자 및 반도체 부품업종에 대한 3~5줄 내외의 상세 분석)
나. 📰 <b>주요 뉴스</b>
• 뉴스 제목 요약 <a href="링크">▶ 원본 뉴스 보기</a>
• 뉴스 제목 요약 <a href="링크">▶ 원본 뉴스 보기</a>
• 뉴스 제목 요약 <a href="링크">▶ 원본 뉴스 보기</a>
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
            logger.info(f"Gemini API 호출 시도중... ({gemini_url.split('/')[-1].split(':')[0]})")
            res = requests.post(gemini_url, json=payload, timeout=30)
            
            if not res.ok:
                logger.warning(f"Gemini API 응답 오류 [{res.status_code}]: {res.text}")
                continue

            data = res.json()
            candidates = data.get("candidates", [])
            if candidates and "parts" in candidates[0]["content"]:
                result_text = candidates[0]["content"]["parts"][0]["text"]
                logger.info("Gemini API 분석 및 인사이트 생성 성공!")
                return result_text
        except Exception as e:
            logger.warning(f"Gemini API 호출 예외: {e}")
            continue

    logger.error("Gemini API 호출 실패. 인사이트 포함 Fallback 메시지를 생성합니다.")
    return build_fallback_summary(news_by_category)

def build_fallback_summary(news_by_category):
    """Gemini API가 실패해도 인사이트 섹션과 뉴스가 100% 무조건 포함되는 Fallback 메시지"""
    output = ["<b>[오늘의 주요 뉴스]</b>\n"]
    
    cat_names = [
        ("1. AI 관련 뉴스", "AI 관련 뉴스", "💡 <b>인사이트</b>: AI 글로벌 시장은 차세대 멀티모달 모델 도입과 생성형 AI의 산업 현장 적용이 가속화되고 있습니다. 기술 내재화와 서비스 상용화 속도가 기업 경쟁력을 좌우할 핵심 요소로 떠오르고 있습니다."),
        ("2. 주식시장 전망", "주식시장 전망", "💡 <b>인사이트</b>: 미국 및 한국 증시는 거시경제 지표 및 금리 변동성에 인과관계를 형성하며 변동성을 나타내고 있습니다. 반도체 중심의 실적 개선 기대감과 기술주 위주의 수급이 지수 방어의 핵심 축을 이루고 있습니다."),
        ("3. 개별종목 분석(대덕전자, 한미반도체)", "개별종목 분석(대덕전자, 한미반도체)", "💡 <b>인사이트</b>: HBM 핵심 장비 공급을 주도하는 한미반도체와 고성능 반도체 기판(FC-BGA)을 생산하는 대덕전자는 차세대 반도체 패키징 시장 확대에 따른 수혜가 지속될 전망입니다.")
    ]

    for title_name, key_name, insight_text in cat_names:
        output.append(f"<b>{title_name}</b>")
        output.append(f"가. {insight_text}")
        output.append("나. 📰 <b>주요 뉴스</b>")
        
        items = news_by_category.get(key_name, [])
        if items:
            for item in items:
                output.append(f"• {item['title']} <a href=\"{item['link']}\">▶ 원본 뉴스 보기</a>")
        else:
            output.append("• 관련 신규 뉴스가 없습니다.")
        output.append("")

    return "\n".join(output)

# ---------------------------------------------------------
# 5. 텔레그램 메시지 전송 (4000자 분할 및 HTML 실패 처리)
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
