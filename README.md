# UniEmoji

统一的 emoji 协议，用同一套语义替换任何表情。

UniEmoji is a unified emoji protocol. Same meanings, any face.

模型或用户给出的是受控 Unicode 表情；显示端按 40 个稳定语义 key，换成当前表情包的图。换一套包，就是换一副脸，语义不变。贴吧、B 站、抖音、QQ、小红书、微博、知乎，以及以后任何画风，都可以成为一副可替换的皮。

本仓库是协议和素材的大本营，不是收录站。

## 协议

当前契约是 [`uniemoji-core@1`](PROTOCOL.md)。40 个 key 的含义、Unicode 映射和绘制边界见 [EMOJI_KEYS.md](EMOJI_KEYS.md)。

线协议只用这 40 个规范 Unicode，另外接受 `😄→laughing`、`🙂→happy` 两个别名。Host 负责换成图；其他 Unicode 保持原样，不猜情绪，也不自动补图。

第一个适配器是 [dsh-emoji](https://www.npmjs.com/package/dsh-emoji)。以后如果出现浏览器插件、输入法或其他 Host，它们也按同一份契约工作；那些适配器不在本仓库实现。

## 素材库

现有 7 个平台、548 张图，是素材库和候选包，不是终局产品形态。站点仍可浏览这些图：

https://hellodigua.github.io/uniemoji/

GitHub 仓库已从 `hellodigua/emoji` 改名为 `hellodigua/uniemoji`。GitHub Pages 地址随之变为上面这一条；旧地址 `https://hellodigua.github.io/emoji/` 会断开，不会自动跳转。

## 许可与素材权利

本项目原创代码及文档采用 [MIT 许可证](LICENSE)。第三方表情素材的相关权利归各自权利人所有，**不适用 MIT 许可证**。

**本项目内表情图片未取得相关平台或权利人的授权。** 收录或提供下载不构成对使用者的授权，个人娱乐用途也不代表素材可自由使用或再分发。详见 [第三方素材权利说明](THIRD_PARTY_NOTICES.md)。
