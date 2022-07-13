# External imports
from ast import Raise
from typing import List
from dns import resolver

# Local imports
from logging_mod import logging
from person import Person
from smtp_checker import _smtp_checker

DOMAIN_STR = "gmail.com"
NAMES_FILE = "names.csv"


MOCK_MAIL = "shlomoisnotreal123123@gmail.com"

logger = logging.getLogger(__name__)

# TODO: validate arguments
def main():

    # Check for MX records, raise error if not
    mx_records = query_mx(DOMAIN_STR)
    if not mx_records:
        logger.error(f"Domain {DOMAIN_STR} doesn't have valid MX records")
        # TODO: add error
        raise Exception(f"Domain {DOMAIN_STR} doesn't have valid MX records")

    mx_records_resolved = []
    for rec in mx_records:
        mx_records_resolved.extend(query_A(rec))

    if not mx_records_resolved:
        logger.error(f"Domain {DOMAIN_STR} doesn't have valid A records for MX servers")
        # TODO: add error
        raise Exception(f"Domain {DOMAIN_STR} doesn't have valid A records for MX servers")

    # client = _smtp_checker(DOMAIN_STR)

    count = 1
    with open(NAMES_FILE, "r") as file:

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

            p = Person(split[0], split[1])
            print(p.test())

            count += 1


# TODO: add if CHECK_ALL
def query_mx(domain: str) -> List[str]:
    try:
        mx_record = resolver.query(domain, "MX")
        mail_exchangers = [exchange.to_text().split()[-1] for exchange in mx_record]
        return mail_exchangers
    except (resolver.NoAnswer, resolver.NXDOMAIN, resolver.NoNameservers):
        return None


def query_A(domain: str) -> List[str]:
    final_IPs_list = []
    try:
        results = resolver.query(domain, "A")
        for res in results:
            final_IPs_list.append(res.to_text())
        return final_IPs_list
    # TODO: add exceptions
    except Exception as e:
        return None


if __name__ == "__main__":
    main()
