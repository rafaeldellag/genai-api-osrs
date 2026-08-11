# OSRS Loadout Value

Aplicação web para montar um equipamento e um inventário de Old School RuneScape
e estimar o valor total usando os preços em tempo real da OSRS Wiki.

## Versão online

- Aplicação: <http://163.176.11.146>
- Documentação da API: <http://163.176.11.146/docs>

## Como rodar

Com Docker e Docker Compose instalados:

```bash
git clone https://github.com/rafaeldellag/genai-api-osrs.git
cd genai-api-osrs
docker compose up --build
```

Depois, acesse <http://localhost>. A documentação interativa da API fica em
<http://localhost/docs>.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/api/health` | Verifica se a aplicação está disponível |
| `GET` | `/api/items?q=whip&slot=weapon` | Busca itens por nome e posição |
| `GET` | `/api/items/{id}` | Retorna um item pelo ID |
| `POST` | `/api/loadout/value` | Calcula o valor do equipamento e do inventário |

O preço estimado de cada item é a média entre os valores mais recentes de compra
e venda. Quando apenas um deles está disponível, esse valor é usado diretamente.

Para evitar consultas desnecessárias à OSRS Wiki, os preços ficam em cache por
60 segundos. O catálogo de itens e suas posições ficam em cache por 24 horas.

Os dados vêm da
[API de preços da OSRS Wiki](https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices)
e das
[tabelas de equipamentos](https://oldschool.runescape.wiki/w/Category:Slot_tables).

## Desenvolvimento

Para executar sem Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Para rodar os testes:

```bash
pytest
```
