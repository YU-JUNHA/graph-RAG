import re
from config import client
from prompts import CYTHER_SYSTEM_PROMPT


def _strip_markdown_fence(text: str) -> str:
    s = text.strip()
    fence = "`" * 3

    prefix = fence + "cypher"
    if s.lower().startswith(prefix):
        s = s[len(prefix):].strip()

    if s.startswith(fence):
        s = s[len(fence):].strip()

    if s.endswith(fence):
        s = s[:-len(fence)].strip()

    return s


def generate_cypher(question: str, product_id: str, graph_context: str) -> str:
    user_content = (
        "다음은 특정 보험상품에 대해 Neo4j 그래프에서 조회한 메타데이터 요약이다.\n"
        "이 요약에 포함된 category / coverage / qualification / limitation / 메타 노드 정보를 "
        "실제 그래프에 존재하는 값으로 간주하라.\n"
        "이 값들을 활용해서, 사용자 질문에 답하기 위한 '읽기 전용 Cypher 쿼리' 한 개를 작성하라.\n"
        "쿼리 안에서는 product_id 를 $product_id 파라미터로 사용해야 한다.\n"
        "마크다운 코드블록(백틱 세 개)을 사용하지 말고, 순수한 Cypher 텍스트만 출력하라.\n\n"
        "=== 그래프 메타데이터 요약 ===\n"
        f"{graph_context}\n\n"
        "=== 사용자 질문 ===\n"
        f"{question}\n"
    )

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": CYTHER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )

    raw = completion.choices[0].message.content or ""
    cypher = _strip_markdown_fence(raw)

    forbidden = r"\b(CREATE|MERGE|DELETE|SET|DROP|LOAD\s+CSV|CALL\s+dbms\.)\b"
    if re.search(forbidden, cypher, re.IGNORECASE):
        raise ValueError(f"쓰기/관리 연산이 포함된 위험한 쿼리입니다:\n{cypher}")

    return cypher.strip()
