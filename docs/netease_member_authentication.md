# 网易云音乐会员认证功能

## 概述

Odysseia-Similu 音乐机器人现在支持网易云音乐会员认证功能，允许使用会员账号Cookie来访问VIP专属歌曲和高品质音频。通过配置会员认证，机器人可以下载原本受限的会员内容，提供更好的音乐体验。

## 系统要求

- Python 3.8+
- cryptography库 (用于API加密)
- aiohttp库 (用于异步HTTP请求)

安装依赖：
```bash
pip install cryptography aiohttp
```

## 功能特性

- **Cookie认证**: 使用网易云音乐会员账号Cookie进行身份验证
- **VIP歌曲访问**: 下载会员专属和VIP限制的歌曲
- **高品质音频**: 支持多种音质等级，包括无损和高解析度音频
- **安全处理**: 安全的Cookie存储和敏感信息保护
- **智能回退**: 会员功能失败时自动回退到免费模式
- **缓存优化**: 会员状态和音频URL缓存，提高性能
- **向后兼容**: 与现有反向代理功能完全兼容

## 支持的音质等级

| 等级 | 描述 | 比特率 | 格式 | 会员要求 |
|------|------|--------|------|----------|
| `standard` | 标准品质 | 128kbps | MP3 | 无 |
| `higher` | 较高品质 | 192kbps | AAC | 无 |
| `exhigh` | 极高品质 | 320kbps | AAC | 推荐 |
| `lossless` | 无损品质 | 999kbps | FLAC | VIP |
| `hires` | 高解析度 | 1411kbps | FLAC | VIP |

## 配置说明

### 获取会员Cookie

1. **登录网易云音乐**
   - 在浏览器中访问 [music.163.com](https://music.163.com)
   - 使用会员账号登录

2. **获取MUSIC_U Cookie**
   - 打开浏览器开发者工具 (F12)
   - 切换到 "Application" 或 "存储" 标签
   - 在左侧找到 "Cookies" → "music.163.com"
   - 复制 `MUSIC_U` 的值

3. **获取CSRF令牌（可选）**
   - 在同一位置找到 `__csrf` 的值
   - 通常会自动从MUSIC_U中提取

### 基本配置

在 `config/config.yaml` 文件中添加以下配置：

```yaml
# 网易云音乐会员认证配置
netease_member:
  # 启用会员认证功能
  enabled: true
  
  # 会员账号Cookie配置
  cookies:
    # 主要认证Cookie - 从浏览器获取
    MUSIC_U: "你的MUSIC_U_Cookie值"
    
    # 可选的CSRF令牌
    __csrf: "你的CSRF令牌"
```

### 高级配置

```yaml
netease_member:
  enabled: true
  
  cookies:
    MUSIC_U: "你的MUSIC_U_Cookie值"
    __csrf: "你的CSRF令牌"
    
    # 其他可能需要的Cookie
    additional_cookies:
      "NMTID": "xxx"
      "WEVNSM": "xxx"
  
  # 音频质量配置
  audio_quality:
    default_level: "exhigh"      # 默认音质等级
    preferred_format: "aac"      # 偏好音频格式
    auto_fallback: true          # 自动降级音质
  
  # 认证和安全配置
  authentication:
    validity_check_interval: 3600    # Cookie有效性检查间隔（秒）
    auto_disable_on_invalid: true    # Cookie失效时自动禁用
    max_retry_attempts: 3            # 最大重试次数
    retry_interval: 2                # 重试间隔（秒）
  
  # 缓存配置
  cache:
    enabled: true                    # 启用缓存
    expiry_time: 1800               # 会员信息缓存过期时间（秒）
    cache_audio_urls: true          # 缓存音频URL
    audio_url_expiry: 300           # 音频URL缓存过期时间（秒）
  
  # 调试配置
  debug:
    log_authentication: true        # 记录认证日志
    log_quality_selection: true     # 记录音质选择日志
    log_cookie_usage: false         # 记录Cookie使用（敏感）
    mask_sensitive_data: true       # 隐藏敏感信息
  
  # 兼容性配置
  compatibility:
    fallback_to_free: true          # 回退到免费模式
    preserve_command_syntax: true   # 保持命令语法
    error_handling: "notify"        # 错误处理策略
```

## 工作原理

### 认证流程

1. **Cookie验证**: 验证MUSIC_U Cookie格式和有效性
2. **API加密**: 使用WEAPI/EAPI加密算法对请求进行加密
3. **会员状态检查**: 调用网易云音乐API检查会员状态
4. **权限缓存**: 缓存会员信息和权限状态
5. **音频获取**: 使用会员权限获取高品质音频URL

### API加密机制

本实现使用与网易云音乐官方客户端相同的加密算法：

- **WEAPI加密**: 用于网页端API请求，采用AES+RSA混合加密
- **EAPI加密**: 用于客户端API请求，采用AES加密
- **关键发现**: EAPI加密使用`/api/`路径，但实际请求使用`/eapi/`路径
- **自动CSRF**: 自动从MUSIC_U Cookie中提取或生成CSRF令牌

#### EAPI路径转换机制

这是解决404错误的关键发现：

```python
# 加密时使用的路径
encrypt_path = "/api/song/enhance/player/url"

# 实际请求的路径
request_path = "/eapi/song/enhance/player/url"

# 这个差异是网易云音乐EAPI工作的核心机制
```

不同的路径会产生完全不同的加密结果，这解释了为什么之前会出现404错误。

#### EAPI响应处理机制

网易云音乐EAPI端点返回加密的响应数据：

```python
# 响应检测和处理
content_type = response.headers.get('content-type', '')

if content_type.startswith('text/plain'):
    # EAPI加密响应 - 需要解密
    raw_content = await response.read()
    decrypted_text = eapi_decrypt(raw_content)
    result = json.loads(decrypted_text)
else:
    # 普通JSON响应 - 直接解析
    result = await response.json()
```

**响应类型识别**:
- `text/plain;charset=utf-8` → EAPI加密响应，需要解密
- `application/json` → 普通JSON响应，直接解析

#### EAPI解密优化

针对AES块长度对齐问题的修复：

```python
# 检查数据长度是否为AES块大小的倍数
block_size = 16  # AES块大小
if len(cipher_bytes) % block_size != 0:
    # 智能处理：填充或截断到块边界
    if len(cipher_bytes) < block_size:
        padding_needed = block_size - (len(cipher_bytes) % block_size)
        cipher_bytes.extend(b'\x00' * padding_needed)
    else:
        truncate_length = (len(cipher_bytes) // block_size) * block_size
        cipher_bytes = cipher_bytes[:truncate_length]
```

#### 会员音频URL支持

新增对直接音频链接的支持：

```python
# 支持的会员音频URL格式
- http://m701.music.126.net/.../*.mp3
- https://music.126.net/.../*.flac
- 支持格式：mp3, flac, m4a, aac
- 自动检测和元数据提取

#### 代理配置智能处理

针对直接音频URL的代理配置优化：

```python
def _process_direct_url_for_proxy(self, url: str) -> str:
    """为直接音频URL处理代理配置"""
    # 检查域名映射配置
    domain_mapping = self.proxy_manager.get_domain_mapping()
    original_domain = parsed.netloc.lower()

    # 如果映射域名与原域名相同，说明配置为直连
    if mapped_domain and mapped_domain.lower() == original_domain:
        return url  # 保持原始URL

    # 否则应用代理域名替换
    return self.proxy_manager.replace_domain_in_url(url)
```

#### 歌曲ID缓存机制

建立URL与歌曲ID的关联：

```python
# 会员认证时缓存映射
self._cache_url_song_id_mapping(member_url, song_id)

# 后续处理时获取关联
cached_song_id = self._get_cached_song_id(url)

# 使用歌曲ID获取完整元数据
metadata = await self._get_song_metadata_by_id(song_id)
```

#### 代理直连配置修复

解决自映射配置识别问题：

```python
# 检查是否为自映射（直连配置）
target_lower = target_domain.lower()
is_self_mapping = False

if domain_without_port == target_lower:
    # 精确匹配的自映射
    is_self_mapping = True
elif domain_without_port.endswith('.' + target_lower):
    # 子域名匹配到父域名，且父域名配置为自映射
    domain_mapping = self.get_domain_mapping()
    parent_mapping = domain_mapping.get(target_lower)
    if parent_mapping and parent_mapping.lower() == target_lower:
        is_self_mapping = True

if is_self_mapping:
    return url  # 保持原始URL
```

**支持的配置场景**:
```yaml
# 直连配置 - 所有子域名都保持原样
netease_proxy:
  domain_mapping:
    music.126.net: music.126.net

# 代理配置 - 所有子域名都使用代理
netease_proxy:
  domain_mapping:
    music.126.net: 139.196.252.172:58581
```
```

### 音质选择策略

1. **默认音质**: 使用配置的默认音质等级
2. **权限检查**: 验证当前会员等级是否支持请求的音质
3. **自动降级**: 如果请求的音质不可用，自动选择较低音质
4. **格式优化**: 根据音质等级选择最佳音频格式

### 错误处理和回退

1. **Cookie失效**: 自动检测并处理Cookie过期
2. **网络错误**: 重试机制处理临时网络问题
3. **权限不足**: 回退到免费用户可用的音质
4. **API限制**: 遵守网易云音乐API速率限制

## 使用示例

### 示例1: 基本会员配置

```yaml
netease_member:
  enabled: true
  cookies:
    MUSIC_U: "1234567890abcdef..."
```

**效果**: 启用会员功能，使用默认音质设置

### 示例2: 高音质配置

```yaml
netease_member:
  enabled: true
  cookies:
    MUSIC_U: "1234567890abcdef..."
  audio_quality:
    default_level: "lossless"
    preferred_format: "flac"
    auto_fallback: true
```

**效果**: 优先使用无损音质，失败时自动降级

### 示例3: 调试配置

```yaml
netease_member:
  enabled: true
  cookies:
    MUSIC_U: "1234567890abcdef..."
  debug:
    log_authentication: true
    log_quality_selection: true
    mask_sensitive_data: true
```

**效果**: 启用详细日志记录，同时保护敏感信息

## 安全考虑

### Cookie安全

1. **格式验证**: 验证Cookie格式防止无效输入
2. **敏感信息隐藏**: 日志中自动隐藏Cookie值
3. **安全存储**: Cookie仅存储在配置文件中
4. **访问控制**: 限制Cookie的使用范围

### 账号保护

1. **速率限制**: 遵守API调用频率限制
2. **错误处理**: 避免频繁的失败请求
3. **自动禁用**: Cookie失效时自动停止使用
4. **监控日志**: 记录认证状态变化

### 隐私保护

1. **数据最小化**: 只获取必要的用户信息
2. **本地处理**: 所有认证在本地进行
3. **无存储**: 不存储用户的个人信息
4. **透明性**: 详细的日志记录所有操作

## 故障排除

### 常见问题

1. **Cookie无效**
   ```
   错误: MUSIC_U Cookie格式无效
   解决: 重新从浏览器获取正确的Cookie值
   ```

2. **会员状态检查失败**
   ```
   错误: 会员状态检查失败: 401 Unauthorized
   解决: Cookie可能已过期，需要重新登录获取
   ```

3. **API加密失败**
   ```
   错误: WEAPI加密失败: 需要安装cryptography库
   解决: 安装加密库: pip install cryptography
   ```

4. **CSRF令牌提取失败**
   ```
   错误: 从MUSIC_U提取CSRF令牌失败: 'utf-8' codec can't decode byte
   解决: 系统会自动使用Cookie哈希值生成CSRF令牌，无需手动处理
   ```

5. **API端点404错误**
   ```
   错误: 音频API响应状态码: 404
   解决: 已更新为正确的API端点，确保网络连接正常
   ```

6. **NoneType错误**
   ```
   错误: "NoneType" object has no attribute "get"
   解决: 这通常是API响应为空，检查Cookie有效性和网络连接
   ```

5. **音质不可用**
   ```
   错误: 请求的音质等级不可用
   解决: 检查会员等级或启用自动降级
   ```

6. **网络连接问题**
   ```
   错误: 获取会员音频URL时出错: Connection timeout
   解决: 检查网络连接或代理设置
   ```

### 调试方法

1. **启用详细日志**:
   ```yaml
   netease_member:
     debug:
       log_authentication: true
       log_quality_selection: true
   ```

2. **检查会员状态**:
   ```
   INFO similubot.utils.netease_member - 会员状态检查成功: 用户名 (VIP: True)
   ```

3. **验证Cookie格式**:
   ```
   WARNING similubot.utils.netease_member - MUSIC_U Cookie格式无效
   ```

4. **监控音质选择**:
   ```
   DEBUG similubot.utils.netease_member - 请求音频质量: exhigh (320000bps, aac)
   ```

## 性能优化

### 缓存策略

- **会员信息缓存**: 30分钟缓存会员状态
- **音频URL缓存**: 5分钟缓存下载链接
- **智能刷新**: 只在必要时检查会员状态

### 网络优化

- **连接复用**: 复用HTTP连接减少延迟
- **并发控制**: 限制同时进行的请求数量
- **超时设置**: 合理的请求超时时间

### 资源管理

- **内存使用**: 及时清理过期缓存
- **CPU优化**: 异步处理避免阻塞
- **存储效率**: 最小化配置文件大小

## 更新日志

- **v1.1.6**: 修复代理直连配置问题
  - 修复自映射配置（music.126.net -> music.126.net）的识别逻辑
  - 添加子域名匹配支持，确保m801.music.126.net等子域名正确处理
  - 改进代理配置调试日志，明确显示直连决策过程
  - 解决了代理系统错误替换直连配置URL的问题

- **v1.1.5**: 修复代理处理和元数据提取问题
  - 修复直接音频URL的代理配置处理逻辑
  - 实现歌曲ID缓存机制，建立URL与歌曲的关联
  - 改进元数据提取，使用完整的NetEase API信息
  - 重构为歌曲ID驱动的架构，提高系统一致性

- **v1.1.4**: 修复EAPI解密和URL兼容性问题
  - 修复EAPI解密中的AES块长度对齐问题
  - 添加对会员音频直链URL的支持（music.126.net域名）
  - 改进EAPI解密错误处理，增加智能回退机制
  - 解决了"不支持的URL格式"和"block length"错误

- **v1.1.3**: 修复EAPI响应解密问题
  - 实现EAPI加密响应的自动检测和解密
  - 支持`text/plain;charset=utf-8`和`application/json`两种响应格式
  - 添加智能回退机制，解密失败时尝试直接解析
  - 解决了"Attempt to decode JSON with unexpected mimetype"错误

- **v1.1.2**: 修复EAPI加密路径问题（关键修复）
  - **重大发现**: 修复EAPI加密中的路径转换问题
  - 加密时使用`/api/`路径，请求时使用`/eapi/`路径
  - 这是pyncm参考实现的关键机制，解决了404错误的根本原因
  - 完全解决了会员音频URL获取失败的问题

- **v1.1.1**: 修复EAPI请求格式问题
  - 修复EAPI请求参数格式，添加必要的header字段
  - 更新EAPI Cookie配置，与pyncm参考实现完全一致
  - 使用正确的设备信息和请求ID生成
  - 确保与网易云音乐服务器的完全兼容性

- **v1.1.0**: 修复关键问题
  - 修复CSRF令牌提取失败问题，支持各种Cookie格式
  - 修复API端点404错误，更新为正确的网易云音乐API地址
  - 改进错误处理，增强系统稳定性
  - 优化Cookie格式验证，支持更多Cookie类型

- **v1.0.0**: 初始版本，支持基本会员认证和VIP歌曲下载
  - 支持多种音质等级选择
  - 添加安全的Cookie处理机制
  - 实现智能回退和错误处理
  - 完善的缓存和性能优化
