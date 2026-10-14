# DocGen 演示文档

这份示例覆盖 **W0~W3 的全部特性**，用来验证 `DFM → IR → HTML / Word` 链路。
段落里可以有 **粗体**、*斜体*、~~删除线~~、`inline code`、H~2~O、E=mc^2^，
以及 [一个链接](https://example.com)。

[[toc]]

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

\begin{code:markdown}
内部可以出现 ``` 而不提前终止：
```python
print(1)
```
\end{code:markdown}

## 表格与数学

| 语法 | IR 节点 |
| --- | --- |
| `**粗体**` | `Styled(style_name="strong")` |
| `[[img:path]]` | `Image` / `ImageBlock` |

行内数学 $x^2 + y^2 = z^2$ 与块级公式：

$$
\int_0^1 x \, dx = \frac{1}{2}
$$

带编号的公式（渲染成无边框三列表格，编号可用 `[[ref:eq:main]]` 引用）：

\begin{equation #eq:main number=1}
$$
E = mc^2
$$
\end{equation}

## 题注与交叉引用

\begin{caption #fig:1}
系统架构（图题注会自动编号）
\end{caption}

见图 [[ref:fig:1]]，另见式 [[ref:eq:main]]。

\begin{table #tab:1}
参数表
\end{table}

两个题注都带书签，正文里的引用是 Word 的 `REF` 域，编号变化时自动更新。

## 图片与分页

[[img:pics/photo.png]]

[[pagebreak]]

最后一页的收尾段落。
