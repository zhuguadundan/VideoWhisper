import os

from app.utils.certificate_manager import CertificateManager, create_ssl_context


def _make_cert_config(tmp_path, auto_generate=True):
    return {
        "cert_file": str(tmp_path / "cert.pem"),
        "key_file": str(tmp_path / "key.pem"),
        "domain": "example.com",
        "country": "US",
        "state": "CA",
        "organization": "Example Org",
        "auto_generate": auto_generate,
    }


def test_generate_self_signed_cert_and_get_info(tmp_path):
    cfg = _make_cert_config(tmp_path)
    cm = CertificateManager(cfg)

    assert cm.certificates_exist() is False

    ok, msg = cm.generate_self_signed_cert()
    assert ok is True
    assert cm.certificates_exist() is True

    ok, info = cm.get_certificate_info()
    assert ok is True
    assert isinstance(info, dict)
    assert info["subject"]
    assert info["issuer"]
    assert info["not_valid_before"]
    assert info["not_valid_after"]

    domains = info.get("domains", [])
    # SAN should at least contain our domain and localhost
    assert any("example.com" in d for d in domains)
    assert any("localhost" in d for d in domains)


def test_delete_certificates_and_ensure_certificates(tmp_path):
    cfg = _make_cert_config(tmp_path)
    cm = CertificateManager(cfg)
    cm.generate_self_signed_cert()
    assert cm.certificates_exist() is True

    ok, msg = cm.delete_certificates()
    assert ok is True
    assert cm.certificates_exist() is False

    # auto_generate=True should recreate certificates
    cm_auto = CertificateManager(_make_cert_config(tmp_path, auto_generate=True))
    assert cm_auto.ensure_certificates() is True
    assert cm_auto.certificates_exist() is True

    # auto_generate=False should not create certificates when missing
    cfg_no_auto = _make_cert_config(tmp_path, auto_generate=False)
    cm_no_auto = CertificateManager(cfg_no_auto)
    cm_no_auto.delete_certificates()
    assert cm_no_auto.ensure_certificates() is False
    assert cm_no_auto.certificates_exist() is False


def test_create_ssl_context_valid_and_invalid_paths(tmp_path):
    cfg = _make_cert_config(tmp_path)
    cm = CertificateManager(cfg)
    cm.generate_self_signed_cert()

    ctx = create_ssl_context(cm.cert_file, cm.key_file)
    assert ctx is not None

    bad_ctx = create_ssl_context(
        str(tmp_path / "missing_cert.pem"), str(tmp_path / "missing_key.pem")
    )
    assert bad_ctx is None
