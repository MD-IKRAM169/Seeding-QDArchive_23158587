from src.db import init_db
from src.acquire_qdr import run_qdr
from src.acquire_cessda import run_cessda


def main():
    init_db()

    print("\n" + "=" * 70)
    print("RUNNING QDR ACQUISITION")
    print("=" * 70)
    run_qdr(limit_per_query=2)

    print("\n" + "=" * 70)
    print("RUNNING CESSDA ACQUISITION")
    print("=" * 70)
    run_cessda(max_per_query=5)


if __name__ == "__main__":
    main()