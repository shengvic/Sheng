import os
import uuid

import pytest
from cryptography.exceptions import InvalidTag
from travo_api import crypto
from travo_api.config import get_settings
from travo_api.db import tenant_session
from travo_api.keys import load_credential, store_credential
from travo_api.storage import LocalEncryptedStore

from tests.conftest import create_matter, upload


def test_documents_encrypted_at_rest(client, make_tenant):
    t = make_tenant()
    matter = create_matter(client, t)
    assert upload(client, t, matter["id"]).status_code == 201
    tenant_dir = get_settings().storage_dir / t.tenant_id
    files = list(tenant_dir.iterdir())
    assert files
    raw = files[0].read_bytes()
    assert not raw.startswith(b"PK")  # DOCX magic must not be visible
    assert b"Lion City" not in raw


def test_tenant_keys_are_distinct_and_bound(tmp_path):
    kms = crypto.LocalKms(__import__("base64").b64encode(os.urandom(32)).decode())
    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())
    dek = crypto.new_dek()
    wrapped = kms.wrap(t1, dek)
    assert kms.unwrap(t1, wrapped) == dek
    with pytest.raises(InvalidTag):
        kms.unwrap(t2, wrapped)  # wrapped key is bound to its tenant

    store = LocalEncryptedStore(tmp_path)
    ref = store.put(t1, dek, b"secret contract")
    assert store.get(t1, dek, ref) == b"secret contract"
    with pytest.raises(InvalidTag):
        store.get(t1, crypto.new_dek(), ref)
    with pytest.raises(ValueError):
        store.get(t1, dek, "../../etc/passwd")


def test_byo_credentials_encrypted_and_never_returned(client, make_tenant):
    t = make_tenant()
    r = client.post(
        "/v1/admin/provider-credentials",
        json={"provider": "anthropic", "api_key": "sk-test-SECRET-1234"},
        headers=t.headers(),
    )
    assert r.status_code == 201
    assert r.json() == {"provider": "anthropic", "last4": "1234", "status": "active"}
    listed = client.get("/v1/admin/provider-credentials", headers=t.headers()).text
    assert "SECRET" not in listed
    with tenant_session(t.tenant_id) as s:
        assert load_credential(s, t.tenant_id, "anthropic") == "sk-test-SECRET-1234"
        store_credential(s, t.tenant_id, "anthropic", "sk-rotated-9999")
    with tenant_session(t.tenant_id) as s:
        assert load_credential(s, t.tenant_id, "anthropic") == "sk-rotated-9999"
