"""
OmniCore — Data Acquisition Pipeline
Orchestrates the full pipeline:
  Connector → Raw Download → Temp Storage → Validation →
  Cleaning → Normalization → Schema Detection →
  Statistics → Quality Analysis → Versioning →
  Dataset Registry → SQLite Metadata → API Ready

The pipeline never writes directly to the registry — it goes
through the version manager and registry update steps.
"""
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from connectors import ConnectorResult, get_connector
from database import db_session
from models import Dataset, DatasetVersion, SyncLog

logger = logging.getLogger("omnicore.acquisition")


# ── Cleaning ──────────────────────────────────────────────────────────────────

def _clean_records(records: list[dict]) -> list[dict]:
    """
    Clean raw records:
    - Strip leading/trailing whitespace from string fields
    - Remove fully null records
    - Normalise empty strings to None
    """
    cleaned = []
    for rec in records:
        if not any(v is not None for v in rec.values()):
            continue  # Skip fully null records

        clean_rec = {}
        for key, value in rec.items():
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    value = None
            clean_rec[key] = value
        cleaned.append(clean_rec)
    return cleaned


# ── Schema Detection ──────────────────────────────────────────────────────────

def _detect_schema(records: list[dict]) -> dict:
    """
    Detect schema from a sample of records.
    Infers types from observed values and computes null rates per field.
    """
    if not records:
        return {"fields": []}

    sample = records[:min(100, len(records))]
    field_types: dict[str, set] = {}
    field_nulls: dict[str, int] = {}

    for rec in sample:
        for key, value in rec.items():
            field_types.setdefault(key, set())
            field_nulls.setdefault(key, 0)
            if value is None:
                field_nulls[key] += 1
            else:
                t = _infer_type(value)
                field_types[key].add(t)

    fields = []
    for name, types in field_types.items():
        # Pick most specific single type
        if len(types) == 1:
            inferred = list(types)[0]
        elif "string" in types:
            inferred = "string"
        else:
            inferred = list(types)[0]

        null_pct = round(field_nulls.get(name, 0) / len(sample) * 100, 1)
        fields.append({
            "name": name,
            "type": inferred,
            "null_pct": null_pct,
            "description": name.replace("_", " ").title(),
        })

    return {"fields": fields}


def _infer_type(value) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


# ── Statistics Computation ────────────────────────────────────────────────────

def _compute_statistics(records: list[dict]) -> dict:
    """Compute dataset-level statistics."""
    if not records:
        return {"total_records": 0}

    total = len(records)
    all_keys = set()
    for rec in records:
        all_keys.update(rec.keys())

    null_counts: dict[str, int] = {k: 0 for k in all_keys}
    for rec in records:
        for k in all_keys:
            if rec.get(k) is None:
                null_counts[k] += 1

    total_fields = total * len(all_keys)
    total_nulls = sum(null_counts.values())
    completeness_pct = round((1 - total_nulls / max(total_fields, 1)) * 100, 2)

    return {
        "total_records": total,
        "total_fields": len(all_keys),
        "completeness_pct": completeness_pct,
        "null_counts_per_field": {k: v for k, v in null_counts.items() if v > 0},
    }


# ── Version Management ────────────────────────────────────────────────────────

def _increment_version(current_version: str) -> str:
    """Increment the patch component of a semver string."""
    try:
        parts = current_version.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except Exception:
        return "1.0.1"


# ── Acquisition Pipeline ──────────────────────────────────────────────────────

class AcquisitionPipeline:
    """
    Runs the full acquisition pipeline for a single dataset.
    Each stage can succeed or fail independently; failures are logged.
    """

    def __init__(self, dataset_slug: str):
        self.dataset_slug = dataset_slug

    def run(self) -> bool:
        """
        Execute the full pipeline.
        Returns True on success, False on failure.
        """
        with db_session() as db:
            dataset = db.query(Dataset).filter_by(slug=self.dataset_slug, is_active=True).first()
            if not dataset:
                logger.error("Dataset '%s' not found.", self.dataset_slug)
                return False

            # Create sync log entry
            sync_log = SyncLog(
                dataset_id=dataset.id,
                started_at=datetime.utcnow(),
                status="running",
                records_before=dataset.record_count,
            )
            db.add(sync_log)
            db.flush()
            sync_log_id = sync_log.id

        try:
            result = self._execute_pipeline(self.dataset_slug)
            self._apply_result(self.dataset_slug, sync_log_id, result)
            return result.success
        except Exception as exc:
            self._mark_failed(sync_log_id, str(exc))
            logger.exception("Pipeline failed for '%s': %s", self.dataset_slug, exc)
            return False

    def _execute_pipeline(self, slug: str) -> ConnectorResult:
        with db_session() as db:
            dataset = db.query(Dataset).filter_by(slug=slug).first()
            connector_name = dataset.connector
            dataset_slug = dataset.slug

        # Stage 1: Get connector
        connector = get_connector(connector_name, config={"dataset_slug": dataset_slug})
        if not connector:
            logger.warning("No connector registered for '%s'. Using cached data.", connector_name)
            # Return a no-op success for connectors not yet implemented (manual, kaggle, etc.)
            return ConnectorResult(success=True, records=[], record_count=0)

        # Stages 2–8: Delegated to connector.sync()
        result = connector.sync()

        if not result.success:
            return result

        # Stage 9: Additional cleaning pass
        cleaned = _clean_records(result.records)

        # Stage 10: Schema detection (supplement connector's schema)
        if not result.schema_info.get("fields"):
            result.schema_info = _detect_schema(cleaned)

        # Stage 11: Statistics
        if not result.statistics:
            result.statistics = _compute_statistics(cleaned)

        result.records = cleaned
        result.record_count = len(cleaned)
        return result

    def _apply_result(self, slug: str, sync_log_id: str, result: ConnectorResult) -> None:
        with db_session() as db:
            dataset = db.query(Dataset).filter_by(slug=slug).first()
            sync_log = db.query(SyncLog).filter_by(id=sync_log_id).first()

            if result.success and result.record_count > 0:
                new_version = _increment_version(dataset.version)

                # Deactivate previous current version
                db.query(DatasetVersion).filter_by(
                    dataset_id=dataset.id, is_current=True
                ).update({"is_current": False})
                
                # Create DataFrame for Parquet conversion
                import pandas as pd
                df = pd.DataFrame(result.records)
                file_size = int(df.memory_usage(deep=True).sum())
                columns_count = len(df.columns)

                # Update dataset metadata
                dataset.version = new_version
                dataset.record_count = result.record_count
                dataset.columns_count = columns_count
                dataset.file_size_bytes = file_size
                dataset.file_format = "parquet"
                dataset.schema_info = json.dumps(result.schema_info)
                dataset.statistics = json.dumps(result.statistics)
                dataset.quality_score = result.quality_score
                dataset.integrity_hash = result.integrity_hash
                dataset.last_sync = datetime.utcnow()
                dataset.processing_status = "ready"
                
                # Convert to Parquet, Upload to HF & Update Registry
                from hf_storage import hf_storage
                ds_dict = dataset.to_dict(include_provenance=True)
                
                hf_storage.upload_dataset(df, dataset.category, slug, ds_dict, new_version)
                
                registry = hf_storage.get_registry()
                updated = False
                for i, entry in enumerate(registry):
                    if entry.get("slug") == slug:
                        registry[i] = ds_dict
                        updated = True
                        break
                if not updated:
                    registry.append(ds_dict)
                hf_storage.update_registry(registry)

                # Create new version record
                version = DatasetVersion(
                    dataset_id=dataset.id,
                    version=new_version,
                    record_count=result.record_count,
                    quality_score=result.quality_score,
                    integrity_hash=result.integrity_hash,
                    changelog=f"Synced {result.record_count} records to HF Registry.",
                    is_current=True,
                )
                db.add(version)

                if sync_log:
                    sync_log.status = "success"
                    sync_log.records_after = result.record_count
                    sync_log.completed_at = datetime.utcnow()
            elif result.success and result.record_count == 0:
                # Connector returned no records (e.g. manual connector)
                dataset.last_sync = datetime.utcnow()
                dataset.processing_status = "ready"
                if sync_log:
                    sync_log.status = "success"
                    sync_log.records_after = dataset.record_count
                    sync_log.completed_at = datetime.utcnow()
            else:
                dataset.processing_status = "error"
                if sync_log:
                    sync_log.status = "failed"
                    sync_log.error_message = result.error
                    sync_log.completed_at = datetime.utcnow()

    def _mark_failed(self, sync_log_id: str, error: str) -> None:
        try:
            with db_session() as db:
                sl = db.query(SyncLog).filter_by(id=sync_log_id).first()
                if sl:
                    sl.status = "failed"
                    sl.error_message = error[:2000]
                    sl.completed_at = datetime.utcnow()

                dataset = db.query(Dataset).filter_by(slug=self.dataset_slug).first()
                if dataset:
                    dataset.processing_status = "error"
        except Exception:
            pass


def run_acquisition(dataset_slug: str) -> bool:
    """Entry point for triggering acquisition of a single dataset."""
    pipeline = AcquisitionPipeline(dataset_slug)
    return pipeline.run()
