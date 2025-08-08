"""
网易云音乐API加密模块 - 基于pyncm参考实现

提供网易云音乐API请求所需的加密算法，包括：
- WEAPI加密（网页端API）
- EAPI加密（客户端API）
- AES加密/解密
- RSA加密
- 各种工具函数

基于pyncm的crypto.py实现，确保与网易云音乐API的完全兼容性。
"""

import base64
import random
import hashlib
import logging
from typing import Dict, Any, Union


# 网易云音乐API加密常量
WEAPI_RSA_PUBKEY = (
    int("00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7", 16),
    int("10001", 16)  # textbook rsa without padding
)

# AES密钥和IV
WEAPI_AES_KEY = "0CoJUm6Qyw8W8jud"  # cbc
WEAPI_AES_IV = "0102030405060708"   # cbc
LINUXAPI_AES_KEY = "rFgB&h#%2?^eDg:Q"  # ecb
EAPI_DIGEST_SALT = "nobody%(url)suse%(text)smd5forencrypt"
EAPI_DATA_SALT = "%(url)s-36cd479b6b5-%(text)s-36cd479b6b5-%(digest)s"
EAPI_AES_KEY = "e82ckenh8dichen8"  # ecb

# 字符集
BASE62 = "PJArHa0dpwhvMNYqKnTbitWfEmosQ9527ZBx46IXUgOzD81VuSFyckLRljG3eC"


class NetEaseCrypto:
    """网易云音乐加密工具类"""
    
    def __init__(self):
        self.logger = logging.getLogger("similubot.utils.netease_crypto")
    
    @staticmethod
    def random_string(length: int, chars: str = BASE62) -> str:
        """生成指定长度的随机字符串"""
        return "".join([random.choice(chars) for _ in range(length)])
    
    @staticmethod
    def hex_digest(data: bytearray) -> str:
        """将字节数组转换为十六进制字符串"""
        return "".join([hex(d)[2:].zfill(2) for d in data])
    
    @staticmethod
    def hex_compose(hexstr: str) -> bytearray:
        """将十六进制字符串转换为字节数组"""
        return bytearray([int(hexstr[i:i + 2], 16) for i in range(0, len(hexstr), 2)])
    
    @staticmethod
    def hash_digest(text: str) -> bytes:
        """计算MD5哈希"""
        return hashlib.md5(text.encode("utf-8")).digest()
    
    @staticmethod
    def hash_hex_digest(text: str) -> str:
        """计算MD5哈希并转换为十六进制字符串"""
        return NetEaseCrypto.hex_digest(bytearray(NetEaseCrypto.hash_digest(text)))
    
    @staticmethod
    def pkcs7_pad(data: str, block_size: int = 16) -> str:
        """PKCS7填充"""
        pad_len = block_size - len(data) % block_size
        return data + chr(pad_len) * pad_len
    
    @staticmethod
    def pkcs7_unpad(data: str, block_size: int = 16) -> str:
        """PKCS7去填充"""
        if not data:
            return data
        pad_len = ord(data[-1])
        if pad_len > block_size or pad_len == 0:
            return data  # 数据未填充
        return data[:-pad_len]
    
    def aes_encrypt_ecb(self, data: str, key: str) -> bytearray:
        """AES ECB模式加密（使用标准库实现）"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            
            # 填充数据
            padded_data = self.pkcs7_pad(data).encode('utf-8')
            
            # 创建AES加密器
            cipher = Cipher(
                algorithms.AES(key.encode('utf-8')),
                modes.ECB(),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # 加密
            encrypted = encryptor.update(padded_data) + encryptor.finalize()
            return bytearray(encrypted)
            
        except ImportError:
            self.logger.error("cryptography库未安装，无法进行AES加密")
            raise ImportError("需要安装cryptography库: pip install cryptography")
    
    def aes_encrypt_cbc(self, data: str, key: str, iv: str) -> bytearray:
        """AES CBC模式加密"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            
            # 填充数据
            padded_data = self.pkcs7_pad(data).encode('utf-8')
            
            # 创建AES加密器
            cipher = Cipher(
                algorithms.AES(key.encode('utf-8')),
                modes.CBC(iv.encode('utf-8')),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # 加密
            encrypted = encryptor.update(padded_data) + encryptor.finalize()
            return bytearray(encrypted)
            
        except ImportError:
            self.logger.error("cryptography库未安装，无法进行AES加密")
            raise ImportError("需要安装cryptography库: pip install cryptography")
    
    def aes_decrypt_ecb(self, data: bytes, key: str) -> str:
        """AES ECB模式解密"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            
            # 创建AES解密器
            cipher = Cipher(
                algorithms.AES(key.encode('utf-8')),
                modes.ECB(),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # 解密
            decrypted = decryptor.update(data) + decryptor.finalize()
            
            # 去填充
            return self.pkcs7_unpad(decrypted.decode('utf-8'))
            
        except ImportError:
            self.logger.error("cryptography库未安装，无法进行AES解密")
            raise ImportError("需要安装cryptography库: pip install cryptography")
    
    def rsa_encrypt(self, data: str, n: int, e: int, reverse: bool = True) -> str:
        """RSA加密"""
        m = data if not reverse else data[::-1]
        m_int = int(''.join(m).encode('utf-8').hex(), 16)
        r = pow(m_int, e, n)
        return hex(r)[2:].zfill(256)
    
    def weapi_encrypt(self, params: Union[str, Dict[str, Any]], aes_key2: str = None) -> Dict[str, str]:
        """
        WEAPI加密 - 用于网页端API请求
        
        Args:
            params: 要加密的参数（字符串或字典）
            aes_key2: 第二个AES密钥，如果为None则随机生成
            
        Returns:
            包含加密参数的字典
        """
        if aes_key2 is None:
            aes_key2 = self.random_string(16)
        
        # 转换参数为字符串
        if isinstance(params, dict):
            import json
            params_str = json.dumps(params, separators=(',', ':'), ensure_ascii=False)
        else:
            params_str = str(params)
        
        try:
            # 第一次AES加密
            first_encrypted = self.aes_encrypt_cbc(params_str, WEAPI_AES_KEY, WEAPI_AES_IV)
            first_b64 = base64.b64encode(first_encrypted).decode('utf-8')
            
            # 第二次AES加密
            second_encrypted = self.aes_encrypt_cbc(first_b64, aes_key2, WEAPI_AES_IV)
            second_b64 = base64.b64encode(second_encrypted).decode('utf-8')
            
            # RSA加密第二个密钥
            enc_sec_key = self.rsa_encrypt(aes_key2, *WEAPI_RSA_PUBKEY)
            
            return {
                'params': second_b64,
                'encSecKey': enc_sec_key
            }
            
        except Exception as e:
            self.logger.error(f"WEAPI加密失败: {e}")
            raise
    
    def eapi_encrypt(self, url: str, params: Union[str, Dict[str, Any]]) -> Dict[str, str]:
        """
        EAPI加密 - 用于客户端API请求
        
        Args:
            url: API URL
            params: 要加密的参数
            
        Returns:
            包含加密参数的字典
        """
        # 转换参数为字符串
        if isinstance(params, dict):
            import json
            params_str = json.dumps(params, separators=(',', ':'), ensure_ascii=False)
        else:
            params_str = str(params)
        
        try:
            # 计算摘要
            digest = self.hash_hex_digest(EAPI_DIGEST_SALT % {'url': url, 'text': params_str})
            
            # 构建数据
            data = EAPI_DATA_SALT % {'url': url, 'text': params_str, 'digest': digest}
            
            # AES加密
            encrypted = self.aes_encrypt_ecb(data, EAPI_AES_KEY)
            
            return {
                'params': self.hex_digest(encrypted)
            }
            
        except Exception as e:
            self.logger.error(f"EAPI加密失败: {e}")
            raise
    
    def eapi_decrypt(self, cipher: Union[str, bytes]) -> str:
        """
        EAPI解密 - 解密EAPI响应（基于pyncm实现）

        Args:
            cipher: 加密的响应数据

        Returns:
            解密后的字符串
        """
        if not cipher:
            return ""

        try:
            # 转换为bytearray（模拟pyncm的处理方式）
            if isinstance(cipher, str):
                # 如果是十六进制字符串，转换为字节
                try:
                    cipher_bytes = self.hex_compose(cipher)
                except Exception:
                    # 如果不是十六进制，直接编码
                    cipher_bytes = cipher.encode('utf-8')
            else:
                cipher_bytes = bytearray(cipher) if not isinstance(cipher, bytearray) else cipher

            # 检查数据长度是否为AES块大小的倍数
            block_size = 16  # AES块大小
            if len(cipher_bytes) % block_size != 0:
                self.logger.debug(f"EAPI数据长度 {len(cipher_bytes)} 不是块大小 {block_size} 的倍数")

                # 尝试填充到块大小的倍数（如果数据太短）
                if len(cipher_bytes) < block_size:
                    self.logger.debug("数据太短，尝试填充")
                    padding_needed = block_size - (len(cipher_bytes) % block_size)
                    cipher_bytes.extend(b'\x00' * padding_needed)
                else:
                    # 如果数据长度不对，可能不是标准的EAPI加密数据
                    self.logger.debug("数据长度不符合AES块要求，可能不是EAPI加密数据")
                    # 尝试截断到最近的块边界
                    truncate_length = (len(cipher_bytes) // block_size) * block_size
                    if truncate_length > 0:
                        cipher_bytes = cipher_bytes[:truncate_length]
                    else:
                        raise ValueError("数据长度不足一个AES块")

            return self.aes_decrypt_ecb(bytes(cipher_bytes), EAPI_AES_KEY)

        except Exception as e:
            self.logger.error(f"EAPI解密失败: {e}")
            raise
    
    def linux_api_encrypt(self, params: Union[str, Dict[str, Any]]) -> Dict[str, str]:
        """
        Linux API加密 - 用于Linux客户端API请求
        
        Args:
            params: 要加密的参数
            
        Returns:
            包含加密参数的字典
        """
        # 转换参数为字符串
        if isinstance(params, dict):
            import json
            params_str = json.dumps(params, separators=(',', ':'), ensure_ascii=False)
        else:
            params_str = str(params)
        
        try:
            # AES加密
            encrypted = self.aes_encrypt_ecb(params_str, LINUXAPI_AES_KEY)
            
            return {
                'eparams': self.hex_digest(encrypted)
            }
            
        except Exception as e:
            self.logger.error(f"Linux API加密失败: {e}")
            raise


# 全局加密实例
_crypto_instance = None


def get_crypto() -> NetEaseCrypto:
    """获取全局加密实例"""
    global _crypto_instance
    if _crypto_instance is None:
        _crypto_instance = NetEaseCrypto()
    return _crypto_instance


# 便捷函数
def weapi_encrypt(params: Union[str, Dict[str, Any]], aes_key2: str = None) -> Dict[str, str]:
    """WEAPI加密便捷函数"""
    return get_crypto().weapi_encrypt(params, aes_key2)


def eapi_encrypt(url: str, params: Union[str, Dict[str, Any]]) -> Dict[str, str]:
    """EAPI加密便捷函数"""
    return get_crypto().eapi_encrypt(url, params)


def eapi_decrypt(cipher: Union[str, bytes]) -> str:
    """EAPI解密便捷函数"""
    return get_crypto().eapi_decrypt(cipher)
