import psycopg2
from psycopg2 import sql
import uuid
import os
import subprocess




def gerar_id():
    return str(uuid.uuid4())

#caso o banco não exista el será criado
def criar_banco():
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        dbname="postgres",
        user="postgres",
        password= "postgres"
    )

    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (DB_NAME,)
    )

    if cur.fetchone() is None:
        cur.execute(
            sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(DB_NAME)
            )
        )
        print("Banco criado com sucesso!")
    else:
        print("Banco já existe.")

    cur.close()
    conn.close()


def get_conn():
    return psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname='Viajuc',
        user='postgres',
        password='postgres'
    )


def listar_rotas():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM rotas ORDER BY id_rota")

    rotas = cur.fetchall()

    cur.close()
    conn.close()

    return rotas


def listar_motoristas():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM motoristas ORDER BY nome")

    motoristas = cur.fetchall()

    cur.close()
    conn.close()

    return motoristas