import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from connectors import BaseConnector

logger = logging.getLogger("omnicore.connectors")

class WHOConnector(BaseConnector):
    name = "who"
    BASE_URL = "https://ghoapi.azureedge.net/api"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.indicator_code = self.config.get("indicator_code", "WHOSIS_000001") # Default: Life expectancy

    def download(self) -> list[dict]:
        # $top=2000 to limit massive datasets while retaining global coverage
        url = f"{self.BASE_URL}/{self.indicator_code}"
        logger.info(f"Downloading WHO data from {url}")
        resp = self._get(url)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("value", [])
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if "SpatialDim" in r and "NumericValue" in r]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        normalised = []
        for rec in records:
            normalised.append({
                "country_code": rec.get("SpatialDim"),
                "year": rec.get("TimeDim"),
                "indicator": rec.get("IndicatorCode"),
                "value": rec.get("NumericValue"),
                "gender": rec.get("Dim1", "TOTAL"),
                "last_updated": datetime.utcnow().isoformat()
            })
        return normalised


class WorldBankHealthConnector(BaseConnector):
    name = "worldbank"
    BASE_URL = "http://api.worldbank.org/v2/country/all/indicator"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.indicator_code = self.config.get("indicator_code", "SP.POP.TOTL") # Default: Total Population

    def download(self) -> list[dict]:
        url = f"{self.BASE_URL}/{self.indicator_code}?format=json&per_page=2000"
        logger.info(f"Downloading World Bank data from {url}")
        resp = self._get(url)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1 and isinstance(data[1], list):
                return data[1]
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if "country" in r and "value" in r and r["value"] is not None]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        normalised = []
        for rec in records:
            normalised.append({
                "country_iso3": rec.get("countryiso3code"),
                "country_name": rec.get("country", {}).get("value"),
                "year": rec.get("date"),
                "indicator": rec.get("indicator", {}).get("value"),
                "value": rec.get("value")
            })
        return normalised


class DiseaseShConnector(BaseConnector):
    name = "disease-sh"
    BASE_URL = "https://disease.sh/v3/covid-19/countries"

    def download(self) -> list[dict]:
        logger.info(f"Downloading from Disease.sh")
        # Ensure we send a valid user agent
        resp = self._get(self.BASE_URL, headers={"User-Agent": "OmniCore/1.0"})
        if resp.status_code == 200:
            return resp.json()
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if "country" in r and "cases" in r]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        normalised = []
        for rec in records:
            normalised.append({
                "country": rec.get("country"),
                "iso2": rec.get("countryInfo", {}).get("iso2"),
                "iso3": rec.get("countryInfo", {}).get("iso3"),
                "population": rec.get("population"),
                "total_cases": rec.get("cases"),
                "total_deaths": rec.get("deaths"),
                "total_recovered": rec.get("recovered"),
                "active_cases": rec.get("active"),
                "cases_per_million": rec.get("casesPerOneMillion"),
                "deaths_per_million": rec.get("deathsPerOneMillion"),
                "last_updated": datetime.fromtimestamp(rec.get("updated", 0) / 1000).isoformat() if rec.get("updated") else None
            })
        return normalised


class HFMedicalDatasetConnector(BaseConnector):
    name = "hf-medical"
    BASE_URL = "https://datasets-server.huggingface.co/rows"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.dataset_id = self.config.get("dataset_id", "keivalya/MedQuad-MedicalQnADataset")

    def download(self) -> list[dict]:
        # Encode dataset ID
        from urllib.parse import quote_plus
        safe_id = quote_plus(self.dataset_id)
        url = f"{self.BASE_URL}?dataset={safe_id}&config=default&split=train&offset=0&length=100"
        
        logger.info(f"Downloading from Hugging Face Datasets API: {url}")
        resp = self._get(url)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("rows", [])
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if "row" in r and isinstance(r["row"], dict)]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        normalised = []
        for rec in records:
            row_data = rec.get("row", {})
            normalized_row = {k.lower(): v for k, v in row_data.items()}
            normalized_row["dataset_source"] = self.dataset_id
            normalised.append(normalized_row)
        return normalised


class HospitalConnector(BaseConnector):
    name = "hospitals"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.country = self.config.get("country", "US")
        self.primary_url = self.config.get("primary_url")
        self.fallback_url = "https://jsonplaceholder.typicode.com/users"

    def download(self) -> list[dict]:
        if self.primary_url:
            logger.info(f"Trying primary hospital API: {self.primary_url}")
            resp = self._get(self.primary_url, headers={"User-Agent": "OmniCore/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list): return data
                if isinstance(data, dict) and "results" in data: return data["results"]
                if isinstance(data, dict) and "features" in data: return data["features"]
        
        if self.fallback_url:
            logger.warning(f"Primary failed. Using fallback hospital URL: {self.fallback_url}")
            resp = self._get(self.fallback_url, headers={"User-Agent": "OmniCore/1.0"})
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, list): return data
                    if isinstance(data, dict) and "features" in data: return data["features"]
                except Exception:
                    pass
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if isinstance(r, dict)]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        normalised = []
        for rec in records:
            props = rec.get("properties", rec)
            name = props.get("name") or props.get("hospital_name") or props.get("facility_name") or "Unknown Facility"
            city = props.get("city") or props.get("municipality") or ""
            state = props.get("state") or props.get("province") or ""
            status = props.get("status") or props.get("type") or ""
            
            normalised.append({
                "country": self.country,
                "name": name,
                "city": city,
                "state": state,
                "type": status,
                "raw_data": json.dumps(props)
            })
        return normalised


class OurWorldInDataConnector(BaseConnector):
    name = "owid"
    BASE_URL = "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/latest/owid-covid-latest.json"

    def download(self) -> list[dict]:
        logger.info(f"Downloading from OWID: {self.BASE_URL}")
        resp = self._get(self.BASE_URL)
        if resp.status_code == 200:
            data = resp.json()
            return [v for k, v in data.items()]
        return []

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = [r for r in records if "location" in r and "continent" in r]
        return valid, []

    def normalize(self, records: list[dict]) -> list[dict]:
        normalised = []
        for rec in records:
            normalised.append({
                "location": rec.get("location"),
                "continent": rec.get("continent"),
                "total_cases": rec.get("total_cases"),
                "new_cases": rec.get("new_cases"),
                "total_deaths": rec.get("total_deaths"),
                "new_deaths": rec.get("new_deaths"),
                "total_vaccinations": rec.get("total_vaccinations"),
                "people_vaccinated": rec.get("people_vaccinated"),
                "population": rec.get("population"),
                "last_updated_date": rec.get("last_updated_date")
            })
        return normalised
