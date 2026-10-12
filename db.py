import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def conectar_banco():
    try:
        conexao = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        print("Conectado ao PostgreSQL com sucesso!")
        return conexao
        
    except Exception as error:
        print(f"Erro ao conectar ao banco de dados: {error}")
        return None

if __name__ == "__main__":
    conn = conectar_banco()
    if conn:
        conn.close()