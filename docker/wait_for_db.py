import os
import sys
import time

import psycopg
from dotenv import load_dotenv


def main():
    load_dotenv()
    attempts = int(os.getenv("DB_WAIT_ATTEMPTS", "30"))
    connection_options = {
        "dbname": os.getenv("POSTGRES_DB", "tradeflow_oms"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "connect_timeout": 3,
    }

    for attempt in range(1, attempts + 1):
        try:
            with psycopg.connect(**connection_options):
                print("PostgreSQL is ready.")
                return
        except psycopg.OperationalError as error:
            if attempt == attempts:
                print(
                    f"PostgreSQL did not become ready after {attempts} attempts: {error}",
                    file=sys.stderr,
                )
                raise SystemExit(1) from error

            print(f"Waiting for PostgreSQL ({attempt}/{attempts})...")
            time.sleep(1)


if __name__ == "__main__":
    main()
