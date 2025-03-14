# Database
from pythreads.credentials import Credentials
from api.utils.logger import logger
import psycopg2
from psycopg2.extras import RealDictCursor
from cryptography.fernet import Fernet
import json

from api.utils.config import get_settings

settings = get_settings()

class Database:
    _instance = None
    _initialized = False
    conn = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.init_db()
        return cls._instance
    
    def init_db(self):
        if self._initialized:
            return
        
        try: 
            logger.info(f"Initializing database.")
            self.connect()
            logger.info(f"✓ Connected to database: {settings.DATABASE_USER}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}")
            logger.info(f"Creating tables ...")
            # self.create_tables()
            logger.info(f"✓ Tables created.")
            logger.info(f"Setting up encryption key ...")
            self.crypto_key = Fernet(settings.ENCRYPTION_KEY.encode())
            logger.info(f"✓ Encryption key set.")
            self._initialized = True
            logger.info(f"✅ Database initialized.")   
        except Exception as e:
            logger.error(f"❌ Error initializing database: {str(e)}")
        
    def connect(self):
        self.conn = psycopg2.connect(
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            dbname=settings.DATABASE_NAME
        )

    def create_tables(self):
        with self.conn.cursor() as cur:
            cur.execute(open("api/db/schemas/init_db.sql", "r").read())
            self.conn.commit()

    def encrypt_data(self, data):
        return self.crypto_key.encrypt(json.dumps(data).encode())

    def decrypt_data(self, encrypted_data) -> dict | None:
        if encrypted_data is None:
            return None
        if isinstance(encrypted_data, memoryview):
            encrypted_data = encrypted_data.tobytes()
        return json.loads(self.crypto_key.decrypt(encrypted_data).decode())
    
    async def delete_user_credentials(self, telegram_id: str, provider_id: str):
        try:
            with self.conn.cursor() as cur:
                cur.execute(f"UPDATE users SET {provider_id}_credentials = NULL WHERE telegram_id = %s", (telegram_id,))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error deleting user {provider_id} credentials: {str(e)}")
            raise e
        
    async def store_user_credentials(self, telegram_id: str, credentials: Credentials | dict, provider_id: str):
        try:
            with self.conn.cursor() as cur:
                if isinstance(credentials, Credentials):
                    encrypted_creds = self.encrypt_data(credentials.to_json())
                else:
                    encrypted_creds = self.encrypt_data(credentials)
                    
                provider_column = f"{provider_id}_credentials"
                statement = f"""
                    INSERT INTO users (telegram_id, {provider_column})
                    VALUES (%s, %s)
                    ON CONFLICT (telegram_id)
                    DO UPDATE SET {provider_column} = EXCLUDED.{provider_column}
                """
                cur.execute(statement, (telegram_id, encrypted_creds))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error storing user {provider_id} credentials: {str(e)}")
            raise e

    async def get_user_credentials(self, telegram_id: str, provider_id: str) -> dict | None:
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SELECT {provider_id}_credentials FROM users WHERE telegram_id = %s", (telegram_id,))
                result = cur.fetchone()
                if result and result[f'{provider_id}_credentials']:
                    decrypted_data = self.decrypt_data(result[f'{provider_id}_credentials'])
                
                    logger.debug(f"Decrypted data type: {type(decrypted_data)}")
                    logger.debug(f"Decrypted data: {decrypted_data}")
                    
                    return decrypted_data
            return None
        except Exception as e:
            logger.error(f"Error getting user {provider_id} credentials: {str(e)}")
            raise e
        
db = Database()