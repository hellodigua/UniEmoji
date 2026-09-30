# UniEmoji

**统一的 emoji 协议，用一套语义连接不同的表情。**

Same meanings, any face.

一句话解释：UniEmoji 让 AI 用上丰富多样的表情包。通过统一 emoji 的语义，关联不同风格的表情图片，AI 回复中的 emoji 就能呈现为对应的表情包，让同一种表达拥有不同的面孔。

[访问官网](https://hellodigua.github.io/UniEmoji/)

## 同样是大哭，让AI使用同一种语义表达

|                       贴吧                       |                       知乎                       |                         小红书                          |                        抖音                        |                       QQ                       |                        B 站                         |                       微博                       |
| :----------------------------------------------: | :----------------------------------------------: | :-----------------------------------------------------: | :------------------------------------------------: | :--------------------------------------------: | :-------------------------------------------------: | :----------------------------------------------: |
| <img src="origins/tieba/tb_09.png" width="40" /> | <img src="origins/zhihu/zh_13.png" width="40" /> | <img src="output/xiaohongshu/xhs_15.avif" width="40" /> | <img src="output/douyin/dy_120.avif" width="40" /> | <img src="output/qq/qq_009.avif" width="40" /> | <img src="output/bilibili/bl_07.avif" width="40" /> | <img src="output/weibo/wb_12.avif" width="40" /> |

## 生态实现

本项目定义 emoji 与表情图片之间的语义约定，具体的接入和展示由各个实现完成。

| 实现 | 适配项目 | 备注 |
| --- | --- | --- |
| [uniemoji-browser-extension](https://github.com/hellodigua/uniemoji-browser-extension) | 浏览器扩展 | 已适配 DeepSeek、Gemini |
| [dsh-emoji](https://github.com/hellodigua/dsh-emoji) | deepseek-harness | — |

欢迎为更多应用开发基于 UniEmoji 的实现。

## 北邮人表情

收录北邮人论坛表情面板的经典、悠嘻猴、兔斯基、洋葱头四组，共 199 张原始素材。原始 GIF 保存在 `origins/byr_*/`；140 张动画原样保留，59 张静态素材完成 AI 清晰化，并增加 4 张动图的高清静态伴随图，新增可用条目共 203 个。经过审核的 AI 高清静态母版保存在 `enhanced/byr_*/`，160px 展示版本和原始动图位于 `output/byr_*/`。动画的额外高清静态版本会明确标注。实际处理数量和对应关系以 [处理记录](docs/byr-processing.json) 为准。

[原图与高清对比](docs/byr-preview.html) 支持分组、名称搜索、深色背景核对和高清 PNG 母版下载，需通过 HTTP 服务打开。63 张母版的逐图复核结果及对比图见 [视觉审核记录](docs/byr-ai-review.json)。

采集、发布和离线校验需要 Python 3.10+ 与 Pillow（发布 AVIF 建议 Pillow 12+）。安装依赖后可执行：

```bash
python3 scripts/fetch-byr.py          # 官方编号采集，支持缓存与重试
python3 scripts/fetch-byr.py --offline # 核对原始 GIF 和来源哈希
python3 scripts/prepare-byr.py        # 从审核通过的母版重建展示图与 emoji.json
python3 scripts/validate-byr.py       # 校验素材、语义、动画及发布对应关系
npm test
npm run build
python3 scripts/validate-byr.py --dist # 检查平铺构建产物
```

`prepare-byr.py` 只缩小并编码已有母版，不会自行调用 AI 或把普通放大标记为 AI 修复。母版使用内置 imagegen 逐图生成，提示词保存在各图片的 JSON 记录中。审核通过的记录必须包含与当前母版一致的 `reviewed_sha256`；母版更新后须重新审核，发布和离线校验都会拒绝缺失或不匹配的审核哈希。首页支持按中文组名、名称、标签和关键词搜索；点击复制的是 PNG 静态帧，需要完整动画时使用“下载”。

## 许可与素材权利

本项目原创代码及文档采用 [MIT 许可证](LICENSE)。第三方表情素材的相关权利归各自权利人所有，**不适用 MIT 许可证**。

**本项目内表情图片未取得相关平台或权利人的授权。** 收录或提供下载不构成对使用者的授权，个人娱乐用途也不代表素材可自由使用或再分发。详见 [第三方素材权利说明](THIRD_PARTY_NOTICES.md)。
