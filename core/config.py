
# core/config.py    
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    SUPERADMIN_IDS: str = "" # Comma-separated string from env
    TZ: str = "Asia/Tashkent"

    # Webhook settings
    WEBHOOK_HOST: str = "https://yourdomain.alwaysdata.net"
    WEBHOOK_PATH: str = "/webhook"
    WEBHOOK_SECRET: str = "your_secret_token" # Telegram-ga yuboriladigan maxfiy token

    @property
    def webhook_url(self) -> str:
        return f"{self.WEBHOOK_HOST}{self.WEBHOOK_PATH}"

    @property
    def timezone_name(self) -> str:
        # Ba'zi serverlarda TZ ': /etc/localtime' kabi noto'g'ri bo'lishi mumkin
        if not self.TZ or self.TZ.startswith(":") or "/" in self.TZ and not any(c.islower() for c in self.TZ.split("/")[0]):
            # Agar TZ fayl yo'liga o'xshasa yoki bo'sh bo'lsa
            return "Asia/Tashkent"
        return self.TZ

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
