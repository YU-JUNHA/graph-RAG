# metadata_planner.py

import json
from typing import List

from config import client
from prompts import METADATA_PLAN_SYSTEM_PROMPT


ALLOWED_METADATA_TYPES = {
    "payable_event_summary",
    "coverage_list",
    "qualification_summary",
    "limitation_summary",
    "meta_nodes",
}


def plan_metadata_types(question: str) -> List[str]:
    """
    LLM에게 질문을 넘겨서
    - 어떤 메타데이터 타입을 조회할지 결정하게 한다.
    - 결과는 ["payable_event_summary", "coverage_list", ...] 형태의 리스트.
    """
    user_content = (
        "다음은 사용자의 질문이다.\n\n"
        f"{question}\n\n"
        "이 질문에 답하기 위해 필요한 그래프 메타데이터 타입들을 선택하라.\n"
        "반드시 JSON 형식으로 출력해야 한다."
    )

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": METADATA_PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )

    raw = completion.choices[0].message.content or ""

    # JSON 파싱 시도
    try:
        data = json.loads(raw)
        types = data.get("metadata_types", [])
        # 허용된 타입만 필터링
    #    types = [t for t in types if t in ALLOWED_METADATA_TYPES]
    #    if not types:
    #        # 아무것도 안 골랐으면 기본값
    #        return ["coverage_list", "payable_event_summary"]
        return types
    except Exception:
        # JSON 파싱 실패 시에도 안전한 기본값
    #    return ["coverage_list", "payable_event_summary"]
        return