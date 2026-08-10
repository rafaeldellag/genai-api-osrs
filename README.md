# OSRS Loadout Value

Aplicação web que consulta a API de preços em tempo real da OSRS Wiki e calcula o
valor total de um equipamento com 11 posições e de um inventário com 28 posições.

## Executar com Docker

Pré-requisito: Docker Desktop ou Docker Engine com o Compose.

```bash
git clone https://github.com/rafaeldellag/genai-api-osrs.git
cd genai-api-osrs
docker compose up --build
```

Acesse:

- aplicação pela porta HTTP padrão: <http://localhost>
- aplicação pela porta alternativa: <http://localhost:8000>
- documentação interativa da API: <http://localhost/docs>

A imagem inclui os arquivos estáticos da interface, inclusive os 11 ícones das
posições de equipamento. O `healthcheck` do contêiner consulta
`/api/health` na porta interna 8000.

Para encerrar:

```bash
docker compose down
```

## Implantação atual na Oracle Cloud

Este projeto foi efetivamente implantado em uma VM da Oracle Cloud
Infrastructure e executa com Docker Compose. Os endereços, identificadores,
nomes dos recursos e dados de acesso da implantação não são versionados.

O Compose publica o Uvicorn nas portas TCP 80 e 8000 e usa a política
`restart: unless-stopped`. A reconstrução no servidor é feita com:

```bash
sudo docker compose up --detach --build
```

O inventário operacional da implantação é mantido somente fora do controle de
versão. O arquivo local `docs/oracle-cloud.md` é explicitamente ignorado pelo Git.

## API

| Método | Rota | Função |
| --- | --- | --- |
| `GET` | `/api/health` | Verifica se a aplicação está ativa |
| `GET` | `/api/items?q=whip&slot=weapon` | Busca itens por nome e, opcionalmente, posição de equipamento |
| `GET` | `/api/items/{id}` | Consulta um item pelo ID |
| `POST` | `/api/loadout/value` | Calcula equipamento, inventário e total |

O valor unitário estimado é a média do último preço de compra instantânea (`high`)
e venda instantânea (`low`). Se apenas um deles existir, esse valor é usado. Os
preços ficam em cache por 60 segundos; o catálogo e as posições equipáveis, por
24 horas. As posições são consultadas nos dados estruturados da OSRS Wiki.

Fontes: [OSRS Wiki Real-time Prices](https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices),
[tabelas de slots da OSRS Wiki](https://oldschool.runescape.wiki/w/Category:Slot_tables)
e [ícones de Worn Equipment](https://oldschool.runescape.wiki/w/Worn_Equipment).
O projeto envia um `User-Agent` descritivo, conforme solicitado pela API.

## Desenvolvimento local

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
pytest
```

O arquivo `environment.yml` também permite criar o ambiente com Conda. A execução
local é o ambiente de desenvolvimento; a instância pública mantida para este
projeto é a implantação OCI descrita acima.
