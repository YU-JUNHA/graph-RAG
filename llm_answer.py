# llm_answer.py

from typing import List, Dict, Any

from config import client


def _rows_to_text(rows: List[Dict[str, Any]]) -> str:
    """
    Cypher 결과 rows(list of dict)를 LLM이 읽기 쉬운 텍스트로 변환.
    """
    if not rows:
        return "그래프 쿼리 결과: 0행 (데이터 없음)."

    lines: List[str] = []
    for i, row in enumerate(rows, start=1):
        parts = []
        for k, v in row.items():
            parts.append(f"{k}={v}")
        line = f"{i}. " + ", ".join(parts)
        lines.append(line)

    return "\n".join(lines)


def generate_answer(
    question: str,
    cypher: str,
    rows: List[Dict[str, Any]],
    graph_context: str | None = None,
) -> str:
    """
    - question: 사용자 질문 원문
    - cypher: 실제로 실행한 Cypher 쿼리
    - rows: 쿼리 결과 (record.data()로 받은 dict 리스트)
    - graph_context: (선택) graph_context.build_graph_context 에서 만든 요약 텍스트
    """

    rows_text = _rows_to_text(rows)

    # 시스템 프롬프트: "그래프 쿼리 결과만 믿고 한국어로 답해라"
    system_prompt = (
        "너는 보험 상품에 대한 질문에 답하는 어시스턴트이다. "
        "Neo4j 그래프에서 가져온 데이터(rows_text)와, "
        "그래프 메타데이터 요약(graph_context)이 주어진다. "
        "반드시 이 데이터에 근거해서만 답변해야 한다. "
        "데이터에 없는 내용은 추측하지 말고, "
        "그래프에 해당 정보가 없다고 솔직하게 말해라. "
        "답변은 한국어로 자연스럽게 작성해라."
    )

    # 유저 컨텍스트 구성
    user_parts: List[str] = []

    user_parts.append("=== 사용자 질문 ===")
    user_parts.append(question)

    user_parts.append("\n=== 실행된 Cypher 쿼리 ===")
    user_parts.append(cypher)

    if graph_context:
        user_parts.append("\n=== 그래프 메타데이터 요약 ===")
        user_parts.append(graph_context)

    user_parts.append("\n=== 그래프 쿼리 결과(요약) ===")
    user_parts.append(rows_text)

    user_parts.append(
        "\n위 정보를 바탕으로, 사용자의 질문에 친절하게 답변해라. "
        "숫자나 조건 등은 가능한 한 그대로 인용하되, "
        "표현은 사용자에게 이해하기 쉽게 풀어서 설명해라."
        "사용자의 질문에 최대한 자세하고 정확하게 답변해라."
    )

    user_content = "\n".join(user_parts)

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
    )

    return completion.choices[0].message.content or ""
