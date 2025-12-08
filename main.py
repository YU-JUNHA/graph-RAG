from config import DEFAULT_PRODUCT_ID
from graph_client import run_cypher, close_driver
from graph_context import build_graph_context
from llm_cypher import generate_cypher
from llm_answer import generate_answer


def ask_product_id(default_product_id: str) -> str:
    """
    DEFAULT_PRODUCT_ID 가 설정되어 있지 않으면
    터미널에서 product_id 를 직접 입력받는다.
    """
    if default_product_id and default_product_id != "YOUR_PRODUCT_ID_HERE":
        return default_product_id

    if default_product_id:
        # 빈 문자열은 아니지만, PLACEHOLDER 로 쓴 경우는 제외
        return default_product_id

    print("config.py 에 DEFAULT_PRODUCT_ID 가 아직 설정되지 않았습니다.")
    print("Neo4j 에서 아래 쿼리로 product_id 를 먼저 확인하세요:")
    print("  MATCH (p:Product) RETURN p.product_id LIMIT 5;")
    print()

    pid = input("사용할 product_id 를 직접 입력하세요 (예: SHLIFE_001): ").strip()
    if not pid:
        raise ValueError("product_id 가 비어 있습니다. config.py 의 DEFAULT_PRODUCT_ID 를 설정하거나, 유효한 값을 입력해야 합니다.")
    return pid


def qa_loop(product_id: str) -> None:
    print("=== 보험 GraphRAG QA ===")
    print(f"사용 중인 product_id: {product_id}")
    print("질문을 입력하세요. 끝내려면 q 또는 quit 입력.\n")

    while True:
        question = input("질문> ").strip()
        if question.lower() in {"q", "quit", "exit"}:
            print("종료합니다.")
            break

        if not question:
            continue

        try:
            # 2단계: 질문을 보고 LLM이 필요한 정보 타입 결정 → 그래프에서 해당 값 조회
            graph_ctx_text = build_graph_context(question, product_id)
            print("\n[그래프 컨텍스트]")
            print(graph_ctx_text)

            # 3단계: 질문 + 그래프 컨텍스트 기반 Cypher 생성
            cypher = generate_cypher(question, product_id, graph_ctx_text)
            print("\n[생성된 Cypher 쿼리]")
            print(cypher)

            # 4단계: 그래프 실행 + 답변
            rows = run_cypher(cypher, {"product_id": product_id})
            print(f"\n[쿼리 결과 행 수] {len(rows)}")

            answer = generate_answer(
                question=question,
                cypher=cypher,
                rows=rows,
                graph_context=graph_ctx_text,  # llm_answer 에서 필요시 활용
            )
            print("\n[답변]")
            print(answer)
            print("\n" + "-" * 60 + "\n")

        except Exception as e:
            print("\n[에러 발생]")
            print(e)
            print("\n" + "-" * 60 + "\n")


if __name__ == "__main__":
    print("main.py 실행 시작")

    try:
        product_id = ask_product_id(DEFAULT_PRODUCT_ID)
    except Exception as e:
        print("[product_id 설정 에러]", e)
    else:
        try:
            qa_loop(product_id)
        finally:
            close_driver()
