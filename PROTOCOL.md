# UniEmoji 协议

UniEmoji 是统一的 emoji 协议。同一套语义，换成任何一副表情。

UniEmoji is a unified emoji protocol. Same meanings, any face.

当前契约标识为：

```text
uniemoji-core@1
```

`Uni` 表示统一的语义，也点 Unicode 这条线。模型或用户给出的是受控 Unicode 表情；显示端按 40 个稳定语义 key，换成当前表情包的图。换一套包，就是换一副脸，语义不变。贴吧、B 站、抖音、QQ、小红书、微博、知乎，以及以后任何画风，都可以成为一副可替换的皮。

本仓库是这份协议和素材的大本营，不是收录站。40 个 key 的含义、相近语义边界和绘制要求以 [EMOJI_KEYS.md](EMOJI_KEYS.md) 为准。

## 线协议

AI 或用户只输出受控 Unicode。Host 再按本契约换成图。key 是机器协议，不翻译、不改名，也不把作品角色名写入 key。表情包只实现 key 与图片，不能自定义 Unicode 映射。

规范映射如下：

```text
😊→happy        😢→sad          😕→confused     👀→watching
😠→angry        😑→speechless   😉→doge         😵‍💫→overloaded
😐→neutral      😆→laughing     😭→crying       😅→sweating
🤔→thinking     👌→okay         🙂‍↕️→nodding       😴→sleeping
🥺→hurt         🫣→peeking      👍→approve      🫶→heart
😳→shy          🤩→star-eyes    😂→laugh-cry    🥹→touched
😱→scared       🤦→facepalm     🙄→eye-roll     😮‍💨→sigh
😫→frustrated   😜→playful      🤭→snickering   😏→sarcastic
😎→cool         🎉→celebrate    💪→cheer        🙏→thanks
🙇→sorry        🤗→hug          🤲→please       👏→applause
```

Host 另接受两个明确别名：`😄→laughing`、`🙂→happy`。它们不新增素材 key。其他 Unicode 保持原样，不根据相似度或上下文猜测情绪，也不自动补图。

40 个稳定 key 是：

```text
happy, sad, confused, watching, angry, speechless, doge, overloaded,
neutral, laughing, crying, sweating, thinking, okay, nodding, sleeping,
hurt, peeking, approve, heart, shy, star-eyes, laugh-cry, touched,
scared, facepalm, eye-roll, sigh, frustrated, playful, snickering,
sarcastic, cool, celebrate, cheer, thanks, sorry, hug, please, applause
```

## 表情包形态

以后分发 ZIP 时使用下面的结构。ZIP 可以直接包含这些文件，也可以再包一层同名目录：

```text
my-emoji-pack.zip
├── pack.json
└── images/
    ├── happy.png
    ├── sad.png
    └── ...其余 38 个标准 key
```

`pack.json` 必须同时声明：

```json
{
  "schemaVersion": 1,
  "keySet": "uniemoji-core@1",
  "id": "my-emoji-pack",
  "name": "我的表情包",
  "version": "1.0.0"
}
```

`schemaVersion` 描述 ZIP 与 `pack.json` 的技术格式；`keySet` 描述图片所实现的语义集合。两者独立演进。当前成品包必须声明 `uniemoji-core@1`。

每个 key 必须且只能提供一张 `images/<key>.png`，文件名大小写与上表完全一致。`id` 使用小写字母、数字和连字符，`version` 使用 SemVer。`uniemoji-core@1` 中现有 key 的含义不会被静默改变；若未来发生不兼容的增删或重定义，将发布新的 `keySet` 主版本。

适配器可以额外限制体积、尺寸、路径和安装位置。那些限制属于 Host 实现，不属于本契约的语义部分。

## 适配器

第一个适配器是 [dsh-emoji](https://www.npmjs.com/package/dsh-emoji)。本仓库只维护协议和素材，不实现 Host、浏览器插件或跨 Agent 接入。以后任何能把受控 Unicode 换成当前表情包图片的程序，都可以成为适配器。
