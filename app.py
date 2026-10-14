import os
import re
from contextlib import contextmanager
from datetime import date, time, timedelta
from functools import wraps

import click
import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from flask.json.provider import DefaultJSONProvider
from psycopg2 import errors as pgerr
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from werkzeug.security import check_password_hash, generate_password_hash


# ============================================================
# Configuração
# ============================================================
load_dotenv()


class JSONProvider(DefaultJSONProvider):
    """Serializa datetime.time (usado em horarios_ida/volta) como 'HH:MM'."""

    @staticmethod
    def default(o):
        if isinstance(o, time):
            return o.strftime("%H:%M")
        return DefaultJSONProvider.default(o)


app = Flask(__name__)
app.json = JSONProvider(app)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ViaJuc",
)
pool = ThreadedConnectionPool(1, 10, DATABASE_URL)


@contextmanager
def cursor():
    """Entrega um cursor (dict) e faz commit/rollback automaticamente."""
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ============================================================
# Erros
# ============================================================
class ApiError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


@app.errorhandler(ApiError)
def handle_api_error(e):
    return jsonify(erro=e.message), e.status


@app.errorhandler(pgerr.UniqueViolation)
def handle_unique(e):
    return jsonify(erro="Registro duplicado (e-mail, placa ou cidade já cadastrados).",
                   detalhe=e.diag.constraint_name), 409


@app.errorhandler(pgerr.RaiseException)  # mensagens dos triggers (ex.: veículo de outro motorista)
def handle_raise(e):
    return jsonify(erro=e.diag.message_primary), 400


@app.errorhandler(pgerr.IntegrityError)
def handle_integrity(e):
    return jsonify(erro="Dados inválidos ou referência inexistente.",
                   detalhe=e.diag.message_primary), 400


@app.errorhandler(psycopg2.DataError)
def handle_data(e):
    return jsonify(erro="Formato de dado inválido.", detalhe=e.diag.message_primary), 400


# ============================================================
# Autenticação (sessão por cookie)
# ============================================================
def login_required(role):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get("role") != role:
                raise ApiError("Acesso não autorizado.", 401)
            return fn(*args, **kwargs)
        return wrapper
    return deco


def current_id():
    return session["id"]


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Envie um JSON válido no corpo da requisição.")
    return data


def require(data, *fields):
    faltando = [f for f in fields if data.get(f) in (None, "")]
    if faltando:
        raise ApiError(f"Campos obrigatórios ausentes: {', '.join(faltando)}")


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PLACA_RE = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")
HORA_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _login(tabela, id_col, perfil):
    data = body()
    require(data, "email", "senha")
    with cursor() as cur:
        extra = ", ativo" if tabela == "motorista" else ""
        cur.execute(f"SELECT {id_col} AS id, nome, senha_hash{extra} FROM {tabela} WHERE email = %s",
                    (data["email"].strip(),))
        u = cur.fetchone()
    if not u or not check_password_hash(u["senha_hash"], data["senha"]):
        raise ApiError("E-mail ou senha incorretos.", 401)
    if u.get("ativo") is False:
        raise ApiError("Conta desativada. Fale com a administração.", 403)
    session.clear()
    session.update(role=perfil, id=u["id"])
    return jsonify(id=u["id"], nome=u["nome"], perfil=perfil)


@app.post("/api/auth/motorista/login")
def login_motorista():
    return _login("motorista", "id_motorista", "motorista")


@app.post("/api/auth/admin/login")
def login_admin():
    return _login("administrador", "id_administrador", "admin")


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/auth/me")
def me():
    if "role" not in session:
        raise ApiError("Não autenticado.", 401)
    return jsonify(perfil=session["role"], id=session["id"])


# ============================================================
# Público: cidades e vitrine de rotas
# ============================================================
@app.get("/api/cidades")
def listar_cidades():
    with cursor() as cur:
        cur.execute("SELECT id_cidade, nome, uf FROM cidade ORDER BY nome")
        return jsonify(cur.fetchall())


ROTA_SELECT = """
    SELECT r.id_rota, r.local_embarque, r.local_desembarque, r.preco, r.descricao,
           r.datas_semana, r.data_inicio, r.data_fim, r.horarios_ida, r.horarios_volta,
           r.ativa, r.atualizado_em,
           co.id_cidade AS id_origem,  co.nome AS origem,  co.uf AS origem_uf,
           cd.id_cidade AS id_destino, cd.nome AS destino, cd.uf AS destino_uf,
           m.id_motorista, m.nome AS motorista, m.telefone, m.foto_url AS motorista_foto,
           v.id_veiculo, v.modelo, v.placa, v.tipo, v.foto_url AS veiculo_foto
    FROM rota r
    JOIN cidade   co ON co.id_cidade   = r.id_origem
    JOIN cidade   cd ON cd.id_cidade   = r.id_destino
    JOIN motorista m ON m.id_motorista = r.id_motorista
    JOIN veiculo   v ON v.id_veiculo   = r.id_veiculo
"""


@app.get("/api/rotas")
def listar_rotas():
    """Filtros (query string): origem, destino (ids), dia (1=Seg..7=Dom), tipo."""
    where = ["r.ativa", "m.ativo", "v.ativo",
             "(r.data_fim IS NULL OR r.data_fim >= CURRENT_DATE)"]
    params = []

    for arg, col in (("origem", "r.id_origem"), ("destino", "r.id_destino")):
        if request.args.get(arg):
            where.append(f"{col} = %s")
            params.append(request.args[arg])
    if request.args.get("dia"):
        where.append("%s = ANY (r.datas_semana)")
        params.append(request.args["dia"])
    if request.args.get("tipo"):
        where.append("v.tipo = %s")
        params.append(request.args["tipo"])

    sql = f"{ROTA_SELECT} WHERE {' AND '.join(where)} ORDER BY co.nome, cd.nome, r.preco NULLS LAST"
    with cursor() as cur:
        cur.execute(sql, params)
        return jsonify(cur.fetchall())


@app.get("/api/rotas/<int:id_rota>")
def detalhe_rota(id_rota):
    with cursor() as cur:
        cur.execute(f"{ROTA_SELECT} WHERE r.id_rota = %s AND r.ativa AND m.ativo", (id_rota,))
        rota = cur.fetchone()
    if not rota:
        raise ApiError("Rota não encontrada.", 404)
    return jsonify(rota)


@app.get("/api/rotas/<int:id_rota>/datas")
def datas_da_rota(id_rota):
    """Calendário: datas reais em que a rota roda. ?de=YYYY-MM-DD&ate=YYYY-MM-DD
    (padrão: do dia 1 ao último dia do mês atual; máximo 366 dias)."""
    try:
        hoje = date.today()
        de = date.fromisoformat(request.args["de"]) if "de" in request.args else hoje.replace(day=1)
        if "ate" in request.args:
            ate = date.fromisoformat(request.args["ate"])
        else:
            prox = (de.replace(day=28) + timedelta(days=4)).replace(day=1)
            ate = prox - timedelta(days=1)
    except ValueError:
        raise ApiError("Datas devem estar no formato YYYY-MM-DD.")
    if ate < de or (ate - de).days > 366:
        raise ApiError("Intervalo inválido (máximo de 366 dias).")

    with cursor() as cur:
        cur.execute("SELECT data FROM gerar_datas_rota(%s, %s, %s)", (id_rota, de, ate))
        datas = [r["data"].isoformat() for r in cur.fetchall()]
    return jsonify(id_rota=id_rota, de=de, ate=ate, datas=datas)


# ============================================================
# Motorista: cadastro, perfil
# ============================================================
@app.post("/api/motoristas")
def cadastrar_motorista():
    data = body()
    require(data, "nome", "email", "senha", "telefone")
    if not EMAIL_RE.match(data["email"].strip()):
        raise ApiError("E-mail inválido.")
    if len(data["senha"]) < 8:
        raise ApiError("A senha deve ter pelo menos 8 caracteres.")
    with cursor() as cur:
        cur.execute(
            """INSERT INTO motorista (nome, email, senha_hash, telefone, foto_url)
               VALUES (%s, %s, %s, %s, %s) RETURNING id_motorista, nome, email, telefone, foto_url""",
            (data["nome"].strip(), data["email"].strip(), generate_password_hash(data["senha"]),
             data["telefone"].strip(), data.get("foto_url")),
        )
        return jsonify(cur.fetchone()), 201


@app.get("/api/motorista/perfil")
@login_required("motorista")
def meu_perfil():
    with cursor() as cur:
        cur.execute("SELECT id_motorista, nome, email, telefone, foto_url, criado_em "
                    "FROM motorista WHERE id_motorista = %s", (current_id(),))
        return jsonify(cur.fetchone())


@app.patch("/api/motorista/perfil")
@login_required("motorista")
def atualizar_perfil():
    data = body()
    campos = {k: data[k] for k in ("nome", "telefone", "foto_url") if k in data}
    if "senha" in data:
        if len(data["senha"]) < 8:
            raise ApiError("A senha deve ter pelo menos 8 caracteres.")
        campos["senha_hash"] = generate_password_hash(data["senha"])
    if not campos:
        raise ApiError("Nada para atualizar.")
    sets = ", ".join(f"{c} = %s" for c in campos)
    with cursor() as cur:
        cur.execute(f"UPDATE motorista SET {sets} WHERE id_motorista = %s "
                    "RETURNING id_motorista, nome, email, telefone, foto_url",
                    (*campos.values(), current_id()))
        return jsonify(cur.fetchone())


# ============================================================
# Motorista: veículos
# ============================================================
TIPOS_VEICULO = {"van", "onibus", "micro-onibus", "carro"}


def normalizar_placa(p):
    p = re.sub(r"[\s-]", "", str(p)).upper()
    if not PLACA_RE.match(p):
        raise ApiError("Placa inválida. Use AAA9999 ou AAA9A99.")
    return p


@app.get("/api/motorista/veiculos")
@login_required("motorista")
def meus_veiculos():
    with cursor() as cur:
        cur.execute("SELECT * FROM veiculo WHERE id_motorista = %s ORDER BY ativo DESC, modelo",
                    (current_id(),))
        return jsonify(cur.fetchall())


@app.post("/api/motorista/veiculos")
@login_required("motorista")
def criar_veiculo():
    data = body()
    require(data, "modelo", "placa", "tipo")
    if data["tipo"] not in TIPOS_VEICULO:
        raise ApiError(f"Tipo inválido. Use um de: {', '.join(sorted(TIPOS_VEICULO))}.")
    with cursor() as cur:
        cur.execute(
            """INSERT INTO veiculo (id_motorista, modelo, placa, tipo, foto_url)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (current_id(), data["modelo"].strip(), normalizar_placa(data["placa"]),
             data["tipo"], data.get("foto_url")),
        )
        return jsonify(cur.fetchone()), 201


@app.patch("/api/motorista/veiculos/<int:id_veiculo>")
@login_required("motorista")
def atualizar_veiculo(id_veiculo):
    data = body()
    campos = {k: data[k] for k in ("modelo", "tipo", "foto_url", "ativo") if k in data}
    if "placa" in data:
        campos["placa"] = normalizar_placa(data["placa"])
    if "tipo" in campos and campos["tipo"] not in TIPOS_VEICULO:
        raise ApiError("Tipo de veículo inválido.")
    if not campos:
        raise ApiError("Nada para atualizar.")
    sets = ", ".join(f"{c} = %s" for c in campos)
    with cursor() as cur:
        cur.execute(f"UPDATE veiculo SET {sets} WHERE id_veiculo = %s AND id_motorista = %s RETURNING *",
                    (*campos.values(), id_veiculo, current_id()))
        v = cur.fetchone()
    if not v:
        raise ApiError("Veículo não encontrado.", 404)
    return jsonify(v)


@app.delete("/api/motorista/veiculos/<int:id_veiculo>")
@login_required("motorista")
def aposentar_veiculo(id_veiculo):
    """Não apaga: apenas aposenta (ativo = FALSE), preservando o histórico das rotas."""
    with cursor() as cur:
        cur.execute("UPDATE veiculo SET ativo = FALSE WHERE id_veiculo = %s AND id_motorista = %s "
                    "RETURNING id_veiculo", (id_veiculo, current_id()))
        if not cur.fetchone():
            raise ApiError("Veículo não encontrado.", 404)
    return "", 204


# ============================================================
# Motorista: rotas
# ============================================================
# coluna -> expressão de placeholder (com cast quando o tipo é array/time/date)
ROTA_COLS = {
    "id_veiculo": "%s", "id_origem": "%s", "id_destino": "%s",
    "local_embarque": "%s", "local_desembarque": "%s",
    "preco": "%s", "descricao": "%s",
    "datas_semana": "%s::smallint[]",
    "data_inicio": "%s::date", "data_fim": "%s::date",
    "horarios_ida": "%s::time[]", "horarios_volta": "%s::time[]",
    "ativa": "%s",
}


def validar_rota(data, parcial=False):
    campos = {k: data[k] for k in ROTA_COLS if k in data}

    if not parcial:
        require(data, "id_veiculo", "id_origem", "id_destino",
                "local_embarque", "local_desembarque", "datas_semana")
        campos.setdefault("horarios_ida", [])
        campos.setdefault("horarios_volta", [])

    if "datas_semana" in campos:
        d = campos["datas_semana"]
        if not isinstance(d, list) or not d or any(not isinstance(x, int) or not 1 <= x <= 7 for x in d):
            raise ApiError("datas_semana deve ser uma lista de inteiros de 1 (Seg) a 7 (Dom).")
        campos["datas_semana"] = sorted(set(d))

    for k in ("horarios_ida", "horarios_volta"):
        if k in campos:
            h = campos[k]
            if not isinstance(h, list) or any(not isinstance(x, str) or not HORA_RE.match(x) for x in h):
                raise ApiError(f"{k} deve ser uma lista de horários 'HH:MM'.")
            campos[k] = sorted(set(h))

    if not parcial and not (campos["horarios_ida"] or campos["horarios_volta"]):
        raise ApiError("Informe ao menos um horário de ida ou de volta.")
    if "id_origem" in campos and "id_destino" in campos and campos["id_origem"] == campos["id_destino"]:
        raise ApiError("Origem e destino devem ser diferentes.")
    if campos.get("preco") is not None and float(campos["preco"]) < 0:
        raise ApiError("O preço não pode ser negativo.")
    return campos


@app.get("/api/motorista/rotas")
@login_required("motorista")
def minhas_rotas():
    with cursor() as cur:
        cur.execute(f"{ROTA_SELECT} WHERE r.id_motorista = %s ORDER BY r.ativa DESC, r.atualizado_em DESC",
                    (current_id(),))
        return jsonify(cur.fetchall())


@app.post("/api/motorista/rotas")
@login_required("motorista")
def criar_rota():
    campos = validar_rota(body())
    cols = ["id_motorista", *campos]
    marks = ["%s", *(ROTA_COLS[c] for c in campos)]
    with cursor() as cur:
        cur.execute(f"INSERT INTO rota ({', '.join(cols)}) VALUES ({', '.join(marks)}) RETURNING id_rota",
                    (current_id(), *campos.values()))
        novo = cur.fetchone()["id_rota"]
        cur.execute(f"{ROTA_SELECT} WHERE r.id_rota = %s", (novo,))
        return jsonify(cur.fetchone()), 201


@app.patch("/api/motorista/rotas/<int:id_rota>")
@login_required("motorista")
def atualizar_rota(id_rota):
    campos = validar_rota(body(), parcial=True)
    if not campos:
        raise ApiError("Nada para atualizar.")
    sets = ", ".join(f"{c} = {ROTA_COLS[c]}" for c in campos)
    with cursor() as cur:
        cur.execute(f"UPDATE rota SET {sets} WHERE id_rota = %s AND id_motorista = %s RETURNING id_rota",
                    (*campos.values(), id_rota, current_id()))
        if not cur.fetchone():
            raise ApiError("Rota não encontrada.", 404)
        cur.execute(f"{ROTA_SELECT} WHERE r.id_rota = %s", (id_rota,))
        return jsonify(cur.fetchone())


@app.delete("/api/motorista/rotas/<int:id_rota>")
@login_required("motorista")
def excluir_rota(id_rota):
    with cursor() as cur:
        cur.execute("DELETE FROM rota WHERE id_rota = %s AND id_motorista = %s RETURNING id_rota",
                    (id_rota, current_id()))
        if not cur.fetchone():
            raise ApiError("Rota não encontrada.", 404)
    return "", 204


# ============================================================
# Administrador
# ============================================================
@app.post("/api/admin/cidades")
@login_required("admin")
def criar_cidade():
    data = body()
    require(data, "nome", "uf")
    uf = data["uf"].strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", uf):
        raise ApiError("UF deve ter 2 letras.")
    with cursor() as cur:
        cur.execute("INSERT INTO cidade (nome, uf) VALUES (%s, %s) RETURNING *",
                    (data["nome"].strip(), uf))
        return jsonify(cur.fetchone()), 201


@app.get("/api/admin/motoristas")
@login_required("admin")
def admin_listar_motoristas():
    with cursor() as cur:
        cur.execute("""SELECT m.id_motorista, m.nome, m.email, m.telefone, m.ativo, m.criado_em,
                              (SELECT COUNT(*) FROM rota r WHERE r.id_motorista = m.id_motorista) AS total_rotas
                       FROM motorista m ORDER BY m.criado_em DESC""")
        return jsonify(cur.fetchall())


@app.patch("/api/admin/motoristas/<int:id_motorista>")
@login_required("admin")
def admin_ativar_motorista(id_motorista):
    data = body()
    if not isinstance(data.get("ativo"), bool):
        raise ApiError("Envie {\"ativo\": true|false}.")
    with cursor() as cur:
        cur.execute("UPDATE motorista SET ativo = %s WHERE id_motorista = %s "
                    "RETURNING id_motorista, nome, ativo", (data["ativo"], id_motorista))
        m = cur.fetchone()
    if not m:
        raise ApiError("Motorista não encontrado.", 404)
    return jsonify(m)


# ============================================================
# CLI
# ============================================================
@app.cli.command("criar-admin")
@click.option("--nome", prompt=True)
@click.option("--email", prompt=True)
@click.password_option()
def criar_admin(nome, email, password):
    """Cria um administrador (não há cadastro público de admin)."""
    with cursor() as cur:
        cur.execute("INSERT INTO administrador (nome, email, senha_hash) VALUES (%s, %s, %s)",
                    (nome, email, generate_password_hash(password)))
    click.echo("Administrador criado.")


# ============================================================
@app.get("/")
def pagina_inicio():
    return render_template("index.html")


@app.get("/rota/<int:id_rota>")
def pagina_rota(id_rota):
    return render_template("rota.html")


@app.get("/motorista/login")
def pagina_login_motorista():
    return render_template("motorista/login.html")


@app.get("/motorista/cadastro")
def pagina_cadastro_motorista():
    return render_template("motorista/cadastro.html")


@app.get("/motorista/painel")
def pagina_painel_motorista():
    return render_template("motorista/painel.html")


@app.get("/api/saude")
def saude():
    with cursor() as cur:
        cur.execute("SELECT 1")
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(debug=True)
