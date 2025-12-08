import streamlit as st
from neo4j import GraphDatabase
from llm_cypher import generate_cypher
from llm_answer import generate_answer

# ==========================
# 설정
# ==========================
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "wnsgk7575"
DEFAULT_PRODUCT_ID = "PRD_SHLIFE_GOODDOCTOR_EASY_001"  # 너가 실제로 사용 중인 product_id 로 바꿔줘

# ==========================
# Neo4j 드라이버 초기화
# ==========================
@st.cache_resource
def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


driver = get_driver()

# ==========================
# 그래프 컨텍스트 조회 함수
# ==========================
def get_graph_context(product_id: str):
    """
    LLM에 던져줄 요약용 컨텍스트 + 디버깅용 raw 데이터를 Neo4j에서 가져온다.
    - Coverage 목록
    - PayableEvent 카테고리/예시 지급사유
    """

    coverages = []
    events_summary = []

    with driver.session() as session:
        # 1) Coverage 목록
        cov_query = """
        MATCH (p:Product {product_id: $product_id})-[:HAS_COVERAGE]->(c:Coverage)
        RETURN c.type AS type, c.name AS name
        ORDER BY type, name
        """
        cov_rows = session.run(cov_query, product_id=product_id)
        for row in cov_rows:
            coverages.append({"type": row["type"], "name": row["name"]})

        # 2) PayableEvent 카테고리 + 예시 지급사유
        evt_query = """
        MATCH (p:Product {product_id: $product_id})
              -[:HAS_COVERAGE]->(c:Coverage)
              -[:HAS_EVENT]->(e:PayableEvent)
        RETURN e.category AS category,
               c.name     AS coverage_name,
               e.reason   AS reason
        ORDER BY category, coverage_name
        """
        evt_rows = session.run(evt_query, product_id=product_id)
        for row in evt_rows:
            events_summary.append(
                {
                    "category": row["category"],
                    "coverage_name": row["coverage_name"],
                    "reason": row["reason"],
                }
            )

    # LLM 프롬프트에 넣기 좋은 텍스트 형태로도 만들어준다.
    # (너가 안 쓰고 싶으면 무시해도 됨)
    cov_lines_main = []
    cov_lines_rider = []
    for c in coverages:
        if c["type"] == "MAIN":
            cov_lines_main.append(c["name"])
        else:
            cov_lines_rider.append(c["name"])

    context_text_lines = []
    context_text_lines.append("=== Coverage 목록 ===")
    if cov_lines_main:
        context_text_lines.append("- type: MAIN")
        context_text_lines.append(f"  이름들: {', '.join(cov_lines_main)}")
    if cov_lines_rider:
        context_text_lines.append("- type: RIDER")
        context_text_lines.append(f"  이름들: {', '.join(cov_lines_rider)}")

    context_text_lines.append("=== PayableEvent 요약 ===")
    # category 별로 하나씩만 예시 붙여보자
    seen_cat = set()
    for e in events_summary:
        cat = e["category"]
        if cat in seen_cat:
            continue
        seen_cat.add(cat)
        context_text_lines.append(f"- category: {cat}")
        context_text_lines.append(f"  예시 커버리지: {e['coverage_name']}")
        context_text_lines.append(f"  예시 지급사유: {e['reason']}")

    context_text = "\n".join(context_text_lines)

    return {
        "coverages": coverages,
        "events_summary": events_summary,
        "context_text": context_text,
    }


# ==========================
# Cypher 실행 함수
# ==========================
def run_cypher(cypher: str, product_id: str):
    """
    Cypher 쿼리를 실행해서 dict 리스트로 반환.
    """
    with driver.session() as session:
        result = session.run(cypher, product_id=product_id)
        rows = []
        for record in result:
            rows.append(record.data())
    return rows


# ==========================
# 간단 Graphviz 시각화용 함수 (선택)
# ==========================
def build_simple_graphviz_from_result(rows):
    """
    Cypher 결과를 바탕으로 아주 단순한 Graphviz DOT 문자열을 만든다.
    - coverage_name, category, amount 정도를 보고
      Product -> Coverage -> "category" 노드 구조로 그린다.
    - 결과 row의 키 구조에 따라 유연하게 작동하도록 매우 느슨하게 작성.
    """
    if not rows:
        return None

    nodes = set()
    edges = set()

    nodes.add("Product")

    for r in rows:
        cov = r.get("coverage_name") or r.get("coverage") or ""
        cat = r.get("category") or ""
        # event_id, amount 등도 있으면 label에 쓰고 싶으면 확장하면 됨

        if cov:
            nodes.add(cov)
            edges.add(("Product", cov, "HAS_COVERAGE"))
        if cov and cat:
            nodes.add(cat)
            edges.add((cov, cat, "category"))

    if not nodes:
        return None

    def esc(s: str) -> str:
        return s.replace('"', '\\"')

    lines = ["digraph G {", "  rankdir=LR;"]

    for n in nodes:
        lines.append(f'  "{esc(n)}";')
    for s, t, label in edges:
        lines.append(f'  "{esc(s)}" -> "{esc(t)}" [label="{esc(label)}"];')

    lines.append("}")
    return "\n".join(lines)


# ==========================
# Streamlit UI
# ==========================
st.set_page_config(page_title="보험 GraphRAG 데모", layout="wide")

st.title("📊 보험 GraphRAG 챗봇 데모")

# 사이드바: product_id 선택
st.sidebar.header("설정")
product_id = st.sidebar.text_input("product_id", value=DEFAULT_PRODUCT_ID)
st.sidebar.write("Neo4j URI:", NEO4J_URI)

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state["messages"] = []  # 각 원소: {"role": "user/assistant", "content": str, "debug": {...}}

# 기존 대화 렌더링
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        debug = msg.get("debug")
        if msg["role"] == "assistant" and debug:
            with st.expander("🔎 디버그 정보 보기", expanded=False):
                st.subheader("그래프 컨텍스트 (텍스트 요약)")
                st.text(debug.get("graph_context_text", ""))

                st.subheader("그래프 컨텍스트 (raw 데이터)")
                st.write("Coverages")
                st.json(debug.get("graph_coverages", []))
                st.write("PayableEvent 요약")
                st.json(debug.get("graph_events_summary", []))

                st.subheader("생성된 Cypher 쿼리")
                st.code(debug.get("cypher", ""), language="cypher")

                st.subheader("Cypher 조회 결과")
                st.json(debug.get("cypher_result", []))

                dot = debug.get("graphviz_dot")
                if dot:
                    st.subheader("간단 그래프 시각화")
                    st.graphviz_chart(dot)


# 사용자 입력
if question := st.chat_input("질문을 입력하세요. 예: 임플란트 보장 되니?"):
    # 1) 사용자 메시지 추가
    st.session_state["messages"].append(
        {"role": "user", "content": question, "debug": None}
    )

    # 2) 그래프 컨텍스트 조회
    graph_ctx = get_graph_context(product_id)
    graph_context_text = graph_ctx["context_text"]

    # 3) Cypher 생성 (graph_context 같이 전달)
    cypher = generate_cypher(
        question=question,
        product_id=product_id,
        graph_context=graph_context_text,
    )

    # 4) Cypher 실행
    cypher_rows = run_cypher(cypher, product_id)

    # 5) LLM 답변 생성
    answer = generate_answer(question, cypher, cypher_rows)

    # 6) 그래프 시각화 DOT 만들기 (실패해도 그냥 None)
    graphviz_dot = None
    try:
        graphviz_dot = build_simple_graphviz_from_result(cypher_rows)
    except Exception:
        graphviz_dot = None

    # 7) 어시스턴트 메시지 + 디버그 정보 세션에 저장
    debug_payload = {
        "graph_context_text": graph_context_text,
        "graph_coverages": graph_ctx["coverages"],
        "graph_events_summary": graph_ctx["events_summary"],
        "cypher": cypher,
        "cypher_result": cypher_rows,
        "graphviz_dot": graphviz_dot,
    }

    st.session_state["messages"].append(
        {"role": "assistant", "content": answer, "debug": debug_payload}
    )
