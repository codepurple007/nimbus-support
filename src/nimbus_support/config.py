from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    gemini_api_key: str = ""
    google_api_key: str = ""
    gemini_chat_model: str = "gemini-flash-lite-latest"
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_embedding_model: str = "gemini-embedding-001"
    retrieval_backend: str = "tfidf"
    database_url: str = "postgresql://nimbus:nimbus@localhost:5432/nimbus"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    help_center_dir: Path = PROJECT_ROOT / "data" / "help-center"
    index_dir: Path = PROJECT_ROOT / "data" / ".index"
    tickets_path: Path = PROJECT_ROOT / "data" / "tickets.json"
    sessions_path: Path = PROJECT_ROOT / "data" / "sessions.json"
    orders_path: Path = PROJECT_ROOT / "data" / "orders.json"
    connectors_dir: Path = PROJECT_ROOT / "data" / "connectors"
    context_window_length: int = 5
    admin_token: str = ""
    google_access_token: str = ""
    google_service_account_file: str = ""
    google_drive_folder_id: str = ""
    google_sheets_id: str = ""
    google_sheets_range: str = "Sheet1"
    zendesk_subdomain: str = ""
    zendesk_email: str = ""
    zendesk_api_token: str = ""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def gemini_key(self) -> str:
        return self.gemini_api_key or self.google_api_key


def get_settings() -> Settings:
    return Settings()
