# NetEase URL刷新功能实现文档

## 问题描述

NetEase Cloud Music的直接下载URL具有时效性，通常在几小时后会过期。当歌曲在队列中等待播放时，原本有效的下载链接可能会过期，导致下载时出现403 "auth failed - expired url"错误，进而导致歌曲被跳过。

## 解决方案概述

实现了一套完整的URL刷新机制，当检测到URL过期时，自动使用歌曲ID重新生成新的下载链接并重试下载。

## 核心实现

### 1. 过期URL检测

在`_download_file_with_retry`方法中添加了403错误检测逻辑：

```python
if response.status == 403:
    # 检查是否是URL过期错误
    auth_msg = response.headers.get('X-AUTH-MSG', '').lower()
    if 'expired url' in auth_msg or 'auth failed' in auth_msg:
        self.logger.warning(f"检测到URL过期错误: {auth_msg}")
        
        # 如果还有重试机会，尝试刷新URL
        if retry_count < max_retries:
            fresh_url = await self._refresh_expired_url(url)
            if fresh_url and fresh_url != url:
                self.logger.info(f"URL刷新成功，重试下载 (第{retry_count + 1}次)")
                return await self._download_file_with_retry(
                    fresh_url, file_path, progress_tracker, retry_count + 1
                )
```

### 2. URL刷新策略

`_refresh_expired_url`方法实现了多层次的URL刷新策略：

#### 2.1 歌曲ID提取
- 优先从缓存中获取URL到歌曲ID的映射
- 从API URL中提取歌曲ID（如`https://api.paugram.com/netease/?id=123456`）
- 对于直接音频URL，依赖缓存映射（通常无法直接提取ID）

#### 2.2 URL生成策略
1. **会员认证模式**（如果启用）：使用`member_auth.get_member_audio_url()`获取高品质会员链接
2. **API模式**：使用`get_playback_url(song_id, use_api=True)`生成API代理链接
3. **直接模式**：使用`get_playback_url(song_id, use_api=False)`生成直接链接

### 3. 重试机制

- 最大重试次数：1次（总共尝试2次）
- 重试条件：检测到403过期错误且URL刷新成功
- 防止无限循环：如果刷新后的URL与原URL相同，视为刷新失败

### 4. 缓存机制优化

利用现有的URL到歌曲ID缓存映射：
- 在获取会员音频URL时自动缓存映射
- 在URL刷新时更新缓存映射
- 缓存键使用URL的主要部分（去除时效性参数）

## 代码变更详情

### 主要新增方法

1. **`_download_file_with_retry`**: 支持重试的下载方法
2. **`_refresh_expired_url`**: URL刷新核心逻辑
3. **`_extract_song_id_from_direct_url`**: 从直接音频URL提取歌曲ID（通常返回None）

### 修改的方法

1. **`_download_file`**: 重构为调用`_download_file_with_retry`的包装方法

## 错误处理

### 1. 过期URL检测
- 检查HTTP状态码403
- 验证响应头中的`X-AUTH-MSG`字段
- 支持多种错误消息格式：`expired url`、`auth failed`

### 2. 刷新失败处理
- 无法提取歌曲ID时记录警告并返回None
- 所有刷新策略失败时记录错误
- 达到最大重试次数时停止重试

### 3. 异常处理
- 所有关键方法都包含try-catch块
- 详细的错误日志记录
- 优雅的降级处理

## 日志记录

### 调试日志
- URL刷新开始和结果
- 歌曲ID提取过程
- 各种刷新策略的尝试结果

### 信息日志
- URL刷新成功通知
- 重试下载通知

### 警告日志
- URL过期检测
- 刷新失败通知
- 无法提取歌曲ID

### 错误日志
- 达到最大重试次数
- 异常情况

## 测试覆盖

### 单元测试
1. **过期URL检测测试**: 验证403错误和过期消息检测
2. **缓存歌曲ID刷新测试**: 验证使用缓存ID的URL刷新
3. **API URL刷新测试**: 验证从API URL提取ID并刷新
4. **会员认证刷新测试**: 验证会员模式的URL刷新
5. **回退模式测试**: 验证API模式失败后的直接模式回退
6. **重试机制测试**: 验证下载重试逻辑
7. **最大重试限制测试**: 验证重试次数限制

### 集成测试
- 完整的下载流程测试，包含URL刷新

## 性能影响

### 正常情况
- 无性能影响：URL未过期时不触发刷新逻辑
- 缓存命中：歌曲ID提取速度快

### 过期情况
- 轻微延迟：需要重新生成URL并重试下载
- 网络开销：会员模式可能需要额外API调用

## 兼容性

### 向后兼容
- 保持所有现有API不变
- 现有错误处理逻辑继续工作
- 不影响其他提供者的功能

### 配置兼容
- 自动适配现有的代理配置
- 兼容会员认证设置
- 支持所有现有的URL生成模式

## 使用示例

### 正常流程
```python
# 歌曲添加到队列时
audio_info = await provider._extract_audio_info_impl(url)
# audio_info.url 包含初始下载链接

# 歌曲播放时（可能几小时后）
success, audio_info, error = await provider._download_audio_impl(url)
# 如果URL过期，自动刷新并重试
```

### 日志输出示例
```
DEBUG - 开始下载NetEase音频: http://m701.music.126.net/expired/test.mp3
WARNING - 检测到URL过期错误: auth failed - expired url
DEBUG - 开始刷新过期URL: http://m701.music.126.net/expired/test.mp3
DEBUG - 从缓存获取歌曲ID: m701.music.126.net/expired/test.mp3 -> 517567145
DEBUG - 使用API模式刷新URL成功: 517567145
INFO - URL刷新成功，重试下载 (第1次)
DEBUG - 开始下载NetEase音频: https://api.paugram.com/netease/?id=517567145
DEBUG - NetEase音频文件下载完成: /tmp/netease_517567145_test.mp3, 大小: 4567890 字节
```

## 总结

该实现解决了NetEase Cloud Music URL过期导致的下载失败问题，通过智能的URL刷新机制确保歌曲能够正常播放，同时保持了良好的性能和兼容性。
