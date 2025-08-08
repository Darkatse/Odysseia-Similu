"""
网易云音乐会员认证模块 - 处理会员Cookie管理和认证

基于pyncm参考实现，提供网易云音乐会员认证功能，支持：
- Cookie管理和验证
- 会员状态检查
- VIP歌曲访问权限
- 高品质音频下载
- 安全的凭据处理

主要功能：
- 会员Cookie存储和管理
- 认证状态验证和缓存
- 音频质量等级选择
- 错误处理和回退机制
"""

import logging
import asyncio
import aiohttp
import json
import time
import hashlib
from typing import Dict, Optional, Tuple, Any, List
from urllib.parse import urlencode
from dataclasses import dataclass, asdict

from similubot.utils.config_manager import ConfigManager
from similubot.utils.netease_crypto import weapi_encrypt, eapi_encrypt, eapi_decrypt


@dataclass
class MemberInfo:
    """会员信息数据类"""
    user_id: int
    nickname: str
    vip_type: int  # 0: 普通用户, 1: VIP, 11: 音乐包
    is_valid: bool
    last_check: float
    
    def is_vip(self) -> bool:
        """检查是否为VIP用户"""
        return self.vip_type > 0
    
    def is_expired(self, expiry_seconds: int) -> bool:
        """检查缓存是否过期"""
        return time.time() - self.last_check > expiry_seconds


@dataclass
class AudioQuality:
    """音频质量配置"""
    level: str  # standard, higher, exhigh, lossless, hires
    bitrate: int
    format: str  # mp3, aac, flac
    
    @classmethod
    def from_level(cls, level: str, preferred_format: str = "aac") -> "AudioQuality":
        """根据质量等级创建音频质量配置"""
        quality_map = {
            "standard": (128000, "mp3"),
            "higher": (192000, "aac"),
            "exhigh": (320000, "aac"),
            "lossless": (999000, "flac"),
            "hires": (1411000, "flac")
        }
        
        bitrate, default_format = quality_map.get(level, (320000, "aac"))
        format_choice = preferred_format if level in ["standard", "higher", "exhigh"] else default_format
        
        return cls(level=level, bitrate=bitrate, format=format_choice)


class NetEaseMemberAuth:
    """
    网易云音乐会员认证管理器
    
    负责处理会员Cookie管理、认证状态验证、VIP权限检查等功能。
    基于pyncm的实现模式，提供安全可靠的会员认证服务。
    """
    
    def __init__(self, config: Optional[ConfigManager] = None):
        """
        初始化会员认证管理器
        
        Args:
            config: 配置管理器实例
        """
        self.logger = logging.getLogger("similubot.utils.netease_member")
        self.config = config or ConfigManager()
        
        # 认证状态缓存
        self._member_info: Optional[MemberInfo] = None
        self._last_validity_check = 0.0
        
        # API端点 - 基于pyncm参考实现的正确端点
        self.login_status_api = "https://music.163.com/weapi/w/nuser/account/get"
        self.track_detail_api = "https://music.163.com/weapi/v3/song/detail"
        # 使用正确的EAPI端点，不带/v1后缀
        self.track_audio_api = "https://music.163.com/eapi/song/enhance/player/url"
        
        # 会话配置
        self.timeout = aiohttp.ClientTimeout(total=15)
        
        self.logger.debug("网易云音乐会员认证管理器初始化完成")
    
    def is_enabled(self) -> bool:
        """
        检查会员认证功能是否启用
        
        Returns:
            如果启用会员认证则返回True
        """
        enabled = self.config.is_netease_member_enabled()
        if enabled:
            music_u = self.config.get_netease_member_music_u()
            if not music_u:
                self.logger.warning("会员认证已启用但未配置MUSIC_U Cookie")
                return False
        return enabled
    
    def get_member_cookies(self) -> Dict[str, str]:
        """
        获取会员认证Cookie
        
        Returns:
            Cookie字典
        """
        cookies = {}
        
        # 主要认证Cookie
        music_u = self.config.get_netease_member_music_u()
        if music_u:
            cookies["MUSIC_U"] = music_u
        
        # CSRF令牌
        csrf_token = self.config.get_netease_member_csrf_token()
        if csrf_token:
            cookies["__csrf"] = csrf_token
        
        # 记住登录状态
        cookies["__remember_me"] = "true"
        
        # 额外Cookie
        additional_cookies = self.config.get_netease_member_additional_cookies()
        cookies.update(additional_cookies)
        
        return cookies
    
    def get_member_headers(self, api_type: str = "weapi") -> Dict[str, str]:
        """
        获取会员API请求头
        
        Args:
            api_type: API类型 (weapi/eapi)
            
        Returns:
            请求头字典
        """
        if api_type == "eapi":
            return {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36 Chrome/91.0.4472.164 NeteaseMusicDesktop/2.10.2.200154",
                "Referer": "",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        else:
            return {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://music.163.com",
                "Content-Type": "application/x-www-form-urlencoded"
            }
    
    def mask_sensitive_data(self, data: str) -> str:
        """
        隐藏敏感数据用于日志记录

        Args:
            data: 原始数据

        Returns:
            隐藏敏感信息后的数据
        """
        if not self.config.should_mask_netease_member_sensitive_data():
            return data

        if len(data) <= 8:
            return "*" * len(data)

        return data[:4] + "*" * (len(data) - 8) + data[-4:]

    def validate_cookie_format(self, music_u: str) -> bool:
        """
        验证MUSIC_U Cookie格式（宽松验证）

        Args:
            music_u: MUSIC_U Cookie值

        Returns:
            如果格式有效则返回True
        """
        if not music_u or not isinstance(music_u, str):
            return False

        # 宽松的格式检查：只要不是空字符串且长度合理即可
        # MUSIC_U可能有各种格式，不应过于严格
        music_u = music_u.strip()
        if len(music_u) < 10:  # 降低最小长度要求
            return False

        # 只检查是否包含明显的无效字符（如控制字符）
        # 允许大部分可打印字符，包括特殊字符
        import re
        if re.search(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', music_u):
            return False  # 包含控制字符

        return True

    def extract_csrf_from_music_u(self, music_u: str) -> Optional[str]:
        """
        从MUSIC_U Cookie中提取或生成CSRF令牌

        Args:
            music_u: MUSIC_U Cookie值

        Returns:
            CSRF令牌，如果提取失败则返回None
        """
        if not music_u:
            return None

        try:
            # 方法1: 尝试从MUSIC_U中解码JSON数据
            import base64
            import json

            # 尝试不同的base64解码方式
            for padding in ['', '=', '==', '===']:
                try:
                    padded_music_u = music_u + padding
                    decoded = base64.b64decode(padded_music_u)

                    # 尝试UTF-8解码
                    try:
                        decoded_str = decoded.decode('utf-8')
                        user_info = json.loads(decoded_str)
                        user_id = user_info.get('userId')
                        if user_id:
                            csrf_token = hashlib.md5(str(user_id).encode()).hexdigest()
                            self.logger.debug("从MUSIC_U JSON数据中提取CSRF令牌成功")
                            return csrf_token
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        # 如果不是UTF-8或JSON，继续尝试其他方法
                        continue

                except Exception:
                    continue

            # 方法2: 如果base64解码失败，使用MUSIC_U的哈希值生成CSRF令牌
            # 这是一个回退方案，确保总能生成一个令牌
            csrf_token = hashlib.md5(music_u.encode('utf-8')).hexdigest()
            self.logger.debug("使用MUSIC_U哈希值生成CSRF令牌")
            return csrf_token

        except Exception as e:
            self.logger.debug(f"从MUSIC_U提取CSRF令牌失败: {e}")

        return None

    def get_secure_cookies(self) -> Dict[str, str]:
        """
        安全地获取会员认证Cookie，包含验证和错误处理

        Returns:
            验证后的Cookie字典
        """
        cookies = {}

        try:
            # 获取并验证MUSIC_U
            music_u = self.config.get_netease_member_music_u()
            if music_u and self.validate_cookie_format(music_u):
                cookies["MUSIC_U"] = music_u
            else:
                if music_u:
                    self.logger.warning("MUSIC_U Cookie格式无效")
                return {}

            # 获取CSRF令牌
            csrf_token = self.config.get_netease_member_csrf_token()
            if not csrf_token:
                # 尝试从MUSIC_U中提取CSRF令牌
                csrf_token = self.extract_csrf_from_music_u(music_u)

            if csrf_token:
                cookies["__csrf"] = csrf_token

            # 记住登录状态
            cookies["__remember_me"] = "true"

            # 额外Cookie
            additional_cookies = self.config.get_netease_member_additional_cookies()
            if isinstance(additional_cookies, dict):
                cookies.update(additional_cookies)

            return cookies

        except Exception as e:
            self.logger.error(f"获取安全Cookie时出错: {e}")
            return {}
    
    async def check_member_status(self, force_refresh: bool = False) -> Optional[MemberInfo]:
        """
        检查会员状态
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            会员信息，如果检查失败则返回None
        """
        if not self.is_enabled():
            return None
        
        # 检查缓存
        if not force_refresh and self._member_info:
            cache_expiry = self.config.get_netease_member_cache_expiry_time()
            if not self._member_info.is_expired(cache_expiry):
                return self._member_info
        
        try:
            cookies = self.get_secure_cookies()
            if not cookies:
                self.logger.warning("无法获取有效的会员Cookie")
                return None

            headers = self.get_member_headers("weapi")

            # 构建请求参数
            csrf_token = cookies.get("__csrf", "")
            request_params = {"csrf_token": csrf_token}

            if self.config.should_log_netease_member_authentication():
                masked_music_u = self.mask_sensitive_data(cookies.get("MUSIC_U", ""))
                self.logger.debug(f"检查会员状态，MUSIC_U: {masked_music_u}")

            # 使用WEAPI加密
            try:
                encrypted_data = weapi_encrypt(request_params)
                self.logger.debug("WEAPI加密成功")
            except Exception as e:
                self.logger.error(f"WEAPI加密失败: {e}")
                return None

            async with aiohttp.ClientSession(
                timeout=self.timeout,
                cookies=cookies
            ) as session:
                async with session.post(
                    self.login_status_api,
                    params={"csrf_token": csrf_token},
                    data=encrypted_data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        try:
                            result = await response.json()
                            self.logger.debug(f"API响应状态码: {result.get('code', 'unknown')}")

                            if result and result.get("code") == 200:
                                profile = result.get("profile")
                                account = result.get("account")

                                if not profile or not account:
                                    self.logger.warning("API响应缺少profile或account信息")
                                    return None

                                member_info = MemberInfo(
                                    user_id=account.get("id", 0),
                                    nickname=profile.get("nickname", ""),
                                    vip_type=profile.get("vipType", 0),
                                    is_valid=True,
                                    last_check=time.time()
                                )

                                self._member_info = member_info

                                if self.config.should_log_netease_member_authentication():
                                    self.logger.info(f"会员状态检查成功: {member_info.nickname} (VIP: {member_info.is_vip()})")

                                return member_info
                            else:
                                error_msg = result.get('message', '未知错误') if result else '响应为空'
                                self.logger.warning(f"会员状态检查失败: {error_msg}")

                        except json.JSONDecodeError as e:
                            self.logger.error(f"解析API响应JSON失败: {e}")
                        except Exception as e:
                            self.logger.error(f"处理API响应时出错: {e}")
                    else:
                        self.logger.warning(f"会员状态检查HTTP错误: {response.status}")
                        # 读取响应内容用于调试
                        try:
                            response_text = await response.text()
                            self.logger.debug(f"HTTP错误响应内容: {response_text[:200]}...")
                        except Exception:
                            pass
            
        except Exception as e:
            self.logger.error(f"检查会员状态时出错: {e}")
        
        # 检查失败时的处理
        if self.config.should_netease_member_auto_disable_on_invalid():
            self._member_info = None
            self.logger.warning("会员认证失效，已自动禁用会员功能")
        
        return None
    
    async def get_member_audio_url(self, song_id: str, quality_level: Optional[str] = None) -> Optional[str]:
        """
        获取会员音频下载URL
        
        Args:
            song_id: 歌曲ID
            quality_level: 音频质量等级，如果为None则使用默认配置
            
        Returns:
            音频下载URL，如果获取失败则返回None
        """
        if not self.is_enabled():
            return None
        
        # 检查会员状态
        member_info = await self.check_member_status()
        if not member_info or not member_info.is_valid:
            return None
        
        try:
            # 确定音频质量
            if quality_level is None:
                quality_level = self.config.get_netease_member_default_quality()
            
            preferred_format = self.config.get_netease_member_preferred_format()
            audio_quality = AudioQuality.from_level(quality_level, preferred_format)
            
            if self.config.should_log_netease_member_quality_selection():
                self.logger.debug(f"请求音频质量: {audio_quality.level} ({audio_quality.bitrate}bps, {audio_quality.format})")
            
            cookies = self.get_secure_cookies()
            if not cookies:
                self.logger.warning("无法获取有效的会员Cookie")
                return None

            # 添加EAPI配置作为cookies（模拟pyncm的行为）
            eapi_cookies = {
                "os": "iPhone OS",
                "appver": "10.0.0",
                "osver": "16.2",
                "channel": "distribution",
                "deviceId": "pyncm!"
            }
            cookies.update(eapi_cookies)

            headers = self.get_member_headers("eapi")

            # 构建EAPI请求参数 - 使用正确的参数格式，包含header字段
            import random
            import json

            # EAPI需要的header信息（模拟pyncm的eapi_config）
            eapi_header = {
                "os": "iPhone OS",
                "appver": "10.0.0",
                "osver": "16.2",
                "channel": "distribution",
                "deviceId": "pyncm!",
                "requestId": str(random.randrange(20000000, 30000000))
            }

            params = {
                "ids": [song_id],
                "br": str(audio_quality.bitrate),  # 使用bitrate而不是level
                "encodeType": str(audio_quality.format),
                "header": json.dumps(eapi_header)  # 关键：添加header字段
            }

            # 使用EAPI加密 - 关键修复：使用/api/路径而不是/eapi/路径
            try:
                # 根据pyncm参考实现，EAPI加密使用/api/路径，但实际请求使用/eapi/路径
                # 这是pyncm中的关键转换：url.replace("/eapi/", "/api/")
                eapi_encrypt_path = "/api/song/enhance/player/url"  # 用于加密
                encrypted_data = eapi_encrypt(eapi_encrypt_path, params)
                self.logger.debug(f"EAPI加密成功，使用路径: {eapi_encrypt_path}")
            except Exception as e:
                self.logger.error(f"EAPI加密失败: {e}")
                return None
            
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                cookies=cookies
            ) as session:
                async with session.post(
                    self.track_audio_api,
                    data=encrypted_data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        try:
                            # 获取响应内容类型和原始数据
                            content_type = response.headers.get('content-type', '')
                            raw_content = await response.read()

                            self.logger.debug(f"EAPI响应内容类型: {content_type}")
                            self.logger.debug(f"EAPI响应数据长度: {len(raw_content)} 字节")

                            # 处理EAPI加密响应（基于pyncm实现）
                            if content_type.startswith('text/plain') or not content_type.startswith('application/json'):
                                # 响应是加密的，需要解密
                                self.logger.debug("检测到EAPI加密响应，开始解密")
                                try:
                                    decrypted_text = eapi_decrypt(raw_content)
                                    self.logger.debug(f"EAPI解密成功，解密后长度: {len(decrypted_text)} 字符")

                                    # 解析解密后的JSON
                                    result = json.loads(decrypted_text)

                                except Exception as decrypt_error:
                                    self.logger.warning(f"EAPI解密失败，尝试直接解析: {decrypt_error}")
                                    # 尝试直接解析原始内容（可能是未加密的响应）
                                    try:
                                        result = json.loads(raw_content.decode('utf-8'))
                                        self.logger.debug("直接JSON解析成功，响应可能未加密")
                                    except Exception as parse_error:
                                        self.logger.error(f"所有解析方法都失败: 解密错误={decrypt_error}, 解析错误={parse_error}")
                                        # 记录原始数据用于调试
                                        self.logger.debug(f"原始响应数据（前200字节）: {raw_content[:200]}")
                                        return None
                            else:
                                # 响应是普通JSON
                                self.logger.debug("检测到普通JSON响应")
                                result = json.loads(raw_content.decode('utf-8'))

                            self.logger.debug(f"音频API响应状态码: {result.get('code', 'unknown')}")

                            if result and result.get("code") == 200:
                                data_list = result.get("data", [])
                                if data_list and len(data_list) > 0:
                                    audio_info = data_list[0]
                                    audio_url = audio_info.get("url")

                                    if audio_url:
                                        self.logger.debug(f"获取会员音频URL成功: {song_id}")
                                        return audio_url
                                    else:
                                        self.logger.warning(f"会员音频URL为空: {song_id}")
                                        # 检查是否有错误信息
                                        if audio_info.get("code") != 200:
                                            self.logger.warning(f"音频信息错误: {audio_info.get('message', '未知错误')}")
                                else:
                                    self.logger.warning(f"音频数据列表为空: {song_id}")
                            else:
                                error_msg = result.get('message', '未知错误') if result else '响应为空'
                                self.logger.warning(f"获取会员音频URL失败: {error_msg}")

                        except json.JSONDecodeError as e:
                            self.logger.error(f"解析音频API响应JSON失败: {e}")
                            # 记录原始响应内容用于调试
                            try:
                                raw_text = (await response.read()).decode('utf-8')
                                self.logger.debug(f"原始响应内容: {raw_text[:200]}...")
                            except Exception:
                                pass
                        except Exception as e:
                            self.logger.error(f"处理音频API响应时出错: {e}")
                            # 记录详细错误信息
                            import traceback
                            self.logger.debug(f"详细错误信息: {traceback.format_exc()}")
                    else:
                        self.logger.warning(f"获取会员音频URL HTTP错误: {response.status}")

                        # 特殊处理404错误
                        if response.status == 404:
                            self.logger.warning("API端点未找到，可能需要更新API地址或检查网络连接")

                        # 读取响应内容用于调试
                        try:
                            response_text = await response.text()
                            self.logger.debug(f"HTTP错误响应内容: {response_text[:200]}...")

                            # 尝试解析错误响应中的JSON信息
                            if response_text.strip().startswith('{'):
                                try:
                                    error_json = json.loads(response_text)
                                    error_msg = error_json.get('message', '未知错误')
                                    self.logger.warning(f"API错误信息: {error_msg}")
                                except json.JSONDecodeError:
                                    pass
                        except Exception:
                            pass
            
        except Exception as e:
            self.logger.error(f"获取会员音频URL时出错: {e}")
        
        return None
    
    async def is_song_available_for_member(self, song_id: str) -> bool:
        """
        检查歌曲是否对会员可用
        
        Args:
            song_id: 歌曲ID
            
        Returns:
            如果歌曲对会员可用则返回True
        """
        if not self.is_enabled():
            return False
        
        # 简单检查：尝试获取会员音频URL
        audio_url = await self.get_member_audio_url(song_id)
        return audio_url is not None
    
    def clear_cache(self):
        """清除认证缓存"""
        self._member_info = None
        self._last_validity_check = 0.0
        self.logger.debug("已清除会员认证缓存")


# 全局会员认证管理器实例
_member_auth: Optional[NetEaseMemberAuth] = None


def get_member_auth(config: Optional[ConfigManager] = None) -> NetEaseMemberAuth:
    """
    获取全局会员认证管理器实例
    
    Args:
        config: 配置管理器实例
        
    Returns:
        会员认证管理器实例
    """
    global _member_auth
    if _member_auth is None:
        _member_auth = NetEaseMemberAuth(config)
    return _member_auth
