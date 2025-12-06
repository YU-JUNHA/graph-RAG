import re

from config import client
from prompts import CYTHER_SYSTEM_PROMPT


def _strip_markdown_fence(text: str) -> str:
    """
    모델이 ```cypher ... ``` 또는 ``` ... ``` 같은 마크다운 코드블록으로
    감싸서 보내더라도, 그 부분을 잘라내고 안의 내용만 반환한다.
    """
    s = text.strip()
    fence = "`" * 3  # 백틱 세 개

    # 1) 맨 앞에 ```cypher 또는 ```CYTHER 가 붙은 경우
    prefix = fence + "cypher"
    if s.lower().startswith(prefix):
        s = s[len(prefix):].strip()

    # 2) 맨 앞에 ``` 만 있는 경우
    if s.startswith(fence):
        s = s[len(fence):].strip()

    # 3) 맨 끝에 ``` 가 있는 경우
    if s.endswith(fence):
        s = s[:-len(fence)].strip()

    return s


def generate_cypher(question: str, product_id: str) -> str:
    """
    사용자 질문을 받아 LLM으로부터 Cypher 쿼리를 생성.
    - 출력 형식은 '순수 Cypher 문자열' 하나가 되도록 정리한다.
    - 혹시 코드블록(백틱 세 개)로 감싸져 있으면 제거한다.
    - 쓰기/관리 연산이 들어가면 예외를 던진다.
    """
    user_content = f"""
product_id: {product_id}

사용자 질문:
\"\"\"{question}\"\"\"

위 질문에 답을 하기 위한 Neo4j Cypher "읽기 전용" 쿼리 한 개를 작성하라.
위 시스템 프롬프트에서 설명한 스키마만 사용해야 한다.
쿼리 안에서는 product_id 를 $product_id 파라미터로 사용하라.

출력 형식:
- 마크다운 코드블록(백틱 세 개)을 사용하지 말고,
  순수 Cypher 쿼리 텍스트만 출력하라.
"""

    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # 필요시 다른 모델명으로 교체
        messages=[
            {"role": "system", "content": CYTHER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )

    raw = completion.choices[0].message.content or ""
    cypher = _strip_markdown_fence(raw)

    # 안전장치: 쓰기/관리 연산 금지
    forbidden = r"\b(CREATE|MERGE|DELETE|SET|DROP|LOAD\s+CSV|CALL\s+dbms\.)\b"
    if re.search(forbidden, cypher, re.IGNORECASE):
        raise ValueError(f"쓰기/관리 연산이 포함된 위험한 쿼리입니다:\n{cypher}")

    return cypher.strip()
