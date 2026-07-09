"""
OmniCore — HuggingFace Storage Adapter
Handles pushing/pulling datasets, metadata, and the global registry.json to the central omnicore-registry repository.
"""
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import HfHubHTTPError, EntryNotFoundError

from config import settings

logger = logging.getLogger("omnicore.hf_storage")

class HFStorage:
    def __init__(self):
        self.api = HfApi(token=settings.HF_TOKEN)
        self.repo_id = f"{settings.HF_ORG_NAME}/omnicore-registry"
        self.repo_type = "dataset"
        
        # Ensure local cache directories exist
        self.cache_dir = Path(settings.DATASET_STORAGE_PATH)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def initialize_repository(self):
        """Ensure the omnicore-registry repository exists on HF."""
        if not settings.HF_TOKEN:
            logger.warning("HF_TOKEN not set. Skipping repository initialization.")
            return

        try:
            self.api.repo_info(repo_id=self.repo_id, repo_type=self.repo_type)
            logger.info(f"Repository {self.repo_id} already exists.")
        except HfHubHTTPError as e:
            if "404" in str(e):
                logger.info(f"Repository {self.repo_id} not found. Creating...")
                self.api.create_repo(
                    repo_id=self.repo_id,
                    repo_type=self.repo_type,
                    private=False,
                    exist_ok=True
                )
                # Initialize empty registry.json
                self.update_registry([])
            else:
                logger.error(f"Error checking repo {self.repo_id}: {e}")

    def _get_dataset_folder(self, category: str, slug: str, version: str = "latest") -> str:
        """Get the folder path in the HF repo for a specific dataset version."""
        safe_cat = category.lower().replace(" ", "_")
        return f"{safe_cat}/{slug}/{version}"

    def get_registry(self) -> List[Dict[str, Any]]:
        """Download and parse the global registry.json from HF."""
        if not settings.HF_TOKEN:
            return []
            
        try:
            path = hf_hub_download(
                repo_id=self.repo_id,
                filename="metadata/registry.json",
                repo_type=self.repo_type,
                token=settings.HF_TOKEN
            )
            with open(path, "r") as f:
                return json.load(f)
        except EntryNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Failed to fetch registry.json: {e}")
            return []

    def update_registry(self, datasets_metadata: List[Dict[str, Any]]):
        """Upload the updated registry.json to HF."""
        if not settings.HF_TOKEN:
            return
            
        try:
            # We use a temporary file to upload
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
                json.dump(datasets_metadata, f, indent=2)
                temp_path = f.name
                
            self.api.upload_file(
                path_or_fileobj=temp_path,
                path_in_repo="metadata/registry.json",
                repo_id=self.repo_id,
                repo_type=self.repo_type,
                commit_message="Update global registry.json"
            )
            os.remove(temp_path)
            logger.info("Successfully updated metadata/registry.json")
        except Exception as e:
            logger.error(f"Failed to update registry.json: {e}")

    def upload_dataset(self, df: pd.DataFrame, category: str, slug: str, metadata: Dict[str, Any], version: str = "latest"):
        """Convert DataFrame to Parquet and CSV, then upload to HF Dataset repository along with metadata.json."""
        if not settings.HF_TOKEN:
            logger.warning("No HF_TOKEN. Skipping upload.")
            return

        folder = self._get_dataset_folder(category, slug, version)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save Parquet
            parquet_path = os.path.join(tmpdir, "data.parquet")
            df.to_parquet(parquet_path, index=False)
            
            # Save CSV
            csv_path = os.path.join(tmpdir, "data.csv")
            df.to_csv(csv_path, index=False)
            
            # Save metadata.json
            meta_path = os.path.join(tmpdir, "metadata.json")
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)
                
            # Upload files
            self.api.upload_file(path_or_fileobj=parquet_path, path_in_repo=f"{folder}/data.parquet", repo_id=self.repo_id, repo_type=self.repo_type)
            self.api.upload_file(path_or_fileobj=csv_path, path_in_repo=f"{folder}/data.csv", repo_id=self.repo_id, repo_type=self.repo_type)
            # Also put metadata in the parent dataset folder
            parent_folder = f"{category.lower().replace(' ', '_')}/{slug}"
            self.api.upload_file(path_or_fileobj=meta_path, path_in_repo=f"{parent_folder}/metadata.json", repo_id=self.repo_id, repo_type=self.repo_type)

            logger.info(f"Uploaded {slug} ({version}) to {self.repo_id}/{folder}")

    def download_dataset(self, category: str, slug: str, version: str = "latest") -> Optional[str]:
        """
        Download the Parquet file to the local cache and return the local path.
        If it's already in the cache, return the cache path immediately (assuming version matches).
        """
        local_cache_path = self.cache_dir / f"{slug}_{version}.parquet"
        
        # If cache exists, serve it
        if local_cache_path.exists():
            return str(local_cache_path)
            
        # Otherwise, download from HF
        if not settings.HF_TOKEN:
            logger.error("No HF_TOKEN. Cannot download dataset.")
            return None

        folder = self._get_dataset_folder(category, slug, version)
        try:
            path = hf_hub_download(
                repo_id=self.repo_id,
                filename=f"{folder}/data.parquet",
                repo_type=self.repo_type,
                token=settings.HF_TOKEN
            )
            # Copy to our cache directory for structured access
            import shutil
            shutil.copy2(path, local_cache_path)
            return str(local_cache_path)
        except EntryNotFoundError:
            logger.error(f"Dataset {slug} version {version} not found in HF.")
            return None
        except Exception as e:
            logger.error(f"Failed to download dataset {slug}: {e}")
            return None

hf_storage = HFStorage()
