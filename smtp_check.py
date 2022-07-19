import email
from operator import truediv
from pyparsing import Opt
from logging_mod import logging
from smtplib import SMTP, SMTPNotSupportedError, SMTPResponseException, SMTPServerDisconnected
from socket import timeout
from ssl import SSLContext, SSLError
from typing import List, Optional, Tuple, Set

from email_address import EmailAddress
from exceptions import (
    AddressNotDeliverableError,
    SMTPCommunicationError,
    SMTPMessage,
    SMTPTemporaryError,
    TLSNegotiationError,
)

import asyncio
import trio

from person import Person

logger = logging.getLogger(__name__)


class _SMTPChecker(SMTP):
    """
    A specialized variant of `smtplib.SMTP` for checking the validity of
    email addresses.

    All the commands used in the check process are modified to raise
    appropriate exceptions: `SMTPServerDisconnected` on connection
    issues and `SMTPResponseException` on negative SMTP server
    responses. Note that the methods of `smtplib.SMTP` already raise
    these exceptions on some conditions.

    Also, a new method `check` is added to run the check for a given
    list of SMTP servers.
    """

    def __init__(
        self,
        local_hostname: Optional[str],
        timeout: float,
        debug: bool,
        sender: str,
        recip: List[str],
        final_results: Set[str],
        entity: Person,
        skip_tls: bool = False,
        tls_context: Optional[SSLContext] = None,
    ):
        """
        Initialize the object with all the parameters which remain
        constant during the check of one email address on all the SMTP
        servers.
        """
        super().__init__(local_hostname=local_hostname, timeout=timeout)
        self.set_debuglevel(debuglevel=2 if debug else False)
        self.__sender = sender
        self._recips = recip
        self._true_results = set()
        self._final_results = final_results
        self.__temporary_errors = {}
        self.__skip_tls = skip_tls
        self.__tls_context = tls_context
        # Avoid error on close() after unsuccessful connect
        self.sock = None
        self.entity = entity

        # https://www.greenend.org.uk/rjk/tech/smtpreplies.html#RCPT
        self.__codes_dict = {"good": [250, 251, 552, 452, 441]}

    def putcmd(self, cmd: str, args: str = ""):
        """
        Like `smtplib.SMTP.putcmd`, but remember the command for later
        use in error messages.
        """
        if args:
            self.__command = f"{cmd} {args}"
        else:
            self.__command = cmd
        super().putcmd(cmd=cmd, args=args)

    def connect(
        self, host: str = "localhost", port: int = 0, source_address: Optional[str] = None
    ) -> Tuple[int, str]:
        """
        Like `smtplib.SMTP.connect`, but raise appropriate exceptions on
        connection failure or negative SMTP server response.
        """
        self.__command = "connect"  # Used for error messages.
        self._host = host  # Workaround: Missing in standard smtplib!
        # Use an OS assigned source port if source_address is passed
        _source_address = None if source_address is None else (source_address, 0)
        try:
            code, message = super().connect(host=host, port=port, source_address=_source_address)
        except OSError as error:
            raise SMTPServerDisconnected(str(error))
        if code >= 400:
            raise SMTPResponseException(code=code, msg=message)
        return code, message.decode()

    def starttls(self, *args, **kwargs):
        """
        Like `smtplib.SMTP.starttls`, but continue without TLS in case
        either end of the connection does not support it.
        """
        try:
            super().starttls(*args, **kwargs)
        except SMTPNotSupportedError:
            # The server does not support the STARTTLS extension
            pass
        except RuntimeError:
            # SSL/TLS support is not available to your Python interpreter
            pass
        except (SSLError, timeout) as exc:
            raise TLSNegotiationError(exc)

    def mail(self, sender: str, options: tuple = None):
        """
        Like `smtplib.SMTP.mail`, but raise an appropriate exception on
        negative SMTP server response.
        A code > 400 is an error here.
        """
        if not options:
            options = tuple()
        code, message = super().mail(sender=sender, options=options)

        if code >= 400:
            raise SMTPResponseException(code=code, msg=message)
        return code, message

    def _handle_rcpt_codes(self, code: int, msg: str) -> bool:
        if code in self.__codes_dict["good"]:

            return True
        # elif code in self.__codes_dict["blocked"]:
        #     logger.warn("Blocked by mail server")
        return False

    async def rcpt(self, recip: str, options: tuple = None):
        """
        Like `smtplib.SMTP.rcpt`, but handle negative SMTP server
        responses directly.
        """
        if not options:
            options = tuple()

        code, message = super().rcpt(recip=recip, options=options)
        if self._handle_rcpt_codes(code, message):
            logger.debug(f"Found new email~ {recip}.")
            self._true_results.add(recip)

        # if code >= 500:
        #     # Address clearly invalid: issue negative result
        #     raise AddressNotDeliverableError(
        #         {
        #             self._host: SMTPMessage(
        #                 command="RCPT TO",
        #                 code=code,
        #                 text=message.decode(errors="ignore"),
        #                 exceptions=(),
        #             )
        #         }
        #     )
        # elif code >= 400:
        #     raise SMTPResponseException(code=code, msg=message)

        # return code, message
        # self._true_results.append([code, message])

    def quit(self):
        """
        Like `smtplib.SMTP.quit`, but make sure that everything is
        cleaned up properly even if the connection has been lost before.
        """
        try:
            return super().quit()
        except SMTPServerDisconnected:
            self.ehlo_resp = self.helo_resp = None
            self.esmtp_features = {}
            self.does_esmtp = False
            self.close()

    def _handle_smtpresponseexception(self, exc: SMTPResponseException) -> bool:
        "Handle an `SMTPResponseException`."
        smtp_error = (
            exc.smtp_error.decode(errors="ignore")
            if type(exc.smtp_error) is bytes
            else exc.smtp_error
        )
        smtp_message = SMTPMessage(
            command=self.__command, code=exc.smtp_code, text=smtp_error, exceptions=(exc,)
        )
        if exc.smtp_code >= 500:
            raise SMTPCommunicationError(error_messages={self._host: smtp_message})
        else:
            self.__temporary_errors[self._host] = smtp_message
        return False

    async def _check_one(self, host: str) -> bool:
        """
        Run the check for one SMTP server.

        Return `True` on positive result.

        Return `False` on ambiguous result (4xx response to `RCPT TO`),
        while collecting the error message for later use.

        Raise `AddressNotDeliverableError`. on negative result.
        """

        try:
            self.connect(host=host)
            if not self.__skip_tls:
                self.starttls(context=self.__tls_context)
            self.ehlo_or_helo_if_needed()
            self.mail(sender=self.__sender)

            # Start async and advance only when all subtasks are done
            async with trio.open_nursery() as nursery:
                for vari in self._recips:
                    try:
                        nursery.start_soon(self.rcpt, vari)
                    except SMTPServerDisconnected:
                        logger.warn(f"Server got disconnected while trying variation - {vari}")

            # TODO: deal with over 15

            # Hard copy of the true set
            temp_true_set = self._true_results.copy()

            # Checking for email duplicates with trailing numbers
            async with trio.open_nursery() as nursery:
                for true_var in temp_true_set:
                    for i in range(1, 3):
                        email_split = true_var.split("@")
                        email_split[0] = email_split[0] + str(i)
                        if len(email_split) != 2:
                            logger.error(
                                f"Error parsing email {true_var} - enriched email with trailing nums"
                            )
                        nursery.start_soon(self.rcpt, "@".join(email_split))

            if self._true_results:
                self._final_results.update(self._true_results)

        except SMTPServerDisconnected as exc:
            self.__temporary_errors[self._host] = SMTPMessage(
                command=self.__command, code=451, text=str(exc), exceptions=(exc,)
            )
            return False
        except SMTPResponseException as exc:
            return self._handle_smtpresponseexception(exc=exc)
        except TLSNegotiationError as exc:
            self.__temporary_errors[self._host] = SMTPMessage(
                command=self.__command, code=-1, text=str(exc), exceptions=exc.args
            )
            return False
        finally:
            self.quit()
        if self._true_results:
            return True
        return False

    async def check(self, hosts: List[str]) -> bool:
        """
        Run the check for all given SMTP servers. On positive result,
        return `True`, else raise exceptions described in `smtp_check`.
        """
        for host in hosts:
            logger.debug(msg=f"Entity - {self.entity}; Trying {host} ...")

            # If a result was found, then no need to check other servers
            if await self._check_one(host=host):
                return self._true_results
        # Raise exception for collected temporary errors
        if self.__temporary_errors:
            raise SMTPTemporaryError(error_messages=self.__temporary_errors)
        return []


async def smtp_check(
    email_addresses: List[str],
    mx_records: List[str],
    from_address: str,
    final_results: Set[str],
    entity: Person,
    timeout: float = 10,
    helo_host: Optional[str] = None,
    skip_tls: bool = False,
    tls_context: Optional[SSLContext] = None,
    debug: bool = False,
) -> bool:
    """
    Returns `True` as soon as the any of the given server accepts the
    recipient address.

    Raise an `AddressNotDeliverableError` if any server unambiguously
    and permanently refuses to accept the recipient address.

    Raise `SMTPTemporaryError` if all the servers answer with a
    temporary error code during the SMTP communication. This means that
    the validity of the email address can not be determined. Greylisting
    or server delivery issues can be a cause for this.

    Raise `SMTPCommunicationError` if any SMTP server replies with an
    error message to any of the communication steps before the recipient
    address is checked, and the validity of the email address can not be
    determined either.
    """
    smtp_checker = _SMTPChecker(
        local_hostname=helo_host,
        timeout=timeout,
        debug=debug,
        sender=from_address,
        recip=email_addresses,
        final_results=final_results,
        skip_tls=skip_tls,
        tls_context=tls_context,
        entity=entity,
    )
    return await smtp_checker.check(hosts=mx_records)
