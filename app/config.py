import os


QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://localhost:6333",
)

EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "BAAI/bge-small-en-v1.5",
)

EMBEDDING_DIMENSION = int(
    os.getenv("EMBEDDING_DIMENSION", "384")
)