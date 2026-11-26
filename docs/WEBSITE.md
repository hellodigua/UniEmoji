# 官网维护

UniEmoji 主项目统一维护项目官网。浏览器扩展、DSH 等具体实现从官网进入各自的安装与使用页面。

## 页面归属

| 页面 | 用途 |
| --- | --- |
| `index.html` | 项目介绍、语义对照表和实现入口 |
| `protocol.html` | 协议及接入约定 |
| `gallery.html` | 原有素材浏览与搜索 |
| `browser-extension.html` | 浏览器扩展介绍、安装和使用 |
| `privacy.html` | 浏览器扩展及官网的隐私政策 |
| `assets/extension.css`、`assets/whale-preview.png` | 从扩展仓库迁入的页面样式和示例图片 |

## 本地预览

需要 Node.js/npm 和 Python 3；官网没有额外依赖或构建步骤。

```sh
npm run dev
```

访问 http://localhost:8000 。修改页面后刷新浏览器即可查看。
指定其他端口可运行 `npm run dev -- 4173`。

`npm run build` 仍用于原有素材整理，不是官网预览的前置步骤。

## 部署与迁移顺序

主项目继续使用现有 GitHub Pages：从 `main` 分支的仓库根目录发布。

1. 先将主项目迁移分支通过 PR 合入 `main`，等待 Pages 发布。
2. 确认以下新地址及页面资源可访问，再发布浏览器扩展仓库的旧地址兼容页：
   - 官网：https://hellodigua.github.io/UniEmoji/
   - 浏览器扩展：https://hellodigua.github.io/UniEmoji/browser-extension.html
   - 隐私政策：https://hellodigua.github.io/UniEmoji/privacy.html
3. 最后更新 Chrome 商店后台的官网和隐私政策字段。文档链接更新不会自动修改商店后台。

原地址 `https://hellodigua.github.io/uniemoji-browser-extension/` 跳转至浏览器扩展介绍页。
原 `privacy.html` 地址保留完整原政策，并链接至本项目的新政策；不要关闭扩展仓库的 Pages。
今后隐私说明统一在本项目更新；旧页作为历史兼容页保留，并明确指向最新说明。
