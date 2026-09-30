# Emoji Compressor 使用说明

## 功能概述

`compressor.py` 是一个综合性的表情包压缩工具，整合了整个项目中所有学到的图片处理技术。

## 主要特性

- 支持多种图片格式：PNG, JPG, WebP, AVIF, GIF
- GIF 原样复制为 `.gif`，完整保留动画帧、播放时长、循环及透明度，不缩放、不压缩、不做 AI 增强
- 智能格式检测和转换
- 可配置的压缩尺寸和质量
- 多工具支持与回退机制（avifenc、cwebp、sips、ImageMagick 等）
- 透明度保持（特别针对 WebP 格式）
- 详细的统计报告

## 基本使用

### 默认压缩（60x60 像素）

```bash
python compressor.py
```

### 自定义参数

```bash
python compressor.py --input origins --output output --size 80 --quality 60
```

### 参数说明

- `--input`: 输入目录（默认：origins）
- `--output`: 输出目录（默认：output）
- `--size`: 静态图片目标尺寸（默认：60 像素，不影响 GIF）
- `--quality`: 静态图片压缩质量（默认：50，不影响 GIF）
- `--quiet`: 关闭逐文件详细信息，保留汇总

## 处理流程

1. **格式检测**: 根据文件头识别 PNG、JPG、WebP、AVIF、GIF87a/GIF89a，扫描包含 `.gif` 及 `.GIF` 文件。
2. **GIF 保留**: GIF 直接复制到输出目录，输出扩展名为 `.gif`；绕过静态转换流程，无需安装编码器。
3. **透明度处理**: 静态 WebP 文件通过 dwebp->PNG->AVIF 管道保持透明度。
4. **尺寸和质量**: 静态图片按指定尺寸缩放，优先转换为 AVIF，编码失败时降级为 WebP。
5. **统计报告**: 记录实际输出文件名、格式及处理前后大小；GIF 格式为 `GIF`、`target_size` 为 `original`，压缩率为 0%。

## BYR 素材的独立流水线

北邮人论坛的 `byr_em`、`byr_ema`、`byr_emb`、`byr_emc` 四组由 `scripts/prepare-byr.py` 独立维护，不加入通用压缩器的默认平台映射。原始 GIF、AI 增强母版与发布图由该流水线分别管理，避免运行 `python compressor.py` 时从原始素材重新生成并覆盖增强结果。

通用压缩器的 GIF 支持只保证原文件完整保留，不代表图像已变清晰，也不会执行 AI 补全。需要提高静态发布图的清晰度时，应保留高分辨率母版并设置合适的发布尺寸；默认 60 像素仅适用于现有的小尺寸展示。

## 技术要求

- Python 3.6+
- macOS 系统（使用 sips 工具）
- 已安装的工具：
  - avifenc/avifdec（libavif 包）
  - dwebp（webp 包）
  - sips（macOS 内置）

## 安装依赖

```bash
# 安装libavif
brew install libavif

# 安装webp工具
brew install webp
```

## 示例结果

处理完成后会显示类似以下的统计信息：

```
=== 压缩统计报告 ===
总文件数: 245
成功压缩: 245
失败: 0
原始总大小: 15.2 MB
压缩后总大小: 3.8 MB
压缩比: 75.0%
平均文件大小: 15.5 KB
```
