import json
from config import client
from prompts import ANSWER_SYSTEM_PROMPT


def generate_answer(question: str, cypher: str, rows) -> str:
    """
    쿼리 결과를 받아 한국어 설명 답변 생성.
    rows 는 Neo4j에서 받은 record 리스트(딕셔너리 리스트)라고 가정.
    """
    rows_json = json.dumps(rows, ensure_ascii=False, indent=2)

    user_content = f"""
[사용자 질문]
{question}

[실행한 Cypher]
{cypher}

[쿼리 결과 JSON]
{rows_json}

위 정보를 바탕으로, 사용자의 질문에 대해 자연스러운 한국어 답변을 작성하라.
"""

    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # 필요시 다른 모델명으로 교체
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
    )

    return completion.choices[0].message.content or ""
