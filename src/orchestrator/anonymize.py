import hashlib
import os


class Anonymizer_old:
    def __init__(self, salt: bytes | None = None):
        if salt is None:
            salt_env = os.environ.get("ANONYMIZATION_SALT", "")
            if not salt_env:
                raise RuntimeError("ANONYMIZATION_SALT must be set")
            salt = salt_env.encode()
        self._salt = salt

    def hash_model(self, model_version_id: str) -> str:
        return hashlib.sha256(self._salt + model_version_id.encode()).hexdigest()[:32]

#import hashlib
#import os


class Anonymizer:
    def __init__(self, salt: bytes | None = None):
        if salt is None:
            salt_env = os.environ.get("ANONYMIZATION_SALT", "")
            if not salt_env:
                raise RuntimeError("ANONYMIZATION_SALT must be set")
            salt = salt_env.encode()
        self._salt = salt
        self._forward: dict[str, str] = {}  # hash -> model_version_id

    def hash_model(self, model_version_id: str) -> str:
        h = hashlib.sha256(self._salt + model_version_id.encode()).hexdigest()[:32]
        self._forward[h] = model_version_id
        return h

    def resolve(self, model_hash: str) -> str | None:
        return self._forward.get(model_hash)
