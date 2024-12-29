# Database
from api.utils.logger import logger
import psycopg2
from psycopg2.extras import RealDictCursor
from cryptography.fernet import Fernet
import json

from api.config import get_settings

settings = get_settings()

class Database:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.init_db()
        return cls._instance
    
    def init_db(self):
        if self._initialized:
            return
        
        logger.info(f"Connecting to database.")
        self.conn = psycopg2.connect(
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            dbname=settings.DATABASE_NAME
        )
        logger.info(f"Connected to database: {settings.DATABASE_USER}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}")
        self.crypto_key = Fernet(settings.ENCRYPTION_KEY.encode())
        self._initialized = True

    def encrypt_data(self, data):
        return self.crypto_key.encrypt(json.dumps(data).encode())

    def decrypt_data(self, encrypted_data):
        if encrypted_data is None:
            return None
        if isinstance(encrypted_data, memoryview):
            encrypted_data = encrypted_data.tobytes()
        return json.loads(self.crypto_key.decrypt(encrypted_data).decode())

    async def store_user_threads_credentials(self, telegram_id, credentials):
        try:
            with self.conn.cursor() as cur:
                encrypted_creds = self.encrypt_data(credentials)
                cur.execute("""
                    INSERT INTO users (telegram_id, threads_credentials)
                    VALUES (%s, %s)
                    ON CONFLICT (telegram_id)
                    DO UPDATE SET threads_credentials = EXCLUDED.threads_credentials
                """, (telegram_id, encrypted_creds))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error storing user threads credentials: {str(e)}")

    async def get_user_threads_credentials(self, telegram_id):
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT threads_credentials FROM users WHERE telegram_id = %s", (telegram_id,))
                result = cur.fetchone()
                if result and result['threads_credentials']:
                    return self.decrypt_data(result['threads_credentials'])
            return None
        except Exception as e:
            logger.error(f"Error getting user threads credentials: {str(e)}")
            return None
        
db = Database()