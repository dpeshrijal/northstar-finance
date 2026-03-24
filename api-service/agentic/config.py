import os
from typing import Optional


def get_env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value or ""


class Settings:
    max_sql_retries: int = int(get_env("MAX_SQL_RETRIES", "3"))
    max_rows: int = int(get_env("MAX_ROWS", "500"))
    max_query_chars: int = int(get_env("MAX_QUERY_CHARS", "4000"))

    # DB
    db_host: str = get_env("DB_HOST", required=True)
    db_name: str = get_env("DB_NAME", required=True)
    db_user: str = get_env("DB_USER", required=True)
    db_pass: str = get_env("DB_PASS", required=True)
    db_sslmode: str = get_env("DB_SSLMODE", "require")
    db_connect_timeout: int = int(get_env("DB_CONNECT_TIMEOUT", "10"))
    db_statement_timeout_ms: int = int(get_env("DB_STATEMENT_TIMEOUT_MS", "15000"))
    db_table_allowlist: str = get_env("DB_TABLE_ALLOWLIST", "")

    # Metadata table config
    dd_table: str = get_env("DATA_DICTIONARY_TABLE", "data_dictionary")
    dd_concept: str = get_env("DATA_DICTIONARY_CONCEPT_COL", "concept_name")
    dd_column: str = get_env("DATA_DICTIONARY_COLUMN_COL", "db_column")
    dd_value: str = get_env("DATA_DICTIONARY_VALUE_COL", "db_value")
    dd_desc: str = get_env("DATA_DICTIONARY_DESC_COL", "description")
    dd_embed: str = get_env("DATA_DICTIONARY_EMBED_COL", "embedding")

    # Policy table config
    policy_table: str = get_env("POLICY_TABLE", "policy_documents")
    policy_content: str = get_env("POLICY_CONTENT_COL", "content")
    policy_embed: str = get_env("POLICY_EMBED_COL", "embedding")

    # Azure OpenAI
    aoai_endpoint: str = get_env("AZURE_OPENAI_ENDPOINT", required=True)
    aoai_key: str = get_env("AZURE_OPENAI_KEY", required=True)
    aoai_api_version: str = get_env("AZURE_OPENAI_API_VERSION", required=True)
    aoai_chat_deployment: str = get_env("AZURE_OPENAI_CHAT_DEPLOYMENT", required=True)
    aoai_embedding_deployment: str = get_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", required=True)


settings = Settings()
