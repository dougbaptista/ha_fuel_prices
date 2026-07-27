# Fuel Prices (Preços de Combustíveis no Brasil)

Este componente personalizado para o Home Assistant busca e exibe os preços de combustíveis a partir dos dados publicados pela [Agência Nacional do Petróleo, Gás Natural e Biocombustíveis (ANP)](https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas). Ele extrai informações de um arquivo XLSX disponibilizado no site oficial e cria sensores que mostram os preços **mínimo**, **médio** e **máximo** para cada tipo de combustível, filtrando os dados pelo estado e município configurados.

## Recursos

- **Extração Automática:**  
  Busca automaticamente a URL do arquivo XLSX mais recente com os dados de preços semanais.

- **Suporte a Múltiplos Combustíveis:**  
  Extrai informações para os seguintes combustíveis:
  - Etanol Hidratado
  - Gasolina Comum
  - Gasolina Aditivada
  - GLP
  - GNV
  - Óleo Diesel
  - Óleo Diesel S10

- **Preços Mínimo, Médio e Máximo:**  
  Para cada combustível, o componente extrai e disponibiliza três valores:
  - **Mínimo**
  - **Médio**
  - **Máximo**

- **Filtragem por Estado e Município:**  
  Os dados são filtrados de acordo com os parâmetros de **estado** e **município** configurados na integração.  
  Por padrão, se não forem informados, os valores padrão são:
  - Estado: `SANTA CATARINA`
  - Município: `TUBARAO`

## Pré-requisitos

- **Home Assistant:**  
  Versão **2024.11.0** ou superior.

- **HACS:**  
  É recomendado instalar o componente via HACS.

- **Dependências Python:**  
  Instaladas automaticamente pelo Home Assistant a partir do `manifest.json`:
  - `openpyxl`
  - `beautifulsoup4`

## Instalação via HACS

1. **Abra o HACS no Home Assistant:**  
   No menu lateral do Home Assistant, clique em "HACS".

2. **Adicionar Repositório Personalizado:**  
   - Clique em "Integrations".
   - Clique nos três pontos no canto superior direito e selecione "Custom repositories".
   - Adicione o repositório do componente (`https://github.com/dougbaptista/ha_fuel_prices`) e selecione "Integration" como tipo.
   - Clique em "Add".

3. **Instalar o Componente:**  
   Após adicionar o repositório, volte à lista de integrações em HACS, localize "Fuel Prices" e clique em "Install".

[![HACS Repository Badge](https://camo.githubusercontent.com/8cec5af6ba93659beb5352741334ef3bbee70c4cb725f20832a1b897dfb8fc5f/68747470733a2f2f6d792e686f6d652d617373697374616e742e696f2f6261646765732f686163735f7265706f7369746f72792e737667)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dougbaptista&repository=ha_fuel_prices&category=Integration)   

5. **Reinicie o Home Assistant:**  
   Após a instalação, reinicie o Home Assistant para que o componente seja carregado.

## Configuração

1. Procure por **Fuel Prices** em **Configurações > Dispositivos e Serviços**.
2. Após instalar o componente via serviços, durante o fluxo de configuração, você poderá informar:

- **Estado:** (Ex.: `SANTA CATARINA`)
- **Município:** (Ex.: `TUBARAO`)

Esses parâmetros serão utilizados para filtrar os dados da planilha e garantir que apenas os preços relevantes para sua região sejam exibidos.

## Contribuição

Contribuições são bem-vindas! Se você tiver sugestões, encontrar bugs ou desejar melhorias, sinta-se à vontade para abrir uma issue ou enviar um pull request no repositório.

## Changelog

### v1.2.0

**⚠️ Atualização de manutenção — leia a nota de migração abaixo.**

**Correções de bugs:**

- **Unidades corrigidas para GLP e GNV.** O GLP era exibido como preço por
  litro (e depois por quilo), mas a ANP o cota **por botijão de 13 kg** — daí
  valores como `R$ 112`. O GNV era exibido por litro, mas é cotado **por m³**.
  A unidade agora é lida da coluna `UNIDADE DE MEDIDA` da própria planilha, em
  vez de ser presumida.

- **O fluxo de opções passa a ter efeito.** As opções eram salvas em
  `entry.options`, mas o código só lia `entry.data` — editar estado/município
  não mudava nada. A configuração efetiva agora é `data + options` e a
  integração se recarrega automaticamente ao salvar.

- **`unique_id` sem colisão.** O identificador era `combustível_tipo_município`,
  que colidia entre municípios homônimos de estados diferentes. Agora é
  derivado do `entry_id`. **A migração é automática** e preserva o histórico
  das entidades existentes.

**Desempenho:**

- **O event loop não trava mais.** `load_workbook`, a varredura das ~40 mil
  linhas e o parsing HTML rodavam direto na corrotina, congelando todo o Home
  Assistant por segundos a cada atualização. Agora rodam em executor.
- Normalização de texto com cache e filtro pelo município antes do estado,
  reduzindo drasticamente o trabalho por linha.
- Logging preguiçoso (`%s`), eliminando formatação de string dentro do laço
  principal mesmo com DEBUG desligado.

**Segurança:**

- **Teto de download de 50 MB**, verificado por `Content-Length` e durante a
  leitura em blocos, evitando exaustão de memória por arquivo anômalo.
- **Validação do link extraído da página:** resolução correta com `urljoin`,
  exigência de HTTPS e restrição ao domínio `gov.br`.
- **Dependências fixadas** no `manifest.json`; `aiohttp` removido de lá, já que
  é dependência do próprio core (declará-la sem versão permitia atualizar a
  biblioteca de rede do Home Assistant durante a instalação).

**Qualidade e diagnóstico:**

- Cada falha (rede, HTTP, layout do site, aba ausente, coluna ausente,
  município inexistente) agora produz uma mensagem específica. Antes, todas
  apareciam como "Nenhum dado retornado", apontando para a causa errada.
- **Dados obsoletos são sinalizados.** O último valor válido continua sendo
  preservado durante falhas passageiras, mas após 14 dias as entidades ficam
  indisponíveis em vez de publicar um preço antigo como se fosse atual. A idade
  é medida pelo período de referência publicado na planilha (`period_start` /
  `period_end`), não pela hora do download.
- **Novos atributos:** `surveyed_stations` (quantos postos a ANP pesquisou —
  amostra pequena significa preço menos representativo), `period_start`,
  `period_end`, `last_successful_update` e `stale`.
- **Normalização defensiva** de estado, município e produto. A ANP hoje publica
  esses campos sem acento; a normalização garante que a integração continue
  funcionando caso isso mude, e aceita entrada acentuada do usuário
  (`Tubarão`, `Criciúma`) na configuração.
- `state_class: measurement` e `native_unit_of_measurement`, habilitando
  estatísticas de longo prazo (gráficos históricos).
- Todos os sensores agrupados sob um dispositivo por município.
- Fluxo de configuração valida a entrada e impede cadastrar o mesmo município
  duas vezes.
- Traduções completas (`en` + `pt-BR`), incluindo o fluxo de opções.
- CI deixou de mascarar falhas com `|| true` e ganhou validação `hassfest` e
  HACS; a suíte de testes agora cobre o parsing real da planilha.

#### Nota de migração

O diretório da integração foi renomeado de `custom_components/ha_fuel_prices`
para `custom_components/fuel_prices`, para coincidir com o domínio declarado no
`manifest.json` — requisito do Home Assistant e do `hassfest`.

Suas configurações e o histórico são preservados (o domínio `fuel_prices` não
mudou). Se você instalou via HACS, atualize normalmente e **remova a pasta
antiga** `custom_components/ha_fuel_prices` caso ela permaneça, antes de
reiniciar o Home Assistant.

### v1.1.0

**Melhorias de desempenho e estabilidade:**

- **Coordenador centralizado (DataUpdateCoordinator):** Os dados da ANP agora são buscados uma única vez e compartilhados entre todos os sensores. Antes, cada sensor (21 no total) fazia seu próprio download e processamento do arquivo — agora é apenas 1 requisição por ciclo.

- **Intervalo de atualização otimizado:** Atualização a cada 6 horas (os dados da ANP são semanais, não faz sentido consultar com mais frequência).

- **Remoção do pandas:** Substituído por leitura direta com `openpyxl` em modo `read_only`. Reduz significativamente o consumo de memória e o tempo de inicialização, especialmente em dispositivos como Raspberry Pi.

- **Leitura em memória do XLSX:** O arquivo XLSX agora é processado em memória (`BytesIO`) evitando gravação em disco temporário.

- **Preservação do histórico:** O sensor agora mantém o último valor válido quando os dados estão indisponíveis (erro de rede, arquivo corrompido, valor inválido). Isso evita "buracos" no histórico com estados `unknown/unavailable`.

- **Sessão HTTP reutilizável e timeouts:** Usa a sessão HTTP do Home Assistant (`async_get_clientsession`) com timeout, melhorando estabilidade e integração.

- **Edição pós-instalação:** Adicionado `Options Flow` para permitir editar `estado` e `município` depois da criação da integração.

### v1.0.0

- Versão inicial com busca de preços da ANP por município.

## Desenvolvimento

Se você deseja contribuir ou rodar verificações locais, siga estas instruções recomendadas.

- Instale Python 3.12 (mesma versão usada pelo CI).
- Crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

- Atualize o pip e instale dependências de desenvolvimento:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
python -m pip install pre-commit
```

- Rode os hooks do pre-commit (formatação e lint):

```powershell
pre-commit install
pre-commit run --all-files
```

- Rode os testes:

```powershell
pytest -q
```

Observações:
- O CI do repositório roda em Python 3.12 e **reprova** o build em qualquer erro de `black`, `isort`, `flake8` ou `pytest`.
- Toda a lógica de scraping e parsing vive em `custom_components/fuel_prices/parser.py`, que não importa nada do Home Assistant. Isso permite testá-la diretamente, com planilhas XLSX geradas em memória pelos testes.
- Não é necessário instalar `homeassistant` para rodar a suíte: `tests/conftest.py` instala stubs mínimos **apenas se** o pacote não estiver presente, então instalar o HA de verdade (ou o `pytest-homeassistant-custom-component`) continua funcionando.

### Estrutura

```
custom_components/fuel_prices/
├── __init__.py       # setup/unload da entrada, listener de opções, migração de unique_id
├── config_flow.py    # fluxos de configuração e opções
├── const.py          # constantes e limites
├── coordinator.py    # I/O HTTP, timeouts, teto de download, ponte com o executor
├── parser.py         # lógica pura: scraping, parsing do XLSX, normalização
└── sensor.py         # entidades
```
