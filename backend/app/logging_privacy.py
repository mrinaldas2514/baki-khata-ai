"""Keep shopkeepers' data out of the logs.

The rule for the whole backend: logs carry ids (user, shop, customer, transaction), never a
sentence, a name, a phone number or an amount. The one place such text could slip in on its
own is uvicorn's access log, which prints each request's URL; query strings (for example
`?search=rahim`) are cut off here.
"""

import logging


class DropQueryString(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        # uvicorn.access: (client_addr, method, full_path, http_version, status_code)
        if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str):
            record.args = (args[0], args[1], args[2].split("?", 1)[0], args[3], args[4])
        return True


def install_access_log_filter() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, DropQueryString) for f in access.filters):
        access.addFilter(DropQueryString())
