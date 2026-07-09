import logging
import json
from datetime import datetime
from typing import Optional

from connectors import BaseConnector

logger = logging.getLogger("omnicore.connectors.electronics")

class ArduinoLibrariesConnector(BaseConnector):
    name = "arduino-libs"
    BASE_URL = "https://downloads.arduino.cc/libraries/library_index.json"

    def download(self) -> list[dict]:
        logger.info(f"Downloading Arduino Libraries from {self.BASE_URL}")
        try:
            resp = self._get(self.BASE_URL)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("libraries", [])
        except Exception as e:
            logger.warning(f"Arduino API failed: {e}")
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if "name" in r and "version" in r]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        normalised = []
        for rec in records:
            normalised.append({
                "library_name": rec.get("name"),
                "version": rec.get("version"),
                "author": rec.get("author"),
                "maintainer": rec.get("maintainer"),
                "sentence": rec.get("sentence"),
                "paragraph": rec.get("paragraph"),
                "website": rec.get("website"),
                "category": rec.get("category"),
                "architectures": ", ".join(rec.get("architectures", [])),
                "types": ", ".join(rec.get("types", [])),
            })
        return normalised


class IoTDeviceConnector(BaseConnector):
    name = "iot-devices"
    BASE_URL = "https://api.github.com/search/repositories?q=topic:iot"

    def download(self) -> list[dict]:
        logger.info(f"Downloading IoT Devices from {self.BASE_URL}")
        try:
            resp = self._get(self.BASE_URL)
            if resp.status_code == 200:
                return resp.json().get("items", [])
        except Exception as e:
            logger.warning(f"IoT API failed: {e}")
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if "id" in r and "name" in r]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        normalised = []
        for rec in records:
            normalised.append({
                "device_id": str(rec.get("id")),
                "device_name": rec.get("name")[:30] if rec.get("name") else "Unknown",
                "description": (rec.get("description") or "")[:100],
                "protocol": rec.get("language") or "Unknown",
                "status": "Active" if not rec.get("archived") else "Archived"
            })
        return normalised


class RaspberryPiProjectsConnector(BaseConnector):
    name = "raspi-projects"
    BASE_URL = "https://jsonplaceholder.typicode.com/albums" # Mock

    def download(self) -> list[dict]:
        try:
            resp = self._get(self.BASE_URL)
            if resp.status_code == 200: return resp.json()
        except Exception as e:
            logger.warning(f"Raspi API failed: {e}")
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if "title" in r]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        return [{"project_id": r.get("id"), "project_name": r.get("title"), "platform": "Raspberry Pi"} for r in records]


class ElectronicComponentsConnector(BaseConnector):
    name = "electronic-components"
    BASE_URL = "https://api.github.com/search/repositories?q=topic:electronic-components"

    def download(self) -> list[dict]:
        try:
            resp = self._get(self.BASE_URL)
            if resp.status_code == 200: return resp.json().get("items", [])
        except Exception as e:
            logger.warning(f"Components API failed: {e}")
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if "id" in r and "name" in r]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        return [{"part_number": str(r.get("id")), "manufacturer": (r.get("owner", {}).get("login") or "Unknown")[:30], "description": (r.get("description") or "Component")[:50], "category": "Passive"} for r in records]


class SemiconductorMarketConnector(BaseConnector):
    name = "semiconductor-market"
    BASE_URL = "https://api.github.com/search/repositories?q=topic:semiconductor"

    def download(self) -> list[dict]:
        try:
            resp = self._get(self.BASE_URL)
            if resp.status_code == 200: return resp.json().get("items", [])
        except Exception as e:
            logger.warning(f"Semiconductor API failed: {e}")
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if "id" in r and "name" in r]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        return [{"market_segment": r.get("name")[:30], "completed": not bool(r.get("archived")), "year": 2026} for r in records]
