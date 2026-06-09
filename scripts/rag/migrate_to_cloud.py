"""Migrate the local Qdrant collection to Qdrant Cloud via scroll + upsert.

Why not snapshot? Qdrant snapshots on Docker Desktop on Windows hit a known
fragility: post-optimization WAL state can be inconsistent with what the
snapshot manifest expects ("WAL: closed-NNNN not found"), and even after a
container restart that cleans the in-memory state, the file-level WAL still
contains a corrupt `first-index` JSON that Cloud refuses on restore. Scroll +
upsert uses only stable read/write APIs and avoids the entire snapshot path.

Setup (.env or shell):
    CLOUD_QDRANT_URL=https://xxxxxxxx.region.aws.cloud.qdrant.io:6333
    CLOUD_QDRANT_API_KEY=<your cloud api key>

Run:
    python scripts/rag/migrate_to_cloud.py
    # optional: --collection <name>   (default: hindu_scriptures)
    # optional: --batch <n>           (default: 500)
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

load_dotenv()

LOCAL_URL = os.environ.get("LOCAL_QDRANT_URL", "http://localhost:6333")


def fail(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 2


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--collection", default="hindu_scriptures")
    p.add_argument("--batch", type=int, default=500,
                   help="Points per scroll/upsert batch (default: 500)")
    args = p.parse_args()

    cloud_url = (os.environ.get("CLOUD_QDRANT_URL") or "").rstrip("/")
    cloud_key = os.environ.get("CLOUD_QDRANT_API_KEY")
    if not cloud_url or not cloud_key:
        return fail("set CLOUD_QDRANT_URL and CLOUD_QDRANT_API_KEY env vars.")

    coll = args.collection
    local = QdrantClient(url=LOCAL_URL, timeout=600)
    cloud = QdrantClient(url=cloud_url, api_key=cloud_key, timeout=600)

    if not local.collection_exists(coll):
        return fail(f"local Qdrant ({LOCAL_URL}) has no collection '{coll}'.")

    info = local.get_collection(coll)
    n_local = info.points_count
    vectors_config = info.config.params.vectors
    sparse_vectors_config = info.config.params.sparse_vectors
    dense_dim = vectors_config["dense"].size if "dense" in (vectors_config or {}) else "?"
    print(f"Local  '{coll}': {n_local:,} points, dense dim={dense_dim}, status={info.status}")

    # (Re)create Cloud collection with matching config.
    # Skip get_collection diagnostics — prior failed snapshot uploads can leave
    # the collection in a broken state where `exists()` is True but
    # `get_collection()` 500s with "Failed to restore local replica".
    if cloud.collection_exists(coll):
        print(f"Cloud  '{coll}': EXISTS — deleting (may be in broken state from prior attempts)...")
        try:
            cloud.delete_collection(coll)
            print("      deleted")
        except Exception as e:
            return fail(
                f"could not delete existing Cloud collection ({e!r}). "
                "Delete it manually via cloud.qdrant.io → cluster → Collections → "
                f"{coll} → Delete, then re-run."
            )

    print(f"\n[1/3] Creating Cloud collection '{coll}'...")
    cloud.create_collection(
        collection_name=coll,
        vectors_config=vectors_config,
        sparse_vectors_config=sparse_vectors_config,
    )

    # Recreate payload indexes (match local's schema)
    payload_schema = info.payload_schema or {}
    if payload_schema:
        print(f"      Recreating {len(payload_schema)} payload indexes...")
        for field_name, schema in payload_schema.items():
            try:
                cloud.create_payload_index(
                    collection_name=coll,
                    field_name=field_name,
                    field_schema=schema.data_type,
                )
            except Exception as e:
                print(f"      WARN: payload index {field_name} failed: {e!r}")

    # Scroll + upsert
    print(f"\n[2/3] Copying {n_local:,} points in batches of {args.batch}...")
    t0 = time.time()
    offset = None
    moved = 0
    while True:
        records, next_offset = local.scroll(
            collection_name=coll,
            limit=args.batch,
            offset=offset,
            with_vectors=True,
            with_payload=True,
        )
        if not records:
            break

        # Records → PointStructs (upsert needs PointStruct, scroll returns Record)
        points = [
            PointStruct(id=r.id, vector=r.vector, payload=r.payload)
            for r in records
        ]
        cloud.upsert(collection_name=coll, points=points, wait=True)

        moved += len(points)
        elapsed = time.time() - t0
        rate = moved / elapsed if elapsed > 0 else 0
        eta_min = (n_local - moved) / rate / 60 if rate > 0 else 0
        print(f"  {moved:>7,}/{n_local:,}  ({100 * moved / n_local:5.1f}%)  "
              f"rate={rate:.0f} pts/s  eta={eta_min:.1f} min")

        offset = next_offset
        if offset is None:
            break

    print(f"      copy done in {time.time() - t0:.1f}s")

    # Verify
    print(f"\n[3/3] Verifying Cloud collection...")
    time.sleep(3)  # let Cloud's optimizers settle before exact count
    n_cloud = cloud.count(collection_name=coll, exact=True).count
    cloud_info = cloud.get_collection(coll)
    cloud_dim = cloud_info.config.params.vectors["dense"].size
    print(f"      Cloud '{coll}': {n_cloud:,} points (exact), dim={cloud_dim}, "
          f"status={cloud_info.status}")
    if n_cloud != n_local:
        return fail(f"point count mismatch (local {n_local:,} vs cloud {n_cloud:,})")

    print(f"\n✓ Migration complete: {n_local:,} points live on Cloud.")
    print(f"  Railway 'main' service will see them on the next search — no redeploy needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
