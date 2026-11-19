# metocean-qc

**Português** · [English](README.en.md)

Controle de qualidade de séries temporais meteorológicas e oceanográficas de boias e estações meteorológicas.
Testes determinísticos decidem os flags; um LLM **opcional** dá uma segunda opinião sobre cada evento
(falha de sensor, evento ambiental real ou indeterminado), e a decisão final é de uma pessoa.

[![CI](https://github.com/hnryguchi/metocean-qc/actions/workflows/ci.yml/badge.svg)](https://github.com/hnryguchi/metocean-qc/actions/workflows/ci.yml) [![Live QC](https://github.com/hnryguchi/metocean-qc/actions/workflows/live.yml/badge.svg)](https://github.com/hnryguchi/metocean-qc/actions/workflows/live.yml)

[![Abrir no GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/hnryguchi/metocean-qc?quickstart=1)

## Motivação

Dados de estações estão cheios de valores que parecem errados: sensores travados, saltos de um único ponto, falhas de transmissão.
Alguns deles são reais. Uma queda de pressão acompanhada de aumento do vento é uma frente, não um barômetro quebrado.
Limiares fixos detectam bem o primeiro tipo e mal o segundo. Esta ferramenta mantém os limiares como única fonte
dos flags e usa as demais variáveis registradas no mesmo instante para explicar cada alerta.

## Execução diária

Uma GitHub Action agendada baixa os dados mais recentes da NOAA para três boias, roda os testes determinísticos
(sem LLM) e publica um **dashboard interativo** em [hnryguchi.github.io/metocean-qc](https://hnryguchi.github.io/metocean-qc/):
mapa das boias, últimas leituras com flag, série temporal de cada variável com os pontos sinalizados e as lacunas,
tabela de eventos e descrição dos testes (PT/EN). O comando que gera o site é `metqc site`.

<a href="https://hnryguchi.github.io/metocean-qc/"><img src="https://hnryguchi.github.io/metocean-qc/41010/status-pt.svg" alt="Boia 41010: últimas leituras, gráfico de 72 horas e flags de QC da execução de hoje" width="540"></a>

As boias estão em [`stations.geojson`](stations.geojson), que o GitHub renderiza como mapa interativo.

**Teste sem instalar nada:** o botão do Codespaces acima abre um ambiente pronto que baixa a boia 41010
e gera o relatório e o card na inicialização.

## Como funciona

```mermaid
flowchart LR
    A[Arquivo NOAA NDBC ou CSV] --> B[Parsing e ordenação]
    B --> C[Testes determinísticos<br/>gross range, spike, flat line, lacunas]
    C --> D[Flags por valor<br/>esquema QARTOD]
    C --> E[Agrupamento de achados em eventos]
    E -->|opcional, desligado por padrão| F[Segunda opinião do LLM<br/>saída em JSON schema]
    D --> G[Relatórios<br/>JSON + Markdown]
    E --> G
    F --> G
```

- **Flags** seguem o esquema do [IOOS QARTOD](https://ioos.noaa.gov/project/qartod/): 1 bom, 2 não avaliado, 3 suspeito, 4 falha, 9 ausente. As famílias de testes são versões simplificadas dos testes QARTOD. Esta não é uma implementação certificada do QARTOD.
- **Testes**:
  - gross range (limites físicos → falha, limites climatológicos → suspeito);
  - spike (desvio em relação à média dos vizinhos, sinalizado apenas no máximo local, para que os valores adjacentes a um spike não sejam sinalizados);
  - flat line (valor inalterado por N horas);
  - lacunas entre registros.
- **Eventos** agrupam achados próximos da mesma variável, de modo que um sensor travado gera um alerta, não 80.
- **Revisão por LLM** (`--review claude`) envia cada evento com uma janela de ±6 h de *todas* as variáveis e solicita veredito, grau de confiança, evidências e ação recomendada. A saída é restrita a um JSON schema. Uma recusa vira "incerto, requer revisão humana". A revisão nunca altera os flags.

## Início rápido

```bash
pip install -e .                       # sem dependências de runtime (apenas biblioteca padrão)
metqc fetch 41010                      # últimos ~45 dias da boia 41010 do NOAA NDBC (domínio público)
metqc check data/41010.txt --out reports/41010
metqc check data/41010.txt --out reports/41010 --card reports/41010/status.svg   # + card SVG de status
```

Entrada CSV (uma coluna de tempo em ISO-8601, uma coluna por variável; `temperatura`, `umidade`, `pressao`, `temperature`, `humidity` e `pressure` são mapeadas automaticamente):

```bash
metqc check station.csv --source csv --time-column timestamp
```

Segunda opinião opcional do LLM (**API paga**, limitada por `--max-reviews`, padrão de 10 eventos por execução):

```bash
pip install -e ".[llm]"
export ANTHROPIC_API_KEY=...           # nunca versione chaves; o código as lê do ambiente
metqc check data/41010.txt --review claude --max-reviews 5
```

## Resultados com dados reais

Testado com arquivos realtime do NOAA NDBC baixados em 2026-11-19 (cerca de 45 dias, registros a cada 10 minutos):

| Estação | Registros | Valores sinalizados | Eventos | O que foram os eventos |
|---|---|---|---|---|
| 41010 (ao largo de Cape Canaveral) | 6,347 | 12 | 2 | temperatura da água inalterada por 24 h (suspeito), uma lacuna de transmissão de 9 h |
| 44013 (aproximação de Boston) | 6,345 | 3 | 3 | dois spikes de um único ponto em temperatura do ar e ponto de orvalho (suspeito), uma lacuna |
| 46042 (Baía de Monterey) | 6,343 | 3 | 3 | spikes em ponto de orvalho e altura de onda (suspeito), uma lacuna |

**A primeira versão gerava falsos positivos, e os dados os expuseram.** A estação 41010 gerou 97 valores sinalizados,
incluindo flags FAIL para temperatura da água "travada" por 12 a 25 horas. A inspeção da série mostrou que não
eram falhas: o NDBC reporta a temperatura da água com resolução de 0,1 °C e a velocidade do vento em m/s inteiros, e
um mar tropical estável ou um alísio constante repete o mesmo valor por muitas horas. Os limiares de flat line
foram reajustados à resolução do sensor (por exemplo, temperatura da água: suspeito após 24 h, falha
após 72 h), e o raciocínio está documentado em [`src/metqc/config.py`](src/metqc/config.py).

Relatório de exemplo: [`examples/41010/qc_report.md`](examples/41010/qc_report.md).

## Estrutura do projeto

```
src/metqc/
  models.py    Series, Flag (valores QARTOD), Finding
  sources.py   parser e downloader de arquivos realtime do NDBC, leitor de CSV
  config.py    limites padrão por variável, com a justificativa de cada um
  rules.py     testes determinísticos (sem efeitos colaterais)
  engine.py    executa os testes, mantém o pior flag por valor, agrupa eventos
  review.py    revisor opcional por LLM (Claude), prompt e JSON schema
  report.py    relatórios em JSON e Markdown
  card.py      card SVG de status (últimas leituras, gráfico de 72 h com pontos sinalizados)
  site.py      dashboard estático: QC por estação, JSON para o navegador, relatórios e cards
  site/        front-end do dashboard (Plotly + Leaflet)
  cli.py       metqc fetch / metqc check [--card]
tests/         pytest; amostra real do NDBC + séries sintéticas claramente identificadas; cliente LLM falso
```

## Desenvolvimento

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q && ruff check src tests
```

O CI roda lint e testes em Python 3.10 a 3.13. Nenhum teste chama API paga: a camada de LLM é testada com um cliente falso.
Uma execução real com `--review claude` ainda não foi feita (não há chave de API na máquina de desenvolvimento). O formato
da requisição foi conferido apenas contra a assinatura do SDK `anthropic` instalado.

## Limitações e próximos passos

- Os limiares padrão são globais e amplos. O uso real exige limites por estação e por época do ano (por exemplo, derivados de climatologia).
- Ainda não há teste de taxa de variação nem testes multivariados; o raciocínio entre variáveis existe apenas na etapa opcional de LLM.
- Próximos passos: fontes brasileiras (estações automáticas do INMET, boias do PNBOIA), arquivo de limites configurável e um conjunto
  de avaliação com eventos rotulados por pessoas, para medir se a segunda opinião do LLM de fato ajuda.

## Dados e licença

- Os dados do NOAA NDBC são de domínio público (obra do governo dos EUA). A fixture de teste é um trecho de 150 registros da estação 41010.
- Código: MIT. Autor: Henry Noguchi.
