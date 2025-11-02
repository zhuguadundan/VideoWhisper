"""
HTTPS certificate generation and management utilities.
Supports auto-generating a self-signed certificate and dual-protocol setups.
"""

import os
import socket
import ssl
import ipaddress
import logging
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


class CertificateManager:
    """Manage TLS certificate and key files."""

    def __init__(self, config):
        # Support both Config object and plain dict
        if hasattr(config, 'CERT_FILE'):
            self.cert_file = config.CERT_FILE
            self.key_file = config.KEY_FILE
            self.domain = config.CERT_DOMAIN
            self.country = config.CERT_COUNTRY
            self.state = config.CERT_STATE
            self.organization = config.CERT_ORGANIZATION
            self.auto_generate = config.CERT_AUTO_GENERATE
        else:
            self.cert_file = config.get('cert_file', 'config/cert.pem')
            self.key_file = config.get('key_file', 'config/key.pem')
            self.domain = config.get('domain', 'localhost')
            self.country = config.get('country', 'CN')
            self.state = config.get('state', 'Beijing')
            self.organization = config.get('organization', 'VideoWhisper Self-Signed')
            self.auto_generate = config.get('auto_generate', True)

        # Ensure parent dir exists
        self.cert_dir = os.path.dirname(self.cert_file)
        if self.cert_dir:
            os.makedirs(self.cert_dir, exist_ok=True)

    def certificates_exist(self) -> bool:
        """Return True if both cert and key exist."""
        return os.path.exists(self.cert_file) and os.path.exists(self.key_file)
    def generate_self_signed_cert(self):
        """Generate a self-signed certificate matching domain/IP + localhost + local IP.
        Returns (ok: bool, message: str)
        """
        try:
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, self.country),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, self.state),
                x509.NameAttribute(NameOID.LOCALITY_NAME, self.state),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.organization),
                x509.NameAttribute(NameOID.COMMON_NAME, self.domain),
            ])

            cert = x509.CertificateBuilder()
            cert = cert.subject_name(subject)
            cert = cert.issuer_name(issuer)
            cert = cert.not_valid_before(datetime.utcnow())
            cert = cert.not_valid_after(datetime.utcnow() + timedelta(days=365))
            cert = cert.serial_number(x509.random_serial_number())
            cert = cert.public_key(private_key.public_key())

            cert = cert.add_extension(
                x509.BasicConstraints(ca=False, path_length=None), critical=False
            )

            cert = cert.add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=True,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )

            cert = cert.add_extension(
                x509.ExtendedKeyUsage([
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                    x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                ]),
                critical=False,
            )

            # Build SAN: prefer correct type (IPAddress vs DNSName)
            ip_addresses = []
            try:
                local_ip = socket.gethostbyname(socket.gethostname())
                ip_obj = ipaddress.ip_address(local_ip)
                ip_addresses.append(x509.IPAddress(ip_obj))
            except Exception:
                pass
            try:
                ip_addresses.append(x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")))
            except Exception:
                pass

            san_list = []
            try:
                # If domain is an IP literal, include as IPAddress; else as DNS
                try:
                    ip_obj = ipaddress.ip_address(self.domain)
                    san_list.append(x509.IPAddress(ip_obj))
                except ValueError:
                    san_list.append(x509.DNSName(self.domain))
                    if "." in self.domain:
                        san_list.append(x509.DNSName(f"*.{self.domain}"))
                san_list.append(x509.DNSName("localhost"))
                san_list += ip_addresses

                cert = cert.add_extension(
                    x509.SubjectAlternativeName(san_list), critical=False
                )
            except Exception as e:
                logging.warning(f"SAN build failed, fallback to domain/localhost only: {e}")
                fallback = [x509.DNSName("localhost")]
                try:
                    ip_obj = ipaddress.ip_address(self.domain)
                    fallback.insert(0, x509.IPAddress(ip_obj))
                except ValueError:
                    fallback.insert(0, x509.DNSName(self.domain))
                    if "." in self.domain:
                        fallback.insert(1, x509.DNSName(f"*.{self.domain}"))
                cert = cert.add_extension(
                    x509.SubjectAlternativeName(fallback), critical=False
                )

            cert = cert.sign(private_key, hashes.SHA256())

            with open(self.key_file, "wb") as f:
                f.write(
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.TraditionalOpenSSL,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                )

            with open(self.cert_file, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))

            return True, "证书生成成功"
        except Exception as e:
            return False, f"证书生成失败: {str(e)}"
    def get_certificate_info(self):
        """Read and return certificate info if exists."""
        try:
            if not self.certificates_exist():
                return False, "证书文件不存在"
            with open(self.cert_file, "rb") as f:
                cert = x509.load_pem_x509_certificate(f.read())
            info = {
                "subject": cert.subject.rfc4514_string(),
                "issuer": cert.issuer.rfc4514_string(),
                "version": cert.version.name,
                "serial_number": hex(cert.serial_number)[2:].upper(),
                "not_valid_before": cert.not_valid_before.isoformat(),
                "not_valid_after": cert.not_valid_after.isoformat(),
                "signature_algorithm": cert.signature_algorithm_oid._name,
                "domains": [],
            }
            try:
                san = cert.extensions.get_extension_for_oid(
                    x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                ).value
                for name in san:
                    if isinstance(name, x509.DNSName):
                        info["domains"].append(name.value)
                    elif isinstance(name, x509.IPAddress):
                        info["domains"].append(str(name.value))
            except Exception:
                pass
            return True, info
        except Exception as e:
            return False, f"读取证书信息失败: {str(e)}"

    def delete_certificates(self):
        """Delete certificate and key files if present."""
        try:
            deleted_files = []
            if os.path.exists(self.cert_file):
                os.remove(self.cert_file)
                deleted_files.append(self.cert_file)
            if os.path.exists(self.key_file):
                os.remove(self.key_file)
                deleted_files.append(self.key_file)
            return True, f"已删除 {len(deleted_files)} 个证书文件"
        except Exception as e:
            return False, f"删除证书文件失败: {str(e)}"

    def ensure_certificates(self) -> bool:
        """Ensure certificates exist; auto-generate if configured."""
        if not self.certificates_exist():
            if self.auto_generate:
                logging.info("证书不存在，自动生成自签名证书...")
                ok, msg = self.generate_self_signed_cert()
                if ok:
                    logging.info(msg)
                    logging.info(f"证书文件: {self.cert_file}")
                    logging.info(f"私钥文件: {self.key_file}")
                    return True
                logging.error(msg)
                return False
            else:
                logging.warning("证书不存在且未配置自动生成")
                return False
        logging.info("证书文件已存在")
        return True


def create_ssl_context(cert_file: str, key_file: str):
    """Create TLS context for a server socket."""
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        return context
    except Exception as e:
        logging.error(f"创建SSL上下文失败: {str(e)}")
        return None
