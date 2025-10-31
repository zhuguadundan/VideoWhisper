"""
HTTPS证书生成和管理工具
支持自动生成自签名证书，提供HTTPS和HTTP双协议支持
"""

import os
import sys
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
    """证书管理器"""
    
    def __init__(self, config):
        # 支持两种配置方式：Config对象或配置字典
        if hasattr(config, 'CERT_FILE'):
            # 旧的Config对象方式（兼容性）
            self.cert_file = config.CERT_FILE
            self.key_file = config.KEY_FILE
            self.domain = config.CERT_DOMAIN
            self.country = config.CERT_COUNTRY
            self.state = config.CERT_STATE
            self.organization = config.CERT_ORGANIZATION
            self.auto_generate = config.CERT_AUTO_GENERATE
        else:
            # 新的配置字典方式
            self.cert_file = config.get('cert_file', 'config/cert.pem')
            self.key_file = config.get('key_file', 'config/key.pem')
            self.domain = config.get('domain', 'localhost')
            self.country = config.get('country', 'CN')
            self.state = config.get('state', 'Beijing')
            self.organization = config.get('organization', 'VideoWhisper Self-Signed')
            self.auto_generate = config.get('auto_generate', True)
        
        # 确保证书目录存在
        self.cert_dir = os.path.dirname(self.cert_file)
        if self.cert_dir:
            os.makedirs(self.cert_dir, exist_ok=True)
    
    def certificates_exist(self):
        """检查证书文件是否存在"""
        return os.path.exists(self.cert_file) and os.path.exists(self.key_file)
    
    def generate_self_signed_cert(self):
        """生成自签名SSL证书"""
        try:
            # 生成RSA私钥
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # 创建证书主体
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, self.country),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, self.state),
                x509.NameAttribute(NameOID.LOCALITY_NAME, self.state),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.organization),
                x509.NameAttribute(NameOID.COMMON_NAME, self.domain),
            ])
            
            # 创建证书
            cert = x509.CertificateBuilder()
            cert = cert.subject_name(subject)
            cert = cert.issuer_name(issuer)
            cert = cert.not_valid_before(datetime.utcnow())
            cert = cert.not_valid_after(
                datetime.utcnow() + timedelta(days=365)  # 1年有效期
            )
            cert = cert.serial_number(x509.random_serial_number())
            cert = cert.public_key(private_key.public_key())
            
            # 添加基本约束
            cert = cert.add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=False
            )
            
            # 添加密钥用途
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
                critical=True
            )
            
            # 添加扩展密钥用途
            cert = cert.add_extension(
                x509.ExtendedKeyUsage([
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                    x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                ]),
                critical=False
            )
            
            # 添加主题备用名称
            try:
                # 获取本机IP地址
                ip_addresses = []
                try:
                    local_ip = socket.gethostbyname(socket.gethostname())
                    ip_obj = ipaddress.ip_address(local_ip)
                    ip_addresses.append(x509.IPAddress(ip_obj))
                except Exception:
                    pass

                # 添加localhost IP
                try:
                    ip_addresses.append(x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")))
                except Exception:
                    pass

                san_list = [
                    x509.DNSName(self.domain),
                    x509.DNSName(f"*.{self.domain}"),
                    x509.DNSName("localhost"),
                ] + ip_addresses

                cert = cert.add_extension(
                    x509.SubjectAlternativeName(san_list),
                    critical=False
                )
            except Exception as e:
                # 如果SAN构造失败，记录告警并回退仅域名
                logging.warning(f"SAN 构造失败，回退仅域名: {e}")
                cert = cert.add_extension(
                    x509.SubjectAlternativeName([
                        x509.DNSName(self.domain),
                        x509.DNSName(f"*.{self.domain}"),
                        x509.DNSName("localhost"),
                    ]),
                    critical=False
                )
            
            # 签名证书
            cert = cert.sign(private_key, hashes.SHA256())
            
            # 保存私钥和证书
            with open(self.key_file, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            with open(self.cert_file, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            return True, "证书生成成功"
            
        except Exception as e:
            return False, f"证书生成失败: {str(e)}"
    
    def get_certificate_info(self):
        """获取证书信息"""
        try:
            if not self.certificates_exist():
                return False, "证书文件不存在"
            
            with open(self.cert_file, "r") as f:
                cert_data = f.read()
            
            cert = x509.load_pem_x509_certificate(cert_data.encode())
            
            info = {
                "subject": cert.subject.rfc4514_string(),
                "issuer": cert.issuer.rfc4514_string(),
                "version": cert.version.name,
                "serial_number": hex(cert.serial_number)[2:].upper(),
                "not_valid_before": cert.not_valid_before.isoformat(),
                "not_valid_after": cert.not_valid_after.isoformat(),
                "signature_algorithm": cert.signature_algorithm_oid._name,
                "key_size": None,  # 需要从私钥获取
                "domains": []
            }
            
            # 获取SAN中的域名
            try:
                san = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                if san:
                    san_data = san.value
                    for name in san_data:
                        if isinstance(name, x509.DNSName):
                            info["domains"].append(name.value)
                        elif isinstance(name, x509.IPAddress):
                            info["domains"].append(str(name.value))
            except:
                pass
            
            # 尝试获取密钥大小
            try:
                with open(self.key_file, "r") as f:
                    key_data = f.read()
                private_key = serialization.load_pem_private_key(key_data.encode())
                info["key_size"] = private_key.key_size
            except:
                pass
            
            return True, info
            
        except Exception as e:
            return False, f"读取证书信息失败: {str(e)}"
    
    def delete_certificates(self):
        """删除证书文件"""
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
    
    def ensure_certificates(self):
        """确保证书存在，如果配置了自动生成则创建新证书"""
        if not self.certificates_exist():
            if self.auto_generate:
                logging.info("证书不存在，自动生成自签名证书...")
                success, message = self.generate_self_signed_cert()
                if success:
                    logging.info(f"{message}")
                    logging.info(f"证书文件: {self.cert_file}")
                    logging.info(f"私钥文件: {self.key_file}")
                    return True
                else:
                    logging.error(f"{message}")
                    return False
            else:
                logging.warning("证书不存在且未配置自动生成")
                return False
        else:
            logging.info("证书文件已存在")
            return True


def create_ssl_context(cert_file, key_file):
    """创建SSL上下文"""
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # 同时加载证书和私钥
        context.load_cert_chain(cert_file, key_file)
        return context
    except Exception as e:
        logging.error(f"创建SSL上下文失败: {str(e)}")
        return None


def main():
    """主函数 - 用于命令行测试"""
    import argparse
    
    parser = argparse.ArgumentParser(description="HTTPS证书管理工具")
    parser.add_argument("--domain", default="localhost", help="证书域名")
    parser.add_argument("--cert-dir", default="config", help="证书保存目录")
    parser.add_argument("--action", choices=["generate", "info", "delete"], help="操作类型")
    parser.add_argument("--auto", action="store_true", help="自动生成")
    
    args = parser.parse_args()
    
    # 模拟配置
    class MockConfig:
        CERT_FILE = os.path.join(args.cert_dir, "cert.pem")
        KEY_FILE = os.path.join(args.cert_dir, "key.pem")
        CERT_DOMAIN = args.domain
        CERT_COUNTRY = "CN"
        CERT_STATE = "Beijing"
        CERT_ORGANIZATION = "VideoWhisper Self-Signed"
        CERT_AUTO_GENERATE = args.auto
    
    config = MockConfig()
    manager = CertificateManager(config)
    
    if args.action == "generate" or args.action is None:
        success, message = manager.generate_self_signed_cert()
        print(f"{'✅' if success else '❌'} {message}")
    
    elif args.action == "info":
        success, info = manager.get_certificate_info()
        if success:
            print("📋 证书信息:")
            print(f"   主题: {info['subject']}")
            print(f"   签发者: {info['issuer']}")
            print(f"   版本: {info['version']}")
            print(f"   序列号: {info['serial_number']}")
            print(f"   有效期: {info['not_valid_before']} 至 {info['not_valid_after']}")
            print(f"   签名算法: {info['signature_algorithm']}")
            print(f"   密钥大小: {info['key_size']} bits")
            print(f"   域名: {', '.join(info['domains'])}")
        else:
            print(f"❌ {info}")
    
    elif args.action == "delete":
        success, message = manager.delete_certificates()
        print(f"{'✅' if success else '❌'} {message}")


if __name__ == "__main__":
    main()
