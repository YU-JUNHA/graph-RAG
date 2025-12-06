from typing import Any, Dict, List

from config import driver, NEO4J_DB


def run_cypher(cypher: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """
    주어진 Cypher 쿼리를 실행하고, 결과를 딕셔너리 리스트로 반환한다.
    각 원소는 한 행(row)에 해당한다.
    """
    if params is None:
        params = {}

    # 필요하면 디버깅용 출력
    # print("[DEBUG] run_cypher] cypher:", cypher)
    # print("[DEBUG] run_cypher] params:", params)

    with driver.session(database=NEO4J_DB) as session:
        result = session.run(cypher, **params)
        rows: List[Dict[str, Any]] = [record.data() for record in result]

    return rows


def close_driver() -> None:
    """
    애플리케이션 종료 시 Neo4j 드라이버를 닫고 싶을 때 사용.
    """
    driver.close()
