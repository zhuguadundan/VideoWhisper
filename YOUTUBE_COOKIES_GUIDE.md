# YouTube Cookies 配置指南

当遇到 "Sign in to confirm you're not a bot" 错误时，需要配置浏览器 cookies 来绕过 YouTube 的反机器人保护。

## 方法一：使用浏览器 Cookies（推荐）

系统会自动尝试从以下浏览器导入 cookies：
1. Chrome（优先）
2. Firefox
3. Edge
4. Safari

**要求：**
- 已安装并登录相应浏览器
- 在浏览器中已登录 YouTube 账号

## 方法二：手动导出 Cookies

### Chrome 浏览器：
1. 安装 [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) 扩展
2. 访问 YouTube.com 并登录
3. 点击扩展图标，选择 "Export cookies.txt"
4. 将下载的 `cookies.txt` 文件放在项目根目录下

### Firefox 浏览器：
1. 安装 [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) 扩展
2. 访问 YouTube.com 并登录
3. 点击扩展图标，导出 cookies
4. 将 `cookies.txt` 文件放在项目根目录下

## 方法三：命令行导出（高级用户）

使用 yt-dlp 命令行工具：
```bash
yt-dlp --cookies-from-browser chrome --write-info-json --skip-download "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## 故障排除

1. **确认 cookies 文件位置**：cookies.txt 应该在项目根目录（与 run.py 同级）

2. **检查 cookies 文件格式**：文件应包含以下格式的内容：
   ```
   # Netscape HTTP Cookie File
   .youtube.com	TRUE	/	FALSE	1234567890	cookie_name	cookie_value
   ```

3. **定期更新 cookies**：cookies 有时效性，建议定期重新导出

4. **尝试不同浏览器**：如果一个浏览器的 cookies 不工作，尝试其他浏览器

## 注意事项

- 不要共享或上传 cookies.txt 文件，其中包含您的登录信息
- cookies.txt 已添加到 .gitignore 文件中，不会被提交到代码库
- 如果仍有问题，可以尝试使用其他 YouTube 视频链接或稍后重试