# Database
import psycopg2
from psycopg2.extras import RealDictCursor
from cryptography.fernet import Fernet
import json

from api.config import get_settings

settings = get_settings()

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            dbname=settings.DATABASE_NAME,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD
        )
        self.crypto_key = Fernet(settings.ENCRYPTION_KEY.encode())

    def encrypt_data(self, data):
        return self.crypto_key.encrypt(json.dumps(data).encode())

    def decrypt_data(self, encrypted_data):
        if encrypted_data is None:
            return None
        return json.loads(self.crypto_key.decrypt(encrypted_data).decode())

    async def store_user_threads_credentials(self, telegram_id, credentials):
        with self.conn.cursor() as cur:
            encrypted_creds = self.encrypt_data(credentials)
            cur.execute("""
                INSERT INTO users (telegram_id, threads_credentials)
                VALUES (%s, %s)
                ON CONFLICT (telegram_id)
                DO UPDATE SET threads_credentials = EXCLUDED.threads_credentials
            """, (telegram_id, encrypted_creds))
            self.conn.commit()

    async def get_user_threads_credentials(self, telegram_id):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT threads_credentials FROM users WHERE telegram_id = %s", (telegram_id,))
            result = cur.fetchone()
            if result and result['threads_credentials']:
                return self.decrypt_data(result['threads_credentials'])
            return None
