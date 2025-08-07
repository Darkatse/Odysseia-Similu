# 网易云音乐反向代理功能

## 概述

Odysseia-Similu 音乐机器人现在支持网易云音乐反向代理功能，用于解决海外部署时的版权限制问题。通过配置反向代理服务器，所有网易云音乐相关请求将通过中国IP地址进行路由，从而绕过地理位置限制。

## 功能特性

- **自动域名替换**: 自动将所有网易云音乐域名替换为配置的代理域名
- **灵活配置**: 支持全局代理域名和特定域名映射
- **协议支持**: 支持HTTP和HTTPS代理协议
- **请求头处理**: 智能处理Referer、Host等请求头
- **调试支持**: 提供详细的调试日志记录
- **向后兼容**: 代理功能默认禁用，不影响现有部署

## 支持的域名

反向代理功能支持以下网易云音乐相关域名：

- `music.163.com` - 主要API和网页域名
- `music.126.net` - CDN和媒体文件域名  
- `y.music.163.com` - 移动端域名
- `api.paugram.com` - 第三方API代理域名

## 配置说明

### 基本配置

在 `config/config.yaml` 文件中添加以下配置：

```yaml
# 网易云音乐反向代理配置
netease_proxy:
  # 是否启用反向代理功能
  enabled: true  # 设置为 true 启用代理功能
  
  # 反向代理服务器域名
  proxy_domain: "your-proxy-server.com"
  
  # 代理协议设置
  use_https: false  # 设置为 false 使用 HTTP，true 使用 HTTPS
```

### 高级配置

```yaml
netease_proxy:
  enabled: true
  proxy_domain: "proxy.example.com"
  use_https: false
  
  # 域名映射配置 - 支持更精细的控制
  domain_mapping:
    "music.163.com": "music-proxy.example.com"  # 特定域名映射
    "music.126.net": ""  # 空值使用默认 proxy_domain
    "api.paugram.com": "api-proxy.example.com"
  
  # 请求头配置
  headers:
    preserve_referer: true   # 是否保持原始Referer头
    preserve_host: false     # 是否保持原始Host头
    custom_headers:          # 自定义请求头
      "X-Forwarded-For": "original-client-ip"
      "X-Real-IP": "original-client-ip"
  
  # 调试配置
  debug:
    log_domain_replacement: true   # 记录域名替换日志
    log_proxy_requests: false      # 记录代理请求详情（生产环境建议关闭）
```

## 工作原理

### URL重写流程

1. **URL检测**: 检查请求URL是否为网易云音乐相关域名
2. **域名映射**: 根据配置的映射规则替换域名
3. **协议处理**: 根据配置设置HTTP或HTTPS协议
4. **路径保持**: 保持原始URL的路径、查询参数和片段

### 请求头处理

1. **Referer处理**: 
   - `preserve_referer: true`: 保持或设置为原始域名
   - `preserve_referer: false`: 移除Referer头
2. **Host处理**:
   - `preserve_host: false`: 移除Host头，使用代理域名
   - `preserve_host: true`: 保持原始Host头
3. **自定义头**: 添加配置的自定义请求头

## 使用示例

### 示例1: 基本代理配置

```yaml
netease_proxy:
  enabled: true
  proxy_domain: "netease-proxy.myserver.com"
  use_https: false
```

**效果**:
- `https://music.163.com/song?id=123` → `http://netease-proxy.myserver.com/song?id=123`
- `https://api.paugram.com/netease/?id=123` → `http://netease-proxy.myserver.com/netease/?id=123`

### 示例2: 多域名映射

```yaml
netease_proxy:
  enabled: true
  proxy_domain: "default-proxy.com"
  use_https: true
  domain_mapping:
    "music.163.com": "music-api.proxy.com"
    "music.126.net": "cdn.proxy.com"
    "api.paugram.com": ""  # 使用默认代理域名
```

**效果**:
- `https://music.163.com/api/search` → `https://music-api.proxy.com/api/search`
- `https://music.126.net/audio/123.mp3` → `https://cdn.proxy.com/audio/123.mp3`
- `https://api.paugram.com/netease/?id=123` → `https://default-proxy.com/netease/?id=123`

## 部署建议

### 反向代理服务器设置

推荐使用 Nginx 作为反向代理服务器，配置示例：

```nginx
server {
    listen 80;
    server_name your-proxy-server.com;
    
    # 代理网易云音乐API
    location /api/ {
        proxy_pass https://music.163.com/api/;
        proxy_set_header Host music.163.com;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # 代理媒体文件
    location /song/media/ {
        proxy_pass https://music.163.com/song/media/;
        proxy_set_header Host music.163.com;
        proxy_set_header Referer https://music.163.com/;
    }
    
    # 代理第三方API
    location /netease/ {
        proxy_pass https://api.paugram.com/netease/;
        proxy_set_header Host api.paugram.com;
    }
}
```

### 安全考虑

1. **访问控制**: 限制代理服务器的访问来源
2. **日志记录**: 监控代理请求的使用情况
3. **速率限制**: 防止滥用代理服务器
4. **SSL证书**: 为HTTPS代理配置有效的SSL证书

## 故障排除

### 常见问题

1. **代理功能不生效**
   - 检查 `enabled: true` 是否正确设置
   - 验证 `proxy_domain` 配置是否正确
   - 查看日志中的域名替换记录

2. **音频下载失败**
   - 检查代理服务器是否正常运行
   - 验证代理服务器的网络连接
   - 确认代理服务器能够访问网易云音乐

3. **请求头问题**
   - 调整 `preserve_referer` 和 `preserve_host` 设置
   - 检查自定义请求头配置
   - 启用 `log_proxy_requests` 查看详细请求信息

### 调试方法

1. **启用调试日志**:
   ```yaml
   netease_proxy:
     debug:
       log_domain_replacement: true
       log_proxy_requests: true
   ```

2. **检查日志输出**:
   ```
   DEBUG similubot.utils.netease_proxy - 域名替换: https://music.163.com/song?id=123 -> http://proxy.example.com/song?id=123
   DEBUG similubot.utils.netease_proxy - 代理请求头: {'User-Agent': '...', 'Referer': 'https://music.163.com/'}
   ```

3. **测试代理连接**:
   ```bash
   curl -H "Host: music.163.com" http://your-proxy-server.com/api/search/get?s=test&type=1&limit=1
   ```

## 性能影响

- **延迟增加**: 通过代理服务器会增加网络延迟
- **带宽消耗**: 代理服务器需要足够的带宽处理音频流量
- **缓存优化**: 建议在代理服务器上启用适当的缓存策略

## 更新日志

- **v1.0.0**: 初始版本，支持基本域名替换和请求头处理
- 支持多域名映射配置
- 添加调试和日志功能
- 完善错误处理和边界情况处理
