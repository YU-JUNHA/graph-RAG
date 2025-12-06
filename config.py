import os

from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

# -----------------------------
# .env 로드
# -----------------------------
# .env 파일에서 환경변수 로드
# 예시 .env:
#   OPENAI_API_KEY=sk-xxxxxx
#   NEO4J_PASSWORD=your_password
load_dotenv()

# -----------------------------
# OpenAI / GPT 설정
# -----------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("환경변수 OPENAI_API_KEY 가 설정되어 있지 않습니다. .env 에 설정했는지 확인하세요.")

client = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------------
# Neo4j 설정
# -----------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "비밀번호를_여기에")  # .env 에 NEO4J_PASSWORD 넣는 걸 추천
NEO4J_DB = os.getenv("NEO4J_DB", "shlife-kg")  # DB 이름도 필요하면 .env 로 뺄 수 있음

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# -----------------------------
# 기본 product_id
# -----------------------------
# 비워두면 main.py 에서 실행 시점에 물어본다.
# 나중에:
#   MATCH (p:Product) RETURN p.product_id LIMIT 5;
# 이런 식으로 확인해서 .env 에 SHLIFE_PRODUCT_ID 넣고 여기서 읽어와도 좋다.
DEFAULT_PRODUCT_ID = os.getenv("SHLIFE_PRODUCT_ID", "PRD_SHLIFE_GOODDOCTOR_EASY_001")
