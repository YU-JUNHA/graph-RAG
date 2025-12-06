import json
from neo4j import GraphDatabase

# ==============================
# Neo4j 접속 정보
# ==============================
URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "wnsgk7575"

# JSON 파일 경로
JSON_PATH = "./sample_docs/jsons/상품요약서_신한(간편가입)굿닥터뇌심치료보험(무배당, 갱신형)_251104.json"  # 네 파일 이름/경로에 맞게 수정

# 이 JSON이 대표하는 상품 ID (네가 규칙 정해서 사용)
PRODUCT_ID = "PRD_SHLIFE_GOODDOCTOR_EASY_001"


driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


# ==============================
# 초기화/유틸 함수
# ==============================

def clear_database(tx):
    """
    그래프 전체를 비우고 싶을 때 사용.
    이미 빈 DB라면 아무 문제 없음.
    """
    tx.run("MATCH (n) DETACH DELETE n")


def _ensure_product(tx, product_id, product_name):
    """
    Product 노드가 없으면 생성.
    """
    query = """
    MERGE (p:Product {product_id: $product_id})
    ON CREATE SET p.name = $product_name
    """
    tx.run(query, product_id=product_id, product_name=product_name)


def _load_coverages(tx, product_id, coverages):
    query = """
    MATCH (p:Product {product_id: $product_id})
    UNWIND $coverages AS c
    MERGE (p)-[:HAS_COVERAGE]->(cov:Coverage {
      product_id: $product_id,
      name:       c.name,
      type:       c.type
    })
    ON CREATE SET cov.coverage_id = randomUUID()
    """
    tx.run(query, product_id=product_id, coverages=coverages)


def _load_payable_events(tx, product_id, events):
    query = """
    MATCH (p:Product {product_id: $product_id})
    UNWIND $events AS e
    MATCH (cov:Coverage {
      product_id: $product_id,
      name:       e.coverage_name,
      type:       e.coverage_type
    })
    MERGE (ev:PayableEvent {
      product_id:    $product_id,
      coverage_name: e.coverage_name,
      category:      e.category,
      reason:        e.reason
    })
    ON CREATE SET
      ev.event_id = randomUUID(),
      ev.amount   = e.amount
    ON MATCH SET
      ev.amount   = e.amount
    MERGE (cov)-[:HAS_EVENT]->(ev)
    """
    tx.run(query, product_id=product_id, events=events)


def _load_limitations(tx, product_id, limitations):
    query = """
    MATCH (p:Product {product_id: $product_id})
    UNWIND $limitations AS l
    OPTIONAL MATCH (cov:Coverage {
      product_id: $product_id,
      name:       l.coverage_name,
      type:       l.coverage_type
    })
    MERGE (lim:Limitation {
      product_id:    $product_id,
      coverage_name: l.coverage_name,
      category:      l.category,
      text:          l.text
    })
    ON CREATE SET lim.limit_id = randomUUID()
    WITH lim, cov
    WHERE cov IS NOT NULL
    MERGE (cov)-[:HAS_LIMITATION]->(lim)
    """
    tx.run(query, product_id=product_id, limitations=limitations)


def _load_qualifications(tx, product_id, qualifications):
    query = """
    MATCH (p:Product {product_id: $product_id})
    UNWIND $qualifications AS q
    MERGE (p)-[:HAS_QUALIFICATION]->(qual:Qualification {
      product_id:       $product_id,
      type1:            q.type1,
      type2:            q.type2,
      insurance_period: q.insurance_period,
      payment_period:   q.payment_period
    })
    ON CREATE SET qual.qualification_id = randomUUID()
    SET
      qual.age_male_min   = q.age_male_min,
      qual.age_male_max   = q.age_male_max,
      qual.age_female_min = q.age_female_min,
      qual.age_female_max = q.age_female_max,
      qual.payment_cycle  = q.payment_cycle
    """
    tx.run(query, product_id=product_id, qualifications=qualifications)


def _load_meta_nodes(tx, product_id, data):
    query = """
    MATCH (p:Product {product_id: $product_id})
    // required_subscription
    MERGE (rs:RequiredSubscription {product_id: $product_id})
    ON CREATE SET rs.required_id = randomUUID()
    SET rs.required = $required_subscription.required,
        rs.text     = $required_subscription.text
    MERGE (p)-[:HAS_REQUIRED_SUBSCRIPTION]->(rs)

    // dividend_info
    MERGE (d:DividendInfo {product_id: $product_id})
    ON CREATE SET d.dividend_id = randomUUID()
    SET d.text = $dividend_info.text
    MERGE (p)-[:HAS_DIVIDEND_INFO]->(d)

    // premium_info
    MERGE (pi:PremiumInfo {product_id: $product_id})
    ON CREATE SET pi.premium_info_id = randomUUID()
    SET pi.text = $premium_info.text
    MERGE (p)-[:HAS_PREMIUM_INFO]->(pi)

    // premium_discount
    MERGE (pd:PremiumDiscount {product_id: $product_id})
    ON CREATE SET pd.premium_discount_id = randomUUID()
    SET pd.text = $premium_discount.text
    MERGE (p)-[:HAS_PREMIUM_DISCOUNT]->(pd)

    // prepayment_info
    MERGE (pp:PrepaymentInfo {product_id: $product_id})
    ON CREATE SET pp.prepayment_id = randomUUID()
    SET pp.text = $prepayment_info.text
    MERGE (p)-[:HAS_PREPAYMENT_INFO]->(pp)
    """
    tx.run(
        query,
        product_id=product_id,
        required_subscription=data["required_subscription"],
        dividend_info=data["dividend_info"],
        premium_info=data["premium_info"],
        premium_discount=data["premium_discount"],
        prepayment_info=data["prepayment_info"],
    )


def load_product_structured(product_id: str, data: dict):
    """
    JSON 하나를 받아서 Product + 관련 노드들을 모두 적재
    """
    # 주계약 이름 (MAIN) 하나 뽑아서 상품 이름으로 사용
    main_name = next(
        (c["name"] for c in data["coverages"] if c.get("type") == "MAIN"),
        "UNKNOWN_PRODUCT",
    )

    with driver.session(database="shlife-kg") as session:  # 멀티 DB 쓰면 database="shlife-kg" 같이 지정
        # 필요하면 DB 전체 비우기 (한 번만 쓰고 주석 처리해도 됨)
        session.execute_write(clear_database)

        session.execute_write(_ensure_product, product_id, main_name)
        session.execute_write(_load_coverages, product_id, data["coverages"])
        session.execute_write(_load_payable_events, product_id, data["payable_events"])
        session.execute_write(_load_limitations, product_id, data["limitations"])
        session.execute_write(_load_qualifications, product_id, data["qualifications"])
        session.execute_write(_load_meta_nodes, product_id, data)


# ==============================
# 엔트리포인트
# ==============================

if __name__ == "__main__":
    # 1) JSON 파일 읽기
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2) Neo4j에 적재
    load_product_structured(PRODUCT_ID, data)

    driver.close()
    print("✅ 그래프 적재 완료")
