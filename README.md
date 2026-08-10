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

- aplicação: <http://localhost:8000>
- documentação interativa da API: <http://localhost:8000/docs>

Para encerrar:

```bash
docker compose down
```

## API

| Método | Rota | Função |
| --- | --- | --- |
| `GET` | `/api/health` | Verifica se a aplicação está ativa |
| `GET` | `/api/items?q=whip` | Busca itens por nome com preços atuais |
| `GET` | `/api/items/{id}` | Consulta um item pelo ID |
| `POST` | `/api/loadout/value` | Calcula equipamento, inventário e total |

O valor unitário estimado é a média do último preço de compra instantânea (`high`)
e venda instantânea (`low`). Se apenas um deles existir, esse valor é usado. As
respostas da Wiki ficam em cache por 60 segundos para evitar consultas excessivas.

Fonte: [OSRS Wiki Real-time Prices](https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices).
O projeto envia um `User-Agent` descritivo, conforme solicitado pela API.

## Desenvolvimento local

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
pytest
```

O arquivo `environment.yml` também permite criar o ambiente com Conda. O contêiner
é autocontido e pode rodar da mesma forma em qualquer servidor com Docker, inclusive
uma VM na Oracle Cloud; nenhum recurso de nuvem é necessário para a execução local.
