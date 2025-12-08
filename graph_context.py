# graph_context.py

from typing import Dict, Any, List

from graph_client import run_cypher
from metadata_planner import plan_metadata_types


def _get_payable_event_summary(product_id: str) -> str:
    rows = run_cypher(
        """
        MATCH (p:Product {product_id: $product_id})
              -[:HAS_COVERAGE]->(c:Coverage)-[:HAS_EVENT]->(e:PayableEvent)
        RETURN
          e.category AS category,
          collect(DISTINCT c.name)[0..5]   AS coverages,
          collect(DISTINCT e.reason)[0..5] AS reasons
        ORDER BY category
        """,
        {"product_id": product_id},
    )

    if not rows:
        return "PayableEvent 데이터가 없습니다."

    lines: List[str] = []
    for row in rows:
        cat = row.get("category")
        covs = row.get("coverages") or []
        reasons = row.get("reasons") or []
        cov_str = ", ".join(covs)
        reason_str = "; ".join(reasons)

        lines.append(
            f"- category: {cat}\n"
            f"  예시 커버리지: {cov_str}\n"
            f"  예시 지급사유: {reason_str}"
        )
    return "\n".join(lines)


def _get_coverage_list(product_id: str) -> str:
    rows = run_cypher(
        """
        MATCH (p:Product {product_id: $product_id})-[:HAS_COVERAGE]->(c:Coverage)
        RETURN c.type AS type, collect(c.name) AS names
        ORDER BY type
        """,
        {"product_id": product_id},
    )

    if not rows:
        return "Coverage 데이터가 없습니다."

    lines: List[str] = []
    for row in rows:
        t = row.get("type")
        names = row.get("names") or []
        name_str = ", ".join(names)
        lines.append(f"- type: {t}\n  이름들: {name_str}")
    return "\n".join(lines)


def _get_qualification_summary(product_id: str) -> str:
    rows = run_cypher(
        """
        MATCH (p:Product {product_id: $product_id})-[:HAS_QUALIFICATION]->(q:Qualification)
        RETURN
          q.type1 AS type1,
          q.type2 AS type2,
          q.insurance_period AS insurance_period,
          q.payment_period AS payment_period,
          q.age_male_min AS age_male_min,
          q.age_male_max AS age_male_max,
          q.age_female_min AS age_female_min,
          q.age_female_max AS age_female_max,
          q.payment_cycle AS payment_cycle
        ORDER BY type1, type2
        """,
        {"product_id": product_id},
    )

    if not rows:
        return "Qualification 데이터가 없습니다."

    lines: List[str] = []
    for row in rows:
        lines.append(
            f"- {row['type1']} / {row['type2']}: "
            f"보험기간={row['insurance_period']}, 납입기간={row['payment_period']}, "
            f"남 {row['age_male_min']}~{row['age_male_max']}세, "
            f"여 {row['age_female_min']}~{row['age_female_max']}세, "
            f"납입주기={row['payment_cycle']}"
        )
    return "\n".join(lines)


def _get_limitation_summary(product_id: str) -> str:
    rows = run_cypher(
        """
        MATCH (p:Product {product_id: $product_id})
              -[:HAS_COVERAGE]->(c:Coverage)-[:HAS_LIMITATION]->(l:Limitation)
        RETURN
          l.category AS category,
          collect(DISTINCT c.name)[0..5] AS coverages,
          collect(DISTINCT l.text)[0..5] AS texts
        ORDER BY category
        """,
        {"product_id": product_id},
    )

    if not rows:
        return "Limitation 데이터가 없습니다."

    lines: List[str] = []
    for row in rows:
        cat = row.get("category")
        covs = row.get("coverages") or []
        texts = row.get("texts") or []
        cov_str = ", ".join(covs)
        text_str = " / ".join(texts)
        lines.append(
            f"- category: {cat}\n"
            f"  관련 커버리지: {cov_str}\n"
            f"  예시 제한 내용: {text_str}"
        )
    return "\n".join(lines)


def _get_meta_nodes(product_id: str) -> str:
    rows = run_cypher(
        """
        MATCH (p:Product {product_id: $product_id})
        OPTIONAL MATCH (p)-[:HAS_REQUIRED_SUBSCRIPTION]->(rs:RequiredSubscription)
        OPTIONAL MATCH (p)-[:HAS_DIVIDEND_INFO]->(d:DividendInfo)
        OPTIONAL MATCH (p)-[:HAS_PREMIUM_INFO]->(pi:PremiumInfo)
        OPTIONAL MATCH (p)-[:HAS_PREMIUM_DISCOUNT]->(pd:PremiumDiscount)
        OPTIONAL MATCH (p)-[:HAS_PREPAYMENT_INFO]->(pp:PrepaymentInfo)
        RETURN
          rs.text AS required_subscription,
          d.text AS dividend_info,
          pi.text AS premium_info,
          pd.text AS premium_discount,
          pp.text AS prepayment_info
        """,
        {"product_id": product_id},
    )

    if not rows:
        return "메타 노드 데이터가 없습니다."

    row = rows[0]
    lines: List[str] = []

    if row.get("required_subscription"):
        lines.append(f"- RequiredSubscription: {row['required_subscription']}")
    if row.get("dividend_info"):
        lines.append(f"- DividendInfo: {row['dividend_info']}")
    if row.get("premium_info"):
        lines.append(f"- PremiumInfo: {row['premium_info']}")
    if row.get("premium_discount"):
        lines.append(f"- PremiumDiscount: {row['premium_discount']}")
    if row.get("prepayment_info"):
        lines.append(f"- PrepaymentInfo: {row['prepayment_info']}")

    if not lines:
        return "메타 노드 텍스트가 없습니다."

    return "\n".join(lines)


def build_graph_context(question: str, product_id: str) -> str:
    """
    1) LLM이 질문을 보고 어떤 메타데이터 타입이 필요할지 결정(plan_metadata_types)
    2) 각 타입에 맞는 Cypher를 실행해서 요약 텍스트를 만든다.
    3) 다음 단계(싸이퍼 생성)에 넘길 수 있는 하나의 큰 문자열로 합친다.
    """
    metadata_types = plan_metadata_types(question)

    sections: List[str] = []
    for mtype in metadata_types:
        if mtype == "payable_event_summary":
            sections.append("=== PayableEvent 요약 ===")
            sections.append(_get_payable_event_summary(product_id))
        elif mtype == "coverage_list":
            sections.append("=== Coverage 목록 ===")
            sections.append(_get_coverage_list(product_id))
        elif mtype == "qualification_summary":
            sections.append("=== Qualification 요약 ===")
            sections.append(_get_qualification_summary(product_id))
        elif mtype == "limitation_summary":
            sections.append("=== Limitation 요약 ===")
            sections.append(_get_limitation_summary(product_id))
        elif mtype == "meta_nodes":
            sections.append("=== 메타 노드 요약 ===")
            sections.append(_get_meta_nodes(product_id))
        else:
            # 안전장치: 모르는 타입은 무시
            continue

    return "\n".join(sections)
