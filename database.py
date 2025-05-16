# database.py
import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    try:
        conn = psycopg2.connect(
            dbname="juscash",
            user="postgres",
            password="aquario98",
            host="localhost",
            port="5432"
        )
        return conn
    except Exception as e:
        print(f"Erro ao conectar: {e}")
        return None