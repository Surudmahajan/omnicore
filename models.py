"""
OmniCore — Database Models
All SQLAlchemy ORM models.
Schema is SQLite-first but PostgreSQL-compatible.
"""
import json
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.orm import relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    saved_datasets = relationship("SavedDataset", back_populates="user", cascade="all, delete-orphan")
    usage_stats = relationship("UsageStat", back_populates="user", cascade="all, delete-orphan")
    search_history = relationship("SearchHistory", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


# ── Refresh Tokens ────────────────────────────────────────────────────────────

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


# ── API Keys ──────────────────────────────────────────────────────────────────

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False)
    key_prefix = Column(String(16), nullable=False)   # First 12 chars — shown in UI
    name = Column(String(100), nullable=False, default="Default Key")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)

    user = relationship("User", back_populates="api_keys")
    usage_stats = relationship("UsageStat", back_populates="api_key", cascade="all, delete-orphan")


# ── Datasets ──────────────────────────────────────────────────────────────────

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, default=_uuid)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    # Classification
    domain = Column(String(100), nullable=False, index=True)     # IT, Electronics, Healthcare, Geography, Sports
    category = Column(String(100), nullable=False)
    tags = Column(Text, nullable=False, default="[]")             # JSON array of strings
    solution_packs = Column(Text, nullable=False, default="[]")   # JSON array of pack names

    # Provenance (immutable after creation)
    source = Column(String(200), nullable=False)
    source_url = Column(String(500), nullable=False)
    connector = Column(String(100), nullable=False)
    license = Column(String(100), nullable=False)
    downloaded_date = Column(DateTime, nullable=True)

    # Versioning & Sync
    version = Column(String(20), nullable=False, default="1.0.0")
    last_sync = Column(DateTime, nullable=True)
    next_sync = Column(DateTime, nullable=True)
    sync_frequency = Column(String(20), nullable=False, default="weekly")  # daily/weekly/monthly/manual

    # Data characteristics
    record_count = Column(Integer, nullable=True)
    columns_count = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    file_format = Column(String(20), nullable=False, default="parquet")
    schema_info = Column(Text, nullable=True)     # JSON: {fields: [{name, type, description}]}
    statistics = Column(Text, nullable=True)      # JSON: {min, max, mean, null_pct, etc.}

    # Quality & Integrity
    quality_score = Column(Float, nullable=False, default=0.0)    # 0.0–10.0
    integrity_hash = Column(String(64), nullable=True)             # SHA-256 of dataset file
    processing_status = Column(String(50), nullable=False, default="ready")

    # Discovery
    popularity = Column(Integer, default=0, nullable=False)
    endpoint = Column(String(200), nullable=False)

    # Meta
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    versions = relationship("DatasetVersion", back_populates="dataset", cascade="all, delete-orphan")
    sync_logs = relationship("SyncLog", back_populates="dataset", cascade="all, delete-orphan")
    saved_by = relationship("SavedDataset", back_populates="dataset", cascade="all, delete-orphan")

    # ── Convenience helpers ──────────────────────────────────────────────────
    @property
    def tags_list(self) -> list:
        return json.loads(self.tags) if self.tags else []

    @property
    def solution_packs_list(self) -> list:
        return json.loads(self.solution_packs) if self.solution_packs else []

    @property
    def schema_dict(self) -> dict:
        return json.loads(self.schema_info) if self.schema_info else {}

    @property
    def statistics_dict(self) -> dict:
        return json.loads(self.statistics) if self.statistics else {}

    def to_dict(self, include_provenance: bool = True) -> dict:
        d = {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "category": self.category,
            "tags": self.tags_list,
            "solution_packs": self.solution_packs_list,
            "endpoint": self.endpoint,
            "version": self.version,
            "record_count": self.record_count,
            "columns_count": self.columns_count,
            "file_size_bytes": self.file_size_bytes,
            "file_format": self.file_format,
            "quality_score": self.quality_score,
            "processing_status": self.processing_status,
            "popularity": self.popularity,
            "sync_frequency": self.sync_frequency,
            "last_sync": self.last_sync.isoformat() + "Z" if self.last_sync else None,
            "next_sync": self.next_sync.isoformat() + "Z" if self.next_sync else None,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }
        if include_provenance:
            d["provenance"] = {
                "source": self.source,
                "source_url": self.source_url,
                "connector": self.connector,
                "license": self.license,
                "downloaded_date": self.downloaded_date.isoformat() + "Z" if self.downloaded_date else None,
                "integrity_hash": self.integrity_hash,
            }
            d["schema"] = self.schema_dict
            d["statistics"] = self.statistics_dict
        return d


# ── Dataset Versions ──────────────────────────────────────────────────────────

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    version = Column(String(20), nullable=False)
    file_path = Column(String(500), nullable=True)
    record_count = Column(Integer, nullable=True)
    quality_score = Column(Float, nullable=True)
    integrity_hash = Column(String(64), nullable=True)
    changelog = Column(Text, nullable=True)
    is_current = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dataset = relationship("Dataset", back_populates="versions")


# ── Sync Logs ─────────────────────────────────────────────────────────────────

class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running / success / failed
    records_before = Column(Integer, nullable=True)
    records_after = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    dataset = relationship("Dataset", back_populates="sync_logs")


# ── Saved Datasets ────────────────────────────────────────────────────────────

class SavedDataset(Base):
    __tablename__ = "saved_datasets"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    saved_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="saved_datasets")
    dataset = relationship("Dataset", back_populates="saved_by")


# ── Usage Stats ───────────────────────────────────────────────────────────────

class UsageStat(Base):
    __tablename__ = "usage_stats"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=True)
    endpoint = Column(String(200), nullable=False)
    dataset_id = Column(String(36), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="usage_stats")
    api_key = relationship("APIKey", back_populates="usage_stats")


# ── Search History ────────────────────────────────────────────────────────────

class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    query = Column(String(500), nullable=False)
    results_count = Column(Integer, nullable=False, default=0)
    searched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="search_history")
