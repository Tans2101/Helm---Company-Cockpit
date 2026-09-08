"""Mongo mock helpers for unit tests."""
from unittest.mock import MagicMock


def attach_users_in_find(users):
    """Route users.find($in) through users.find_one so batch lookups work on mocks."""
    def find(query, projection=None):
        raw = (query or {}).get("user_id")
        if isinstance(raw, dict) and "$in" in raw:
            ids = list(raw.get("$in") or [])
        elif raw:
            ids = [raw]
        else:
            ids = []
        cursor = MagicMock()

        async def to_list(_n=None):
            out = []
            for uid in ids:
                u = await users.find_one({"user_id": uid}, projection)
                if u:
                    doc = dict(u)
                    doc.setdefault("user_id", uid)
                    out.append(doc)
            return out

        cursor.to_list = to_list
        return cursor

    users.find = find
    return users
