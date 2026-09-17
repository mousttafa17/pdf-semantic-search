from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import fitz
import requests


BASE_URL = "http://localhost:8000"
TOP_K_VALUES = (1, 3, 5)
REQUEST_TIMEOUT = 60

DATASET_PATH = Path(__file__).with_name("dataset.json")


def load_dataset() -> dict:
    with DATASET_PATH.open("r", encoding="utf-8") as file:
        dataset = json.load(file)

    if not isinstance(dataset, dict):
        raise ValueError("Dataset root must be a JSON object.")

    documents = dataset.get("documents")
    queries = dataset.get("queries")

    if not isinstance(documents, list) or not documents:
        raise ValueError("Dataset must contain a non-empty 'documents' list.")

    if not isinstance(queries, list) or not queries:
        raise ValueError("Dataset must contain a non-empty 'queries' list.")

    document_names = [document.get("name") for document in documents]

    if any(not isinstance(name, str) or not name for name in document_names):
        raise ValueError("Every document must have a non-empty 'name'.")

    if len(document_names) != len(set(document_names)):
        raise ValueError("Document names must be unique.")

    known_documents = set(document_names)

    for query in queries:
        if not isinstance(query, dict):
            raise ValueError("Every query must be a JSON object.")

        query_text = query.get("query")
        relevant_documents = query.get("relevant_documents")

        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError("Every query must contain a non-empty 'query'.")

        if (
            not isinstance(relevant_documents, list)
            or not relevant_documents
            or any(document not in known_documents for document in relevant_documents)
        ):
            raise ValueError(
                "Every query must contain non-empty 'relevant_documents' "
                "referring to documents in the dataset."
            )

    return dataset


def create_pdf(path: Path, content: str) -> None:
    document = fitz.open()

    try:
        page = document.new_page()
        page.insert_textbox(
            fitz.Rect(50, 50, 545, 790),
            content,
            fontsize=11,
        )
        document.save(path)
    finally:
        document.close()


def wait_for_service() -> None:
    response = requests.get(
        f"{BASE_URL}/health",
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    payload = response.json()

    if payload.get("status") != "ok":
        raise RuntimeError(f"Application is not healthy: {payload}")


def ingest_document(path: Path) -> None:
    with path.open("rb") as file:
        response = requests.post(
            f"{BASE_URL}/ingest/",
            files={"input": (path.name, file, "application/pdf")},
            timeout=REQUEST_TIMEOUT,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to ingest {path.name}: "
            f"HTTP {response.status_code}: {response.text}"
        )


def search(query: str) -> list[dict]:
    response = requests.post(
        f"{BASE_URL}/search/",
        json={"query": query},
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Search failed for query {query!r}: "
            f"HTTP {response.status_code}: {response.text}"
        )

    payload = response.json()
    results = payload.get("results")

    if not isinstance(results, list):
        raise RuntimeError("Search response does not contain a valid 'results' list.")

    return results


def calculate_metrics(
    results: list[dict],
    relevant_documents: set[str],
    k: int,
) -> tuple[int, float, float]:
    top_results = results[:k]

    retrieved_documents = {
        result.get("document")
        for result in top_results
        if isinstance(result, dict) and result.get("document")
    }

    relevant_retrieved = retrieved_documents & relevant_documents

    hit = int(bool(relevant_retrieved))
    precision = len(relevant_retrieved) / k
    recall = len(relevant_retrieved) / len(relevant_documents)

    return hit, precision, recall


def print_metrics(metrics: dict[str, list[tuple[int, float, float]]]) -> None:
    print("\nRetrieval Evaluation")
    print("====================")
    print(f"Queries evaluated: {len(metrics)}")

    for query_number, values in metrics.items():
        print(f"\n{query_number}")

        for k, (hit, precision, recall) in zip(TOP_K_VALUES, values):
            print(
                f"  @{k}: "
                f"Hit={hit} "
                f"Precision={precision:.3f} "
                f"Recall={recall:.3f}"
            )

    count = len(metrics)

    aggregate = {}

    for index, k in enumerate(TOP_K_VALUES):
        hits = [values[index][0] for values in metrics.values()]
        precisions = [values[index][1] for values in metrics.values()]
        recalls = [values[index][2] for values in metrics.values()]

        aggregate[k] = (
            sum(hits) / count,
            sum(precisions) / count,
            sum(recalls) / count,
        )

    print("\nAggregate Metrics")
    print("=================")
    print("k    Hit@k    Precision@k    Recall@k")

    for k in TOP_K_VALUES:
        hit, precision, recall = aggregate[k]
        print(
            f"{k:<4} "
            f"{hit:.3f}    "
            f"{precision:.3f}         "
            f"{recall:.3f}"
        )


def main() -> int:
    try:
        dataset = load_dataset()

        wait_for_service()

        documents = dataset["documents"]
        queries = dataset["queries"]

        print("Application is healthy.")
        print(f"Evaluating {len(documents)} documents and {len(queries)} queries.")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            print("\nIngesting evaluation documents...")

            for document in documents:
                pdf_path = temp_path / document["name"]
                create_pdf(pdf_path, document["content"])
                ingest_document(pdf_path)
                print(f"  ingested: {document['name']}")

        metrics: dict[str, list[tuple[int, float, float]]] = {}

        print("\nRunning evaluation queries...")

        for index, query_data in enumerate(queries, start=1):
            query_text = query_data["query"]
            relevant_documents = set(query_data["relevant_documents"])

            results = search(query_text)

            query_metrics = [
                calculate_metrics(results, relevant_documents, k)
                for k in TOP_K_VALUES
            ]

            metrics[f"Query {index}: {query_text}"] = query_metrics

            top_documents = [
                result.get("document")
                for result in results[:5]
                if isinstance(result, dict)
            ]

            print(f"  Query {index}: {query_text}")
            print(f"    Expected: {sorted(relevant_documents)}")
            print(f"    Retrieved: {top_documents}")

        print_metrics(metrics)

        return 0

    except (OSError, ValueError, requests.RequestException, RuntimeError) as exc:
        print(f"\nEvaluation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())