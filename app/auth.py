"""
Simple role-based authentication for AgenticPharma MVP.
Roles: investigator (PI) = read/write own site, sponsor = read-only all sites, admin = all
"""

USERS = {
    "investigator": {
        "password": "pi2024",
        "role": "investigator",
        "name": "Dr. Investigator (PI)",
        "site": "001",
    },
    "sponsor": {
        "password": "sponsor2024",
        "role": "sponsor",
        "name": "AstraZeneca Sponsor",
        "site": None,
    },
    "admin": {
        "password": "admin2024",
        "role": "admin",
        "name": "Study Administrator",
        "site": None,
    },
    "maruthi": {
        "password": "agentic2024",
        "role": "admin",
        "name": "Maruthi (AgenticPharma)",
        "site": None,
    },
}

ROLE_PERMISSIONS = {
    "investigator": {"can_write": True, "own_site_only": True, "can_see_checks": False},
    "sponsor":      {"can_write": False, "own_site_only": False, "can_see_checks": True},
    "admin":        {"can_write": True, "own_site_only": False, "can_see_checks": True},
}


def authenticate(username: str, password: str):
    user = USERS.get(username.lower())
    if user and user["password"] == password:
        return {
            "username": username.lower(),
            "role": user["role"],
            "name": user["name"],
            "site": user["site"],
            "permissions": ROLE_PERMISSIONS[user["role"]],
        }
    return None


def can_write(session_user: dict) -> bool:
    return session_user.get("permissions", {}).get("can_write", False)


def can_edit_subject(session_user: dict, subject_site: str) -> bool:
    perms = session_user.get("permissions", {})
    if not perms.get("can_write"):
        return False
    if perms.get("own_site_only") and session_user.get("site") != str(subject_site):
        return False
    return True
