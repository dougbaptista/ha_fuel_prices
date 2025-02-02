# Fuel Prices (Preços de Combustíveis no Brasil)

Este componente personalizado para o Home Assistant busca e exibe os preços de combustíveis a partir dos dados publicados pela Agência Nacional do Petróleo, Gás Natural e Biocombustíveis (ANP). Ele extrai informações de um arquivo XLSX disponibilizado no site oficial e cria sensores que mostram os preços **mínimo**, **médio** e **máximo** para cada tipo de combustível, filtrando os dados pelo estado e município configurados.

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
  Este componente é desenvolvido para o Home Assistant (versão 2021.XX ou superior).

- **HACS:**  
  É recomendado instalar o componente via HACS.

- **Dependências Python:**  
  As dependências são definidas no `manifest.json` e incluem:
  - `aiohttp`
  - `pandas`
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

## Instalação

1. Procure por **Fuel Prices** em **Configurações > Dispositivos e Serviços**.
2. Após instalar o componente via serviços, durante o fluxo de configuração, você poderá informar:

- **Estado:** (Ex.: `SANTA CATARINA`)
- **Município:** (Ex.: `TUBARAO`)

Esses parâmetros serão utilizados para filtrar os dados da planilha e garantir que apenas os preços relevantes para sua região sejam exibidos.

## Tempo de Atualização:
Dependendo do tamanho do arquivo XLSX, a atualização dos sensores pode levar alguns segundos (entre 40 e 60 segundos). Se o tempo de atualização for elevado, verifique a conectividade e a performance do servidor.

## Contribuição
Contribuições são bem-vindas! Se você tiver sugestões, encontrar bugs ou desejar melhorias, sinta-se à vontade para abrir uma issue ou enviar um pull request no repositório.

