#!/usr/bin/env python3
"""
测试脚本：验证 Bilibili 多P视频的时长验证修复

这个脚本演示了修复后的 BilibiliProvider 如何正确处理多P视频的时长验证。
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from similubot.provider.bilibili_provider import BilibiliProvider
    BILIBILI_AVAILABLE = True
except ImportError as e:
    print(f"Bilibili 提供者不可用: {e}")
    BILIBILI_AVAILABLE = False


async def test_bilibili_page_extraction():
    """测试 Bilibili 页面索引提取功能"""
    if not BILIBILI_AVAILABLE:
        print("跳过测试：Bilibili 提供者不可用")
        return
    
    provider = BilibiliProvider("./temp")
    
    # 测试用例
    test_cases = [
        {
            "url": "https://www.bilibili.com/video/BV1LDTEz2ErB",
            "expected_page": 0,
            "description": "普通视频（无p参数）"
        },
        {
            "url": "https://www.bilibili.com/video/BV1LDTEz2ErB?p=1",
            "expected_page": 0,
            "description": "第一页（p=1）"
        },
        {
            "url": "https://www.bilibili.com/video/BV1LDTEz2ErB?p=26",
            "expected_page": 25,
            "description": "第26页（p=26）"
        },
        {
            "url": "https://www.bilibili.com/video/BV1LDTEz2ErB?vd_source=ec9afe1d3d2b9c3d6f4fc7af22a32b4a&spm_id_from=333.788.videopod.episodes&p=26",
            "expected_page": 25,
            "description": "复杂URL，第26页"
        }
    ]
    
    print("=== 测试页面索引提取 ===")
    for i, case in enumerate(test_cases, 1):
        page_index = provider._extract_page_index(case["url"])
        status = "✓" if page_index == case["expected_page"] else "✗"
        print(f"{i}. {case['description']}: {status}")
        print(f"   URL: {case['url']}")
        print(f"   期望页面索引: {case['expected_page']}, 实际: {page_index}")
        print()


async def test_video_id_extraction():
    """测试视频ID提取功能"""
    if not BILIBILI_AVAILABLE:
        print("跳过测试：Bilibili 提供者不可用")
        return
    
    provider = BilibiliProvider("./temp")
    
    test_cases = [
        {
            "url": "https://www.bilibili.com/video/BV1LDTEz2ErB",
            "expected_id": "BV1LDTEz2ErB",
            "description": "标准BV号"
        },
        {
            "url": "https://www.bilibili.com/video/BV1LDTEz2ErB?p=26&vd_source=abc",
            "expected_id": "BV1LDTEz2ErB",
            "description": "带参数的BV号"
        }
    ]
    
    print("=== 测试视频ID提取 ===")
    for i, case in enumerate(test_cases, 1):
        video_id = provider._extract_video_id(case["url"])
        status = "✓" if video_id == case["expected_id"] else "✗"
        print(f"{i}. {case['description']}: {status}")
        print(f"   URL: {case['url']}")
        print(f"   期望视频ID: {case['expected_id']}, 实际: {video_id}")
        print()


def test_url_support():
    """测试URL支持检测"""
    if not BILIBILI_AVAILABLE:
        print("跳过测试：Bilibili 提供者不可用")
        return
    
    provider = BilibiliProvider("./temp")
    
    test_cases = [
        {
            "url": "https://www.bilibili.com/video/BV1LDTEz2ErB",
            "expected": True,
            "description": "标准Bilibili URL"
        },
        {
            "url": "https://www.bilibili.com/video/BV1LDTEz2ErB?p=26",
            "expected": True,
            "description": "带p参数的Bilibili URL"
        },
        {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "expected": False,
            "description": "YouTube URL（不支持）"
        }
    ]
    
    print("=== 测试URL支持检测 ===")
    for i, case in enumerate(test_cases, 1):
        is_supported = provider.is_supported_url(case["url"])
        status = "✓" if is_supported == case["expected"] else "✗"
        print(f"{i}. {case['description']}: {status}")
        print(f"   URL: {case['url']}")
        print(f"   期望支持: {case['expected']}, 实际: {is_supported}")
        print()


async def main():
    """主函数"""
    print("Bilibili 多P视频修复测试")
    print("=" * 50)
    print()
    
    # 运行测试
    test_url_support()
    await test_video_id_extraction()
    await test_bilibili_page_extraction()
    
    print("=== 修复说明 ===")
    print("1. 新增 _extract_page_index() 方法，从URL中提取&p=参数")
    print("2. 修改 _extract_audio_info_impl() 方法，获取指定页面的时长信息")
    print("3. 修改 _download_audio_impl() 方法，下载指定页面的音频")
    print("4. 对于多P视频，标题会包含分P信息（如：主标题 - P2: 分P标题）")
    print("5. 时长验证现在使用单个分P的时长，而不是整个合集的时长")
    print()
    print("这样，即使整个合集超过时长限制，单个分P在限制内的视频也能正常播放。")


if __name__ == "__main__":
    asyncio.run(main())
