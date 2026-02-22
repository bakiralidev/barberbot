
# core/config.py    
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    SUPERADMIN_IDS: str = "" # Comma-separated string from env
    TZ: str = "Asia/Tashkent"

    @property
    def superadmin_ids(self) -> List[int]:
        if not self.SUPERADMIN_IDS:
            return []
        try:
            return [int(x.strip()) for x in self.SUPERADMIN_IDS.split(",") if x.strip()]
        except ValueError:
            return []

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8"
    )

settings = Settings()
