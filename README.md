# ViaJuc

O ViaJuc organiza informações sobre rotas de ônibus, vans e outros veículos, incluindo cidades, horários, locais de embarque e desembarque e dados dos motoristas.

## Requisitos

- Python 3.10 ou superior
- PostgreSQL instalado e em execução
- Um banco de dados criado a partir do esquema SQL utilizado pelo projeto

## Configuração no Windows (PowerShell)

1. Abra o PowerShell na pasta que contém `app.py`.
2. Crie o ambiente virtual:

   ```powershell
   python -m venv .venv
   ```

3. Instale as dependências usando diretamente o Python do ambiente virtual. Assim, não é necessário ativar scripts do PowerShell:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Copie `.env.example` para `.env` e edite `DATABASE_URL` com a senha correta do PostgreSQL. O padrão de desenvolvimento deste projeto aponta para o banco `ViaJuc` em `localhost:5432`.

   ```text
   DATABASE_URL=postgresql://postgres:SUA_SENHA@localhost:5432/ViaJuc
   SECRET_KEY=uma-chave-aleatoria
   ```

   Se a senha tiver caracteres especiais (como `@`, `:` ou `/`), codifique-os para uso em uma URL. Não envie o arquivo `.env` ao Git nem compartilhe sua senha.

5. Inicie o servidor:

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app app run --debug
   ```

6. Acesse `http://127.0.0.1:5000` no navegador. Para verificar a conexão com o banco, abra `http://127.0.0.1:5000/api/saude`.

## Cidades para teste

O formulário precisa de pelo menos duas cidades para permitir uma rota entre origem e destino diferentes. Se o banco tiver apenas Jucurutu, execute o arquivo `sql/cidades_iniciais.sql` no Query Tool do pgAdmin conectado ao banco `ViaJuc`. Ele adiciona Jucurutu, Caicó e Natal caso ainda não existam. O script não cria rotas nem horários fictícios.

## Estrutura do projeto

```text
ViaJuc-main/
├── app.py                     # Rotas Flask, validações e acesso ao banco
├── db.py                      # Teste de conexão com o PostgreSQL
├── requirements.txt           # Dependências Python
├── .env.example               # Modelo de configuração local
├── sql/
│   └── cidades_iniciais.sql   # Cidades opcionais para desenvolvimento
├── static/
│   ├── app.js                 # Interações e chamadas à API
│   └── style.css              # Estilos e responsividade
└── templates/
    ├── base.html              # Estrutura compartilhada das páginas
    ├── index.html             # Busca de viagens
    ├── rota.html              # Detalhes e horários de uma rota
    └── motorista/             # Login, cadastro e painel do motorista
```

## Observações

- O ambiente virtual `.venv` é local e não deve ser versionado.
- O arquivo `.env` contém configurações locais e deve permanecer privado.
- O modo `--debug` é indicado somente para desenvolvimento local, não para produção.
