import psycopg
from nimbus_support.config import get_settings

def get_db_conn():
    settings = get_settings()
    return psycopg.connect(settings.database_url)
