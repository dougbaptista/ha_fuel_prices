"""Coordinator que busca e compartilha os dados da ANP entre os sensores."""

from __future__ import annotations

import logging
from datetime import datetime

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    CONF_CITY,
    CONF_STATE,
    DEFAULT_CITY,
    DEFAULT_STATE,
    DOMAIN,
    DOWNLOAD_CHUNK_SIZE,
    DOWNLOAD_TIMEOUT,
    MAX_DOWNLOAD_BYTES,
    PAGE_TIMEOUT,
    UPDATE_INTERVAL,
)
from .parser import (
    FuelPricesError,
    MunicipalityNotFoundError,
    SourceUnavailableError,
    find_xls_url,
    parse_workbook,
)

_LOGGER = logging.getLogger(__name__)


def entry_config(entry: ConfigEntry) -> dict:
    """Configuração efetiva: opções sobrescrevem os dados iniciais."""
    return {**entry.data, **entry.options}


class FuelPriceCoordinator(DataUpdateCoordinator[dict]):
    """Busca os dados da ANP uma vez por ciclo e compartilha com os sensores."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self.last_successful_update: datetime | None = None

    @property
    def state_name(self) -> str:
        """Estado configurado."""
        return entry_config(self.entry).get(CONF_STATE, DEFAULT_STATE)

    @property
    def city_name(self) -> str:
        """Município configurado."""
        return entry_config(self.entry).get(CONF_CITY, DEFAULT_CITY)

    async def _async_update_data(self) -> dict:
        """Coleta os preços, traduzindo cada falha em uma mensagem específica."""
        try:
            xls_url = await self._async_find_xls_url()
            content = await self._async_download(xls_url)
            # load_workbook + varredura de ~40 mil linhas é trabalho de CPU:
            # roda em executor para não bloquear o event loop do HA.
            prices = await self.hass.async_add_executor_job(
                parse_workbook, content, self.state_name, self.city_name
            )
            self.last_successful_update = dt_util.utcnow()
            return prices
        except MunicipalityNotFoundError as err:
            raise UpdateFailed(str(err)) from err
        except SourceUnavailableError as err:
            raise UpdateFailed(f"Dados da ANP indisponíveis: {err}") from err
        except FuelPricesError as err:
            raise UpdateFailed(str(err)) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Erro de rede ao acessar a ANP: {err}") from err
        except TimeoutError as err:
            raise UpdateFailed("Tempo esgotado ao acessar a ANP.") from err
        except Exception as err:  # noqa: BLE001 - rede/planilha externa
            _LOGGER.exception("Falha inesperada ao atualizar os dados da ANP")
            raise UpdateFailed(f"Falha inesperada: {err}") from err

    async def _async_find_xls_url(self) -> str:
        """Baixa a página da ANP e resolve a URL da planilha mais recente."""
        session = async_get_clientsession(self.hass)
        timeout = aiohttp.ClientTimeout(total=PAGE_TIMEOUT)
        async with session.get(BASE_URL, timeout=timeout) as response:
            if response.status != 200:
                raise SourceUnavailableError(
                    f"A página da ANP respondeu HTTP {response.status}."
                )
            html = await response.text()

        # BeautifulSoup sobre uma página grande também é trabalho de CPU.
        return await self.hass.async_add_executor_job(find_xls_url, html, BASE_URL)

    async def _async_download(self, url: str) -> bytes:
        """Baixa a planilha respeitando um teto rígido de tamanho."""
        session = async_get_clientsession(self.hass)
        timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
        async with session.get(url, timeout=timeout) as response:
            if response.status != 200:
                raise SourceUnavailableError(
                    f"Download da planilha respondeu HTTP {response.status}."
                )

            declared = response.content_length
            if declared is not None and declared > MAX_DOWNLOAD_BYTES:
                raise SourceUnavailableError(
                    f"Planilha anunciada com {declared} bytes, acima do limite "
                    f"de {MAX_DOWNLOAD_BYTES}."
                )

            buffer = bytearray()
            async for chunk in response.content.iter_chunked(DOWNLOAD_CHUNK_SIZE):
                buffer.extend(chunk)
                if len(buffer) > MAX_DOWNLOAD_BYTES:
                    raise SourceUnavailableError(
                        "Download interrompido: planilha excedeu o limite de "
                        f"{MAX_DOWNLOAD_BYTES} bytes."
                    )

        _LOGGER.debug("Planilha baixada: %s (%d bytes)", url, len(buffer))
        return bytes(buffer)
