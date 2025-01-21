async def fetch_data():
    """Função para buscar e processar os dados da planilha."""
    data = {}
    try:
        # Caminho ou URL da planilha
        file_path = "/mnt/data/resumo_semanal_lpc_2025-01-12_2025-01-18.xlsx"
        
        # Lendo a planilha
        df = pd.read_excel(file_path)

        # Garantindo que as colunas necessárias existem
        required_columns = ["MUNICÍPIO", "PRODUTO", "PREÇO MÉDIO REVENDA"]
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"Colunas obrigatórias não encontradas na planilha: {df.columns}")

        # Filtrando os dados para Santa Catarina
        df_sc = df[df["MUNICÍPIO"] == "SANTA CATARINA"]

        # Calculando o preço médio para cada tipo de combustível
        for fuel_type in df_sc["PRODUTO"].unique():
            fuel_data = df_sc[df_sc["PRODUTO"] == fuel_type]
            avg_price = fuel_data["PREÇO MÉDIO REVENDA"].mean()
            data[fuel_type] = round(avg_price, 2)  # Arredondar para 2 casas decimais

    except Exception as e:
        _LOGGER.error(f"Erro ao processar dados da planilha: {e}")

    return data
