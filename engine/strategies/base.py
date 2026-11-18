from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from decimal import Decimal
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, name: str, version: str = "0.3"):
        self.name = name
        self.version = version

    @abstractmethod
    def evaluate(
        self,
        timeframe_dfs: Dict[str, pd.DataFrame],
        regime: Dict[str, Any],
        symbol_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Evaluate strategy across multi-timeframe data.
        Returns a list of setup candidates.
        """
        pass
