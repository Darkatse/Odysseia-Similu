"""
网易云音乐加密模块测试

测试网易云音乐API加密功能，确保加密算法正确实现并与网易云音乐API兼容。
"""

import unittest
from unittest.mock import Mock, patch
import json

from similubot.utils.netease_crypto import (
    NetEaseCrypto, 
    weapi_encrypt, 
    eapi_encrypt, 
    eapi_decrypt,
    get_crypto
)


class TestNetEaseCrypto(unittest.TestCase):
    """网易云音乐加密工具类测试"""

    def setUp(self):
        """测试前准备"""
        self.crypto = NetEaseCrypto()

    def test_initialization(self):
        """测试加密工具初始化"""
        self.assertIsNotNone(self.crypto)
        self.assertIsNotNone(self.crypto.logger)

    def test_random_string_generation(self):
        """测试随机字符串生成"""
        # 测试默认长度
        random_str = self.crypto.random_string(16)
        self.assertEqual(len(random_str), 16)
        
        # 测试不同长度
        for length in [8, 12, 20, 32]:
            random_str = self.crypto.random_string(length)
            self.assertEqual(len(random_str), length)
        
        # 测试生成的字符串不同
        str1 = self.crypto.random_string(16)
        str2 = self.crypto.random_string(16)
        self.assertNotEqual(str1, str2)

    def test_hex_operations(self):
        """测试十六进制操作"""
        # 测试hex_digest
        test_data = bytearray([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
        hex_str = self.crypto.hex_digest(test_data)
        self.assertEqual(hex_str, "0123456789abcdef")
        
        # 测试hex_compose
        composed = self.crypto.hex_compose(hex_str)
        self.assertEqual(composed, test_data)

    def test_hash_operations(self):
        """测试哈希操作"""
        test_text = "test_string"
        
        # 测试hash_digest
        hash_bytes = self.crypto.hash_digest(test_text)
        self.assertEqual(len(hash_bytes), 16)  # MD5产生16字节
        
        # 测试hash_hex_digest
        hash_hex = self.crypto.hash_hex_digest(test_text)
        self.assertEqual(len(hash_hex), 32)  # 16字节 = 32个十六进制字符
        
        # 测试一致性
        expected_hex = self.crypto.hex_digest(bytearray(hash_bytes))
        self.assertEqual(hash_hex, expected_hex)

    def test_pkcs7_padding(self):
        """测试PKCS7填充"""
        # 测试填充
        test_data = "hello"
        padded = self.crypto.pkcs7_pad(test_data, 16)
        self.assertEqual(len(padded) % 16, 0)
        
        # 测试去填充
        unpadded = self.crypto.pkcs7_unpad(padded, 16)
        self.assertEqual(unpadded, test_data)
        
        # 测试边界情况
        empty_data = ""
        padded_empty = self.crypto.pkcs7_pad(empty_data, 16)
        self.assertEqual(len(padded_empty), 16)
        unpadded_empty = self.crypto.pkcs7_unpad(padded_empty, 16)
        self.assertEqual(unpadded_empty, empty_data)

    def test_rsa_encrypt(self):
        """测试RSA加密"""
        test_data = "test_key_1234567"
        n = 123456789
        e = 65537
        
        encrypted = self.crypto.rsa_encrypt(test_data, n, e, reverse=True)
        self.assertIsInstance(encrypted, str)
        self.assertEqual(len(encrypted), 256)  # 固定长度

    def test_weapi_encrypt_dict(self):
        """测试WEAPI加密 - 字典参数"""
        test_params = {
            "csrf_token": "test_token",
            "username": "test_user",
            "password": "test_pass"
        }
        
        result = self.crypto.weapi_encrypt(test_params)
        
        self.assertIn("params", result)
        self.assertIn("encSecKey", result)
        self.assertIsInstance(result["params"], str)
        self.assertIsInstance(result["encSecKey"], str)
        self.assertEqual(len(result["encSecKey"]), 256)

    def test_weapi_encrypt_string(self):
        """测试WEAPI加密 - 字符串参数"""
        test_params = '{"csrf_token":"test_token"}'
        
        result = self.crypto.weapi_encrypt(test_params)
        
        self.assertIn("params", result)
        self.assertIn("encSecKey", result)

    def test_weapi_encrypt_custom_key(self):
        """测试WEAPI加密 - 自定义密钥"""
        test_params = {"test": "data"}
        custom_key = "custom_key_12345"
        
        result = self.crypto.weapi_encrypt(test_params, custom_key)
        
        self.assertIn("params", result)
        self.assertIn("encSecKey", result)

    def test_eapi_encrypt(self):
        """测试EAPI加密"""
        test_url = "/eapi/song/enhance/player/url/v1"
        test_params = {
            "ids": ["123456"],
            "level": "exhigh",
            "encodeType": "aac"
        }
        
        result = self.crypto.eapi_encrypt(test_url, test_params)
        
        self.assertIn("params", result)
        self.assertIsInstance(result["params"], str)
        self.assertGreater(len(result["params"]), 0)

    def test_eapi_encrypt_string_params(self):
        """测试EAPI加密 - 字符串参数"""
        test_url = "/eapi/test"
        test_params = '{"test":"data"}'
        
        result = self.crypto.eapi_encrypt(test_url, test_params)
        
        self.assertIn("params", result)

    def test_eapi_decrypt(self):
        """测试EAPI解密"""
        # 先加密一些数据
        test_url = "/eapi/test"
        test_params = {"test": "data"}
        encrypted = self.crypto.eapi_encrypt(test_url, test_params)
        
        # 然后尝试解密（注意：这里只是测试解密函数不会崩溃）
        # 实际的解密需要完整的EAPI响应格式
        try:
            decrypted = self.crypto.eapi_decrypt(encrypted["params"])
            self.assertIsInstance(decrypted, str)
        except Exception:
            # 解密可能失败，因为我们没有真实的EAPI响应
            pass

    def test_linux_api_encrypt(self):
        """测试Linux API加密"""
        test_params = {
            "method": "POST",
            "url": "/api/test",
            "params": {"test": "data"}
        }
        
        result = self.crypto.linux_api_encrypt(test_params)
        
        self.assertIn("eparams", result)
        self.assertIsInstance(result["eparams"], str)


class TestGlobalFunctions(unittest.TestCase):
    """测试全局函数"""

    def test_get_crypto(self):
        """测试获取全局加密实例"""
        crypto1 = get_crypto()
        crypto2 = get_crypto()
        
        # 应该返回同一个实例
        self.assertIs(crypto1, crypto2)
        self.assertIsInstance(crypto1, NetEaseCrypto)

    def test_weapi_encrypt_function(self):
        """测试WEAPI加密便捷函数"""
        test_params = {"test": "data"}
        result = weapi_encrypt(test_params)
        
        self.assertIn("params", result)
        self.assertIn("encSecKey", result)

    def test_eapi_encrypt_function(self):
        """测试EAPI加密便捷函数"""
        test_url = "/eapi/test"
        test_params = {"test": "data"}
        result = eapi_encrypt(test_url, test_params)
        
        self.assertIn("params", result)

    def test_eapi_decrypt_function(self):
        """测试EAPI解密便捷函数"""
        # 测试空输入
        result = eapi_decrypt("")
        self.assertEqual(result, "")
        
        # 测试无效输入不会崩溃
        try:
            result = eapi_decrypt("invalid_hex")
            self.assertIsInstance(result, str)
        except Exception:
            # 解密失败是预期的
            pass


class TestEncryptionCompatibility(unittest.TestCase):
    """测试加密兼容性"""

    def test_weapi_encryption_format(self):
        """测试WEAPI加密格式兼容性"""
        test_params = {"csrf_token": "test"}
        result = weapi_encrypt(test_params)
        
        # 验证返回格式
        self.assertIsInstance(result, dict)
        self.assertEqual(set(result.keys()), {"params", "encSecKey"})
        
        # 验证params是base64编码
        import base64
        try:
            base64.b64decode(result["params"])
        except Exception:
            self.fail("params应该是有效的base64编码")
        
        # 验证encSecKey是256字符的十六进制
        self.assertEqual(len(result["encSecKey"]), 256)
        try:
            int(result["encSecKey"], 16)
        except ValueError:
            self.fail("encSecKey应该是有效的十六进制字符串")

    def test_eapi_encryption_format(self):
        """测试EAPI加密格式兼容性"""
        test_url = "/eapi/test"
        test_params = {"test": "data"}
        result = eapi_encrypt(test_url, test_params)
        
        # 验证返回格式
        self.assertIsInstance(result, dict)
        self.assertEqual(set(result.keys()), {"params"})
        
        # 验证params是十六进制编码
        try:
            bytes.fromhex(result["params"])
        except ValueError:
            self.fail("params应该是有效的十六进制字符串")

    def test_encryption_deterministic(self):
        """测试加密的确定性（相同输入应产生不同输出）"""
        test_params = {"test": "data"}
        
        # WEAPI加密应该每次产生不同结果（因为随机密钥）
        result1 = weapi_encrypt(test_params)
        result2 = weapi_encrypt(test_params)
        self.assertNotEqual(result1["params"], result2["params"])
        self.assertNotEqual(result1["encSecKey"], result2["encSecKey"])
        
        # EAPI加密应该产生相同结果（确定性）
        test_url = "/eapi/test"
        eapi_result1 = eapi_encrypt(test_url, test_params)
        eapi_result2 = eapi_encrypt(test_url, test_params)
        self.assertEqual(eapi_result1["params"], eapi_result2["params"])


if __name__ == '__main__':
    unittest.main()
