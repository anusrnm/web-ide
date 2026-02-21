import getpass
import sys
from werkzeug.security import generate_password_hash


def main():
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Enter password to hash: ").strip()

    if not password:
        print("Error: password cannot be empty.", file=sys.stderr)
        raise SystemExit(1)

    print(generate_password_hash(password))


if __name__ == "__main__":
    main()
