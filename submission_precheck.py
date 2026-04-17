from src.db import run_submission_precheck
from src.config import DB_PATH


def main() -> None:
    issues = run_submission_precheck()

    print(f"Checking: {DB_PATH.name}")

    if issues:
        print("FAILED")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(1)

    print("PASSED")


if __name__ == "__main__":
    main()