# DocGen 演示文档

这是一份用来验证 `DFM -> IR -> HTML` 链路的示例。段落里可以有 **粗体**、*斜体*、
~~删除线~~、`inline code`，以及 [一个链接](https://example.com)。

## 样式引用

自定义样式来自 config：这里是 [关键字]{.keyword}，这里是 [说明文字]{.caption}。

## 列表

- 无序项一
- 无序项二
  - 嵌套项（缩进两个空格）
1. 有序项一
2. 有序项二

## 引用与代码

> 引用第一段，行号会记在 IR 里。
>
> 引用第二段。

```python
def add(a: int, b: int) -> int:
    return a + b
```

## 表格与数学

| 语法 | IR 节点 |
| --- | --- |
| `**粗体**` | `Styled(style_name="strong")` |
| `[[img:path]]` | `Image` / `ImageBlock` |

行内数学 $x^2 + y^2 = z^2$ 与块级公式：

$$
\int_0^1 x \, dx = \frac{1}{2}
$$

## 图片与分页

[[img:pics/photo.png]]

[[pagebreak]]

最后一页的收尾段落。

