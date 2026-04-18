# benchmarks/run_benchmark.py
"""Benchmark suite for CCE token savings, retrieval quality, and latency."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_engine.config import load_config
from context_engine.indexer.embedder import Embedder
from context_engine.indexer.pipeline import run_indexing
from context_engine.retrieval.retriever import HybridRetriever
from context_engine.storage.local_backend import LocalBackend


def _count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


async def run_benchmarks(project_dir: Path, queries_path: Path) -> dict:
    config = load_config(project_dir)
    storage_base = Path(config.storage_path) / project_dir.name
    storage_base.mkdir(parents=True, exist_ok=True)

    # Index
    print("Indexing project...")
    result = await run_indexing(config, project_dir, full=True)
    print(f"  Indexed {len(result.indexed_files)} files, {result.total_chunks} chunks")

    backend = LocalBackend(base_path=str(storage_base))
    embedder = Embedder(model_name=config.embedding_model)
    retriever = HybridRetriever(backend=backend, embedder=embedder)

    with open(queries_path) as f:
        queries = json.load(f)

    # Token savings
    print("\n--- Token Savings ---")
    total_full = 0
    for file in project_dir.rglob("*.py"):
        if ".venv" not in str(file) and "__pycache__" not in str(file):
            try:
                total_full += _count_tokens(file.read_text(errors="ignore"))
            except OSError:
                pass

    total_served = 0
    for q in queries:
        chunks = await retriever.retrieve(q["query"], top_k=10)
        served = sum(_count_tokens(c.content) for c in chunks)
        total_served += served

    avg_served = total_served / len(queries) if queries else 0
    savings_pct = (1 - avg_served / total_full) * 100 if total_full > 0 else 0
    print(f"  Full project: {total_full:,} tokens")
    print(f"  Avg per query: {avg_served:,.0f} tokens")
    print(f"  Savings: {savings_pct:.1f}%")

    # Precision / Recall
    print("\n--- Precision@10 / Recall@10 ---")
    precision_sum = 0
    recall_sum = 0
    for q in queries:
        chunks = await retriever.retrieve(q["query"], top_k=10)
        result_files = {c.file_path for c in chunks}
        expected = set(q["expected_files"])
        hits = result_files & expected
        precision = len(hits) / len(result_files) if result_files else 0
        recall = len(hits) / len(expected) if expected else 0
        precision_sum += precision
        recall_sum += recall
        status = "HIT" if hits else "MISS"
        print(f"  [{status}] {q['query'][:50]} — P={precision:.2f} R={recall:.2f}")

    avg_precision = precision_sum / len(queries)
    avg_recall = recall_sum / len(queries)
    print(f"  Avg Precision@10: {avg_precision:.2f}")
    print(f"  Avg Recall@10: {avg_recall:.2f}")

    # Latency
    print("\n--- Latency ---")
    latencies = []
    for _ in range(3):
        await retriever.retrieve("test query", top_k=10)
    for q in queries:
        for _ in range(5):
            t0 = time.perf_counter()
            await retriever.retrieve(q["query"], top_k=10)
            latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    print(f"  p50: {p50:.1f}ms  p95: {p95:.1f}ms  p99: {p99:.1f}ms")

    results = {
        "token_savings_pct": round(savings_pct, 1),
        "avg_precision_at_10": round(avg_precision, 2),
        "avg_recall_at_10": round(avg_recall, 2),
        "latency_p50_ms": round(p50, 1),
        "latency_p95_ms": round(p95, 1),
        "latency_p99_ms": round(p99, 1),
    }
    print(f"\n{json.dumps(results, indent=2)}")
    return results


if __name__ == "__main__":
    project = Path(__file__).parent.parent
    queries = Path(__file__).parent / "sample_queries.json"
    asyncio.run(run_benchmarks(project, queries))
