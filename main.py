# External imports
import binascii
import os
from typing import List
from dns.resolver import Resolver
from dns import resolver
import trio
from functools import partial
from exceptions import NoMXError, SMTPCatchAll, NoValidMXError
import re
import pprint

# Local imports
from logging_mod import logging
from person import Person
from smtp_check import smtp_check

logger = logging.getLogger(__name__)

#
# These variables would have been supplied via a theoretical calling function or command line arguments..
#

DOMAIN_STR = "gmail.com"
NAMES_FILE = "names.csv"
PROXY_TYPE = "socks5"
PROXY_ADDR = "82.196.7.200"
PROXY_PORT = 2434
PROXY_USERNAME = "vpn"
PROXY_PASSWORD = "unlimited"


async def main(
    domain_str: str,
    names_file: str,
    smtp_timeout: float = float(20),
    mock_sender_email: str = "jim@gmail.com",
    proxy_type: str = None,
    proxy_addr: str = None,
    proxy_port: str = None,
    proxy_username: str = None,
    proxy_password: str = None,
):

    # Check for MX records, raise error if not. If the domain name is wrong, this will have no results
    mx_records = query_mx(domain_str)
    if not mx_records:
        logger.error(f"Domain {domain_str} doesn't have valid MX records")
        raise NoMXError(domain_str)

    mx_records_resolved = []
    for rec in mx_records:
        A_res = query_A(rec)
        if A_res:
            mx_records_resolved.extend(A_res)
        else:
            logger.debug(f"No DNS translation for {rec}")

    if not mx_records_resolved:
        logger.error(
            f"Domain {domain_str} doesn't have a respective valid A record to the MX records"
        )
        raise NoValidMXError(domain_str)

    # Check if CHECK ALL is configured on the SMTP server
    rand_email = random_email(domain_str)
    logger.debug("Checking if SMTP servers have Check-All configured...")
    if await smtp_check(
        email_addresses=[rand_email],
        mx_records=mx_records_resolved,
        timeout=smtp_timeout,
        from_address=mock_sender_email,
        final_results=set(),
        entity=Person("not", "real"),
    ):
        logger.error(
            f"Domain {domain_str} is accepting all emails, no way of knowing what emails exist."
        )
        raise SMTPCatchAll(domain_str)

    final_results = set()

    count = 1
    with open(names_file, "r", encoding="utf-8") as file:

        async with trio.open_nursery() as parent_nursery:
            # Read file line by line
            while True:
                line = file.readline()

                # EOF
                if not line:
                    break

                # Input name validation
                if not hasattr(re.match(r"[A-Za-z]{2,}\,[A-Za-z]{2,}\s*$", line), "group"):

                    # Log wrong entries, deducting new lines
                    logging.error(
                        f"Line: {count} | Name format is not aligned '{line[:-1]}', should be 'first,last' AND len(first/last) >= 2."
                    )
                    count += 1
                    continue

                split = line.split(",")
                p = Person(split[0].rstrip(), split[1].rstrip())
                logger.debug(f"Generated Person {p}.")

                parent_nursery.start_soon(
                    partial(
                        smtp_check,
                        email_addresses=[pre + "@" + domain_str for pre in p.enum_all()],
                        mx_records=mx_records_resolved,
                        timeout=smtp_timeout,
                        from_address=mock_sender_email,
                        final_results=final_results,
                        entity=p,
                        proxy_type=proxy_type,
                        proxy_addr=proxy_addr,
                        proxy_port=proxy_port,
                        proxy_username=proxy_username,
                        proxy_password=proxy_password,
                    )
                )
                count += 1

        print("-------\nThe final emails list is:")
        pprint.pprint(final_results)


def query_mx(domain: str) -> List[str]:
    """
    DNS Query to find MX records of the provided domain name.

    :param domain: The domain name to be queried

    :returns: List[str] of the resulted exchange servers, None if no server was found.
    """
    my_resolver = Resolver()
    my_resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
    try:
        mx_record = my_resolver.resolve(domain, "MX")
        mail_exchangers = [exchange.to_text().split()[-1] for exchange in mx_record]
        logger.debug(
            f"Queried {domain} ('MX') successfully. Resulted in {len(mail_exchangers)} records."
        )
        return mail_exchangers
    except (resolver.NoAnswer, resolver.NXDOMAIN, resolver.NoNameservers):
        logger.error(f"Error during querying DNS type MX {domain}")
        return None


def query_A(domain: str) -> List[str]:
    """
    DNS Query to find A records of the provided domain name.

    :param domain: The domain name to be queried

    :returns: List[str] of the resulted IP addresses , None if no IP address was found.
    """
    my_resolver = Resolver()
    my_resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
    final_IPs_list = set()
    try:
        results = my_resolver.resolve(domain, "A")
        logger.debug(f"Queried {domain} ('A') successfully.")
        for res in results:
            logger.debug(f"Adding the exchange server IP '{res}' to list-to-check.")
            final_IPs_list.add(res.to_text())
        return list(final_IPs_list)

    except (resolver.NoAnswer, resolver.NXDOMAIN, resolver.NoNameservers):
        logger.error(f"Error during querying DNS type A {domain}")
        return None


def random_email(domain: str) -> str:
    """
    This method generates a random email by using the os.urandom
    for the domain provided in the parameter.

    :param str domain: the suffix domain name

    :returns: a random string representing a random valid email address.

    """
    return f"{binascii.hexlify(os.urandom(30)).decode()}@{domain}"


if __name__ == "__main__":
    trio.run(
        partial(
            main,
            domain_str=DOMAIN_STR,
            names_file=NAMES_FILE,
            proxy_type=PROXY_TYPE,
            proxy_addr=PROXY_ADDR,
            proxy_port=PROXY_PORT,
            proxy_username=PROXY_USERNAME,
            proxy_password=PROXY_PASSWORD,
        )
    )
