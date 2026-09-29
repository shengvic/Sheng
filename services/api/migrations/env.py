from alembic import context
from sqlalchemy import create_engine
from travo_api.config import get_settings

url = context.config.get_main_option("sqlalchemy.url") or get_settings().admin_database_url
engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
