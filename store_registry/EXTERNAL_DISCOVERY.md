# External discovery snapshot contract (offline only)

The independent intake does **not** call CU or emart24 APIs. Obtain legally
permitted provider responses separately; do not copy secrets, cookies, customer
data, inventory quantities or Telegram credentials into snapshot files.

Save a UTF-8 JSON file **outside** the repository with this exact structure:

```json
{
  "schema_version": 1,
  "snapshots": [{
    "chain": "cu",
    "region": "namwon",
    "source": "cu_parsed_inventory",
    "captured_at": "2026-10-15T00:00:00Z",
    "payload": {"stores": [
      {"code": "00123", "name": "예시점", "address": "전북특별자치도 남원시 예시로 1"}
    ]}
  }]
}
```

For emart24 use source `emart24_store_directory` or `emart24_seed`;
rows may contain `storeCode`, `storeName`, `address`, or be keyed by code
under `stores`. The example is synthetic, **not a verified store**.

Run with a read-only main JSON snapshot (the four files documented in
`verify_main_snapshot.py`):

```sh
python3 -m store_registry.intake --root /tmp/store-registry-main --input /tmp/discovery.json
```

The output contains the SHA-256 of the input, classification counts, and
rejected snapshots. All new stores remain unverified and production admission
is always zero. An operator must independently verify source, identity,
region, and stock lookup compatibility before a separate staged review.
Do not enable unattended fetching, merge this pipeline into production, or
place uploaded snapshots in a production workflow.
