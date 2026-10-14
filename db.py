import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/viajuc",
)


def conectar_banco():
    """Abre uma conexão com o banco configurado em DATABASE_URL."""
    try:
        conexao = psycopg2.connect(DATABASE_URL)
        print("Conexão com o PostgreSQL estabelecida com sucesso.")
        return conexao
    except psycopg2.Error as erro:
        print(f"Não foi possível conectar ao PostgreSQL: {erro}")
        return None


if __name__ == "__main__":
    conexao = conectar_banco()
    if conexao:
        conexao.close()
