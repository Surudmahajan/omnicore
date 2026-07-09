import os
import json
import logging
import httpx
import pandas as pd
from typing import Dict, Any

from connectors import BaseConnector

logger = logging.getLogger(__name__)

class SportsConnector(BaseConnector):
    """Base class for Sports domain connectors"""
    
    def __init__(self, slug: str, name: str, source_url: str, config=None):
        super().__init__(config)
        self.slug = slug
        self.name = name
        self.source_url = source_url
    
    def download(self) -> list[dict]:
        """Download from an API or public CSV source"""
        logger.info(f"Downloading {self.name} from {self.source_url}")
        
        try:
            if self.source_url.endswith('.csv'):
                # Download and parse CSV directly using pandas
                df = pd.read_csv(self.source_url, on_bad_lines='skip', engine='python')
                # Convert to records, replace NaNs with None
                df = df.where(pd.notnull(df), None)
                data = df.to_dict('records')
            else:
                with httpx.Client(follow_redirects=True, timeout=30.0) as client:
                    response = client.get(self.source_url)
                    response.raise_for_status()
                    data = response.json()
        except Exception as e:
            logger.error(f"Failed to download {self.name} from API: {e}.")
            raise

        if not isinstance(data, list):
            if 'data' in data and isinstance(data['data'], list):
                data = data['data']
            else:
                data = [data]
                
        return data
        
    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        """Validate the downloaded JSON"""
        if not records:
            return [], ["No records found"]
        return records, []
        
    def normalize(self, records: list[dict]) -> list[dict]:
        """Normalize JSON to a standardized format"""
        if not records:
            return []
            
        for r in records:
            if 'source_system' not in r:
                r['source_system'] = self.slug
                
        return records


class FifaRankingsConnector(SportsConnector):
    def __init__(self, config=None):
        super().__init__("fifa-world-rankings", "International Football Results", "https://raw.githubusercontent.com/martj42/international_results/master/results.csv", config)

class OlympicHistoryConnector(SportsConnector):
    def __init__(self, config=None):
        super().__init__("olympic-games-history", "Olympic Games History", "https://raw.githubusercontent.com/rfordatascience/tidytuesday/master/data/2021/2021-07-27/olympics.csv", config)

class IplStatsConnector(SportsConnector):
    def __init__(self, config=None):
        super().__init__("ipl-cricket-statistics", "IPL Cricket Statistics", "https://raw.githubusercontent.com/avinashyadav16/ipl-analytics/main/matches_2008-2024.csv", config)

class NbaStatsConnector(SportsConnector):
    def __init__(self, config=None):
        super().__init__("nba-player-stats", "NBA Player Stats", "https://raw.githubusercontent.com/fivethirtyeight/data/master/nba-raptor/historical_RAPTOR_by_player.csv", config)

class AthleticsRecordsConnector(SportsConnector):
    def __init__(self, config=None):
        super().__init__("world-athletics-records", "World Athletics Database", "https://raw.githubusercontent.com/thomascamminady/world-athletics-database/main/data/data.csv", config)

