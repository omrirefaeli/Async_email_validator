import asyncio
from aiosmtplib import SMTP
from logging_mod import logging


logger = logging.getLogger(__name__)


class _smtp_checker(SMTP):
    """
    ff
    """

    def __init__(self, domain_str: str):
        self.domain_str = domain_str

    # async def smtp_c
