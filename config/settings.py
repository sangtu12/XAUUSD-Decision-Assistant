from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional
from decimal import Decimal
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = Field(default="postgresql+psycopg2://postgres:postgres@localhost:5432/xauusd_assistant")
    
    # MetaTrader 5
    MT5_PATH: str = Field(default=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    MT5_LOGIN: Optional[int] = Field(default=None)
    MT5_PASSWORD: Optional[str] = Field(default=None)
    MT5_SERVER: Optional[str] = Field(default=None)
    MT5_SYMBOL: str = Field(default="XAUUSD")
    MT5_TIMEFRAMES: str = Field(default="M5,M15,H1,H4")

    @field_validator("MT5_LOGIN", mode="before")
    def empty_str_to_none_login(cls, v):
        if v == "" or v is None:
            return None
        return int(v)
    
    @property
    def timeframes_list(self) -> List[str]:
        return [tf.strip() for tf in self.MT5_TIMEFRAMES.split(",") if tf.strip()]
    
    # Risk & Gate Parameters
    MAX_SPREAD_CENTS: Decimal = Field(default=Decimal("50.0"))
    MIN_RISK_REWARD: Decimal = Field(default=Decimal("1.5"))
    MAX_STOP_DISTANCE_POINTS: Decimal = Field(default=Decimal("500.0"))
    ALLOW_EXTREME_VOLATILITY: bool = Field(default=False)
    DEFAULT_MAX_LIFETIME_BARS_M5: int = Field(default=36)
    
    # Telegram Notifications
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_CHAT_ID: str = Field(default="")
    
    # Server API
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
