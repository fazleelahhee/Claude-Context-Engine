# CCE Benchmarks

Benchmarks run on the CCE repository itself (~200 files, ~700 chunks).

## Results

| Metric | Value |
|--------|-------|
| Token savings vs full-file reads | TBD% |
| Precision@10 | TBD |
| Recall@10 | TBD |
| Query latency p50 | TBD ms |
| Query latency p95 | TBD ms |

## Methodology

Run: `python benchmarks/run_benchmark.py`

- **Token savings**: Compare full project token count vs average tokens served per query
- **Precision/Recall**: Curated queries with known-relevant files in `benchmarks/sample_queries.json`
- **Latency**: 5 iterations per query, report percentiles (after 3 warm-up runs)
