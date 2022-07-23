# External imports
import binascii
import os
from typing import List
from dns.resolver import Resolver
from dns import resolver
import trio
from functools import partial

from exceptions import NoMXError, SMTPCatchAll, NoValidMXError

# Local imports
from logging_mod import logging
from person import Person

# from smtp_checker import _smtp_checker
from smtp_check import smtp_check

DOMAIN_STR = "gmail.com"
NAMES_FILE = "names.csv"


MOCK_MAIL = "shlomoisnotreal123123@gmail.com"
SMTP_TIMEOUT = float(10)
shlomo = "omrirefaeli@gmail.com"

logger = logging.getLogger(__name__)


async def main():

    # Check for MX records, raise error if not
    mx_records = query_mx(DOMAIN_STR)
    if not mx_records:
        logger.error(f"Domain {DOMAIN_STR} doesn't have valid MX records")
        raise NoMXError(DOMAIN_STR)

    mx_records_resolved = []
    for rec in mx_records:
        A_res = query_A(rec)
        if A_res:
            mx_records_resolved.extend(A_res)
        else:
            logger.debug(f"No DNS translation for {rec}")

    if not mx_records_resolved:
        logger.error(
            f"Domain {DOMAIN_STR} doesn't have a respective valid A record to the MX records"
        )
        raise NoValidMXError(DOMAIN_STR)

    # Check if CHECK ALL is configured on the SMTP server
    rand_email = random_email(DOMAIN_STR)
    logger.debug("Checking if SMTP servers have Check-All configured...")
    if await smtp_check(
        email_addresses=[rand_email],
        mx_records=mx_records_resolved,
        timeout=SMTP_TIMEOUT,
        from_address=MOCK_MAIL,
        final_results=set(),
        entity=Person("not", "real"),
    ):
        logger.error(
            f"Domain {DOMAIN_STR} is accepting all emails, no way of knowing what emails exist."
        )
        raise SMTPCatchAll(DOMAIN_STR)

    final_results = set()

    count = 1
    with open(NAMES_FILE, "r", encoding="utf-8") as file:

        async with trio.open_nursery() as parent_nursery:
            # Read file line by line
            while True:
                line = file.readline()

                # EOF
                if not line:
                    break
                split = line.split(",")
                if not len(split) == 2:

                    # Log wrong entries, deducting new lines
                    logging.error(
                        f"Line: {count} | Name format is not aligned '{line[:-1]}', should be 'first,last'"
                    )
                    continue

                p = Person(split[0].rstrip(), split[1].rstrip())
                logger.debug(f"Generated Person {p}.")

                parent_nursery.start_soon(
                    partial(
                        smtp_check,
                        email_addresses=[pre + "@" + DOMAIN_STR for pre in p.enum_all()],
                        mx_records=mx_records_resolved,
                        timeout=SMTP_TIMEOUT,
                        from_address=MOCK_MAIL,
                        final_results=final_results,
                        entity=p,
                    )
                )

                count += 1

        print(final_results)


def query_mx(domain: str) -> List[str]:
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
    """
    return f"{binascii.hexlify(os.urandom(30)).decode()}@{domain}"


if __name__ == "__main__":
    # with cProfile.Profile() as pr:
    trio.run(
        main,
    )
    # stats = pstats.Stats(pr)
    # stats.sort_stats(pstats.SortKey.TIME)
    # stats.dump_stats(filename="profiling.prof")
