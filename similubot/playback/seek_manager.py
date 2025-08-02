"""
定位管理器 - 处理音频播放位置的定位和跳转

基于原有的SeekManager实现，重构为符合新架构的模块。
支持时间格式解析和播放位置控制。
"""

import re
import logging
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

from similubot.core.interfaces import ISeekManager


class SeekResult(Enum):
    """定位结果枚举"""
    SUCCESS = "success"
    INVALID_FORMAT = "invalid_format"
    OUT_OF_RANGE = "out_of_range"
    NOT_PLAYING = "not_playing"
    ERROR = "error"


@dataclass
class SeekInfo:
    """定位信息数据类"""
    target_seconds: float
    formatted_time: str
    result: SeekResult
    message: Optional[str] = None


class SeekManager(ISeekManager):
    """
    定位管理器实现
    
    处理音频播放位置的定位和跳转功能。
    支持多种时间格式的解析和验证。
    """
    
    def __init__(self):
        """初始化定位管理器"""
        self.logger = logging.getLogger("similubot.playback.seek_manager")
        
        # 时间格式正则表达式
        self.time_patterns = {
            # 绝对时间格式: 1:30, 2:45:30
            'absolute': r'^(\d+):(\d{2})(?::(\d{2}))?$',
            # 相对时间格式: +30, -1:30
            'relative': r'^([+-])(\d+)(?::(\d{2}))?(?::(\d{2}))?$',
            # 纯秒数: 90
            'seconds': r'^(\d+)$'
        }
        
        self.logger.debug("定位管理器初始化完成")
    
    def parse_time_string(self, time_str: str) -> Tuple[bool, float, str]:
        """
        解析时间字符串
        
        Args:
            time_str: 时间字符串 (例: "1:30", "+30", "-1:00")
            
        Returns:
            (解析成功, 目标秒数, 错误消息)
        """
        time_str = time_str.strip()
        
        try:
            # 尝试绝对时间格式
            match = re.match(self.time_patterns['absolute'], time_str)
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                hours = int(match.group(3)) if match.group(3) else 0
                
                if hours > 0:
                    # 格式: H:MM:SS
                    total_seconds = hours * 3600 + minutes * 60 + seconds
                else:
                    # 格式: M:SS
                    total_seconds = minutes * 60 + seconds
                
                return True, float(total_seconds), ""
            
            # 尝试相对时间格式
            match = re.match(self.time_patterns['relative'], time_str)
            if match:
                sign = match.group(1)
                value1 = int(match.group(2))
                value2 = int(match.group(3)) if match.group(3) else 0
                value3 = int(match.group(4)) if match.group(4) else 0
                
                if match.group(4):
                    # 格式: +/-H:MM:SS
                    total_seconds = value1 * 3600 + value2 * 60 + value3
                elif match.group(3):
                    # 格式: +/-M:SS
                    total_seconds = value1 * 60 + value2
                else:
                    # 格式: +/-S
                    total_seconds = value1
                
                if sign == '-':
                    total_seconds = -total_seconds
                
                return True, float(total_seconds), ""
            
            # 尝试纯秒数格式
            match = re.match(self.time_patterns['seconds'], time_str)
            if match:
                seconds = int(match.group(1))
                return True, float(seconds), ""
            
            return False, 0.0, f"无效的时间格式: {time_str}"
            
        except ValueError as e:
            return False, 0.0, f"时间解析错误: {e}"
        except Exception as e:
            return False, 0.0, f"未知解析错误: {e}"
    
    def format_seconds(self, seconds: float) -> str:
        """
        将秒数格式化为可读时间字符串
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间字符串
        """
        try:
            total_seconds = int(seconds)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            secs = total_seconds % 60
            
            if hours > 0:
                return f"{hours}:{minutes:02d}:{secs:02d}"
            else:
                return f"{minutes}:{secs:02d}"
                
        except Exception:
            return "0:00"
    
    def validate_seek_position(self, target_seconds: float, duration: int, current_position: float = 0.0) -> Tuple[bool, str]:
        """
        验证定位位置是否有效
        
        Args:
            target_seconds: 目标位置（秒）
            duration: 音频总时长（秒）
            current_position: 当前位置（秒）
            
        Returns:
            (是否有效, 错误消息)
        """
        try:
            # 处理相对定位
            if target_seconds < 0:
                # 相对定位：从当前位置计算
                actual_target = current_position + target_seconds
            else:
                # 绝对定位
                actual_target = target_seconds
            
            # 检查范围
            if actual_target < 0:
                return False, "定位位置不能小于0"
            
            if actual_target >= duration:
                return False, f"定位位置不能超过音频时长 ({self.format_seconds(duration)})"
            
            return True, ""
            
        except Exception as e:
            return False, f"验证定位位置时发生错误: {e}"
    
    def calculate_seek_position(self, time_str: str, duration: int, current_position: float = 0.0) -> SeekInfo:
        """
        计算定位位置
        
        Args:
            time_str: 时间字符串
            duration: 音频总时长（秒）
            current_position: 当前位置（秒）
            
        Returns:
            定位信息
        """
        try:
            # 解析时间字符串
            success, target_seconds, error_msg = self.parse_time_string(time_str)
            
            if not success:
                return SeekInfo(
                    target_seconds=0.0,
                    formatted_time="0:00",
                    result=SeekResult.INVALID_FORMAT,
                    message=error_msg
                )
            
            # 处理相对定位
            if target_seconds < 0 or (time_str.startswith('+') or time_str.startswith('-')):
                if target_seconds >= 0 and time_str.startswith('+'):
                    # 正向相对定位
                    actual_target = current_position + target_seconds
                elif target_seconds < 0 or time_str.startswith('-'):
                    # 负向相对定位
                    if target_seconds >= 0:
                        target_seconds = -target_seconds
                    actual_target = current_position + target_seconds
                else:
                    actual_target = target_seconds
            else:
                # 绝对定位
                actual_target = target_seconds
            
            # 验证位置
            valid, error_msg = self.validate_seek_position(actual_target, duration, current_position)
            
            if not valid:
                return SeekInfo(
                    target_seconds=actual_target,
                    formatted_time=self.format_seconds(actual_target),
                    result=SeekResult.OUT_OF_RANGE,
                    message=error_msg
                )
            
            return SeekInfo(
                target_seconds=actual_target,
                formatted_time=self.format_seconds(actual_target),
                result=SeekResult.SUCCESS,
                message=f"定位到 {self.format_seconds(actual_target)}"
            )
            
        except Exception as e:
            return SeekInfo(
                target_seconds=0.0,
                formatted_time="0:00",
                result=SeekResult.ERROR,
                message=f"计算定位位置时发生错误: {e}"
            )
    
    async def seek_to_position(self, guild_id: int, target_seconds: float) -> Tuple[bool, Optional[str]]:
        """
        定位到指定位置（接口实现）
        
        注意：实际的定位操作需要在PlaybackEngine中实现，
        这里只提供位置计算和验证功能。
        
        Args:
            guild_id: 服务器ID
            target_seconds: 目标位置（秒）
            
        Returns:
            (成功标志, 错误消息)
        """
        # 这个方法在当前架构中主要用于接口兼容
        # 实际的定位操作应该由PlaybackEngine处理
        self.logger.debug(f"定位请求 - 服务器 {guild_id}, 目标位置: {target_seconds}s")
        return True, None
    
    def get_current_position(self, guild_id: int) -> Optional[float]:
        """
        获取当前播放位置（接口实现）
        
        注意：实际的位置获取需要在PlaybackEngine中实现。
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            当前位置（秒），如果无法获取则返回None
        """
        # 这个方法在当前架构中主要用于接口兼容
        # 实际的位置获取应该由PlaybackEngine处理
        return None
    
    def get_supported_formats(self) -> Dict[str, str]:
        """
        获取支持的时间格式
        
        Returns:
            格式说明字典
        """
        return {
            "绝对时间": "1:30 (1分30秒), 2:45:30 (2小时45分30秒)",
            "相对时间": "+30 (前进30秒), -1:30 (后退1分30秒)",
            "纯秒数": "90 (90秒)"
        }
