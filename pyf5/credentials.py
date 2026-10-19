import re
import subprocess

SERVICE_PREFIX = "pyf5."


def keychain_credentials(environment: str) -> tuple[str, str, str]:
    """Return (host, username, password) for an environment from the macOS Keychain.

    Each environment is one generic password item:
      service = pyf5.<environment>, account = username, comment = host
    """
    service = f"{SERVICE_PREFIX}{environment}"

    def security(*args: str) -> str:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, *args],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            raise LookupError(
                f"No Keychain item for service '{service}'. Create it with:\n"
                f"  security add-generic-password -s {service} -a <username> -j <host> -w"
            )
        return result.stdout

    attributes = security()
    password = security("-w").rstrip("\n")

    def attribute(key: str) -> str:
        match = re.search(rf'"{key}"<blob>="(.*)"', attributes)
        if not match:
            raise LookupError(f"Keychain item '{service}' has no '{key}' attribute")
        return match.group(1)

    return attribute("icmt"), attribute("acct"), password
