import psycopg2
from psycopg2 import sql
import uuid
import os
import subprocess



HOST = "localhost"
PORT = "5432"
#Nao sei se é ViaJuc ou Viajuc, isso pode causar algum erro 
DB_NAME = "ViaJuc"
#Vamos lembrar de mudar o usuario e senha pra algo mais seguro
USER = "postgres"
PASSWORD = "postgres"


def gerar_id():
    return str(uuid.uuid4())

#caso o banco não exista ele será criado
def criar_banco():
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        dbname="ViaJuc",
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
        dbname='ViaJuc',
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


def excluir(id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM rota WHERE id = %s",
        (id,)
    )

    conn.commit()
    cur.close()
    conn.close()

#Na minha opinião só faz sentido o motorista poder atualizar esses dados, mas vemos isso quando começarmos os testes
def atualizar_rotas(local_embarque,local_desembarque,preco, descricao,horario_ida,horario_volta,dias_semana):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "UPDATE rota SET local_embarque = %s, local_desembarque = %s, preco = %s, descricao = %s, horario_ida = %s, horario_volta = %s, dias_semana = %s WHERE id = %s",
        (local_embarque, local_desembarque, preco, descricao, horario_ida, horario_volta, dias_semana,)
    )

    conn.commit()
    cur.close()
    conn.close()