"""Lógica pura de scraping e parsing dos dados da ANP.

Este módulo não importa nada do Home Assistant de propósito: tudo aqui é
síncrono, determinístico e testável isoladamente. O coordinator é quem faz a
ponte com o HA e executa estas funções fora do event loop.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from functools import lru_cache
from io import BytesIO
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from openpyxl import load_workbook

from .const import ALLOWED_HOST_SUFFIX, MAX_DOWNLOAD_BYTES

_LOGGER = logging.getLogger(__name__)

SHEET_NAME = "MUNICIPIOS"

COL_STATE = "ESTADO"
COL_CITY = "MUNICIPIO"
COL_PRODUCT = "PRODUTO"
COL_MED = "PRECO MEDIO REVENDA"
COL_MIN = "PRECO MINIMO REVENDA"
COL_MAX = "PRECO MAXIMO REVENDA"

REQUIRED_COLUMNS = (COL_STATE, COL_CITY, COL_PRODUCT, COL_MED, COL_MIN, COL_MAX)

# Quantas linhas do topo inspecionar procurando o cabeçalho real.
HEADER_SEARCH_LIMIT = 25

LINK_TEXT_RE = re.compile(
    r"pre[çc]os?\s+m[ée]dios?\s+semanais.*munic[íi]pios",
    re.IGNORECASE | re.DOTALL,
)

_WHITESPACE_RE = re.compile(r"\s+")


class FuelPricesError(Exception):
    """Erro base da integração."""


class SourceUnavailableError(FuelPricesError):
    """A página ou o arquivo da ANP não pôde ser obtido/interpretado."""


class MunicipalityNotFoundError(FuelPricesError):
    """O município configurado não existe na planilha da ANP."""


@lru_cache(maxsize=4096)
def normalize_text(text: str) -> str:
    """Remove acentos, colapsa espaços e devolve em maiúsculas.

    Usada em loop sobre dezenas de milhares de células, por isso o cache: o
    domínio de valores (estados, municípios, produtos) é pequeno e repetitivo.
    """
    normalized = (
        unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")
    )
    return _WHITESPACE_RE.sub(" ", normalized).upper().strip()


def normalize_value(value: object) -> str:
    """Normaliza um valor arbitrário de célula para texto comparável."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return normalize_text(value)


def make_unique_id(entry_id: str, fuel_type: str, price_type: str) -> str:
    """Monta o unique_id de uma entidade.

    Baseado no ``entry_id`` e não em estado/município: assim não há colisão
    entre municípios homônimos e as entidades sobrevivem a uma troca de cidade
    pelo fluxo de opções, preservando o histórico.
    """
    slug = normalize_text(f"{fuel_type} {price_type}").lower().replace(" ", "_")
    return f"{entry_id}_{slug}"


def legacy_unique_id(fuel_type: str, price_type: str, city: str) -> str:
    """Reproduz o unique_id usado até a v1.1.0, para migração do registro."""
    base = f"{fuel_type}_{price_type}_{city}"
    return normalize_text(base).lower().replace(" ", "_")


def find_xls_url(html: str, base_url: str) -> str:
    """Extrai da página da ANP a URL da planilha semanal por município.

    Levanta ``SourceUnavailableError`` se o link não for encontrado ou apontar
    para fora do domínio esperado.
    """
    soup = BeautifulSoup(html, "html.parser")

    candidates: list[str] = []
    for anchor in soup.find_all("a", href=True):
        # get_text agrega o texto de tags aninhadas (<span>, <strong>, ...),
        # ao contrário de find_all(string=...), que só casa nós de texto puros.
        label = anchor.get_text(" ", strip=True)
        if not LINK_TEXT_RE.search(label):
            continue
        href = anchor["href"]
        if not href.lower().split("?")[0].endswith((".xlsx", ".xls")):
            continue
        candidates.append(urljoin(base_url, href))

    if not candidates:
        raise SourceUnavailableError(
            "Nenhum link para a planilha semanal por município foi encontrado "
            "na página da ANP (o layout do site pode ter mudado)."
        )

    url = candidates[0]
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if parsed.scheme != "https" or not (
        hostname == "gov.br" or hostname.endswith(ALLOWED_HOST_SUFFIX)
    ):
        raise SourceUnavailableError(f"URL da planilha em host inesperado: {url}")

    return url


def coerce_price(raw: object) -> float | None:
    """Converte um valor de célula em ``float``, tolerando formato brasileiro."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)

    text = str(raw).strip()
    if not text or text in {"-", "--"}:
        return None

    # "1.234,56" -> "1234.56" ; "1234,56" -> "1234.56" ; "1234.56" -> inalterado
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _find_header_row(rows: list[tuple]) -> tuple[int, list[str]]:
    """Localiza a linha de cabeçalho em vez de assumir uma posição fixa."""
    for index, row in enumerate(rows):
        headers = [normalize_value(cell) for cell in row]
        if all(col in headers for col in (COL_STATE, COL_CITY, COL_PRODUCT)):
            return index, headers
    raise SourceUnavailableError(
        "Cabeçalho não localizado nas primeiras "
        f"{len(rows)} linhas da aba {SHEET_NAME}."
    )


def parse_workbook(content: bytes, state: str, city: str) -> dict[str, dict]:
    """Extrai os preços do XLSX para o estado/município informados.

    Função síncrona e pesada (CPU): deve ser chamada em executor.
    """
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise SourceUnavailableError(
            f"Planilha excede o limite de {MAX_DOWNLOAD_BYTES} bytes."
        )

    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    try:
        if SHEET_NAME not in workbook.sheetnames:
            raise SourceUnavailableError(
                f"Aba '{SHEET_NAME}' não encontrada. "
                f"Abas disponíveis: {', '.join(workbook.sheetnames)}"
            )
        sheet = workbook[SHEET_NAME]

        head = []
        for offset, row in enumerate(sheet.iter_rows(values_only=True)):
            if offset >= HEADER_SEARCH_LIMIT:
                break
            head.append(row)

        header_index, headers = _find_header_row(head)

        col_map: dict[str, int] = {}
        for column in REQUIRED_COLUMNS:
            if column not in headers:
                raise SourceUnavailableError(
                    f"Coluna esperada '{column}' não encontrada. "
                    f"Colunas lidas: {', '.join(h for h in headers if h)}"
                )
            col_map[column] = headers.index(column)

        state_filter = normalize_text(state)
        city_filter = normalize_text(city)
        max_index = max(col_map.values())

        prices: dict[str, dict] = {}
        for row in sheet.iter_rows(min_row=header_index + 2, values_only=True):
            if len(row) <= max_index:
                continue
            # Município é bem mais seletivo que estado: filtra primeiro e evita
            # normalizar a coluna de estado em ~40 mil linhas.
            if normalize_value(row[col_map[COL_CITY]]) != city_filter:
                continue
            if normalize_value(row[col_map[COL_STATE]]) != state_filter:
                continue

            product = normalize_value(row[col_map[COL_PRODUCT]])
            if not product:
                continue

            prices[product] = {
                "min": coerce_price(row[col_map[COL_MIN]]),
                "med": coerce_price(row[col_map[COL_MED]]),
                "max": coerce_price(row[col_map[COL_MAX]]),
            }
    finally:
        workbook.close()

    if not prices:
        raise MunicipalityNotFoundError(
            f"Nenhum registro para '{city}' / '{state}' na aba {SHEET_NAME}. "
            "Verifique a grafia do município e do estado."
        )

    _LOGGER.debug("Produtos extraídos para %s/%s: %s", city, state, sorted(prices))
    return prices
