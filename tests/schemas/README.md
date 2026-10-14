# 随附的 OOXML schema（ECMA-376 / ISO-IEC 29500）

这些 `.xsd` 用来对引擎产出的 `word/document.xml` 做**官方 schema 校验**
（[`tests/test_ooxml_schema.py`](../test_ooxml_schema.py)），
比手写结构检查强得多：OOXML 的属性容器是 `xsd:sequence`，
**子元素顺序错了 Word 会静默忽略**，只有 schema 能指出来。

## 来源

取自 [python-openxml/python-docx](https://github.com/python-openxml/python-docx) 仓库的
`ref/xsd/` 目录（该目录本身是 ECMA-376 / ISO-IEC 29500 的 WordprocessingML schema，
由 ECMA 与 ISO 免费提供）。学习借鉴时一并随附，仅用于测试校验，不参与运行时逻辑。

只保留了 WML 的**依赖闭环**：

| 文件 | 作用 |
|---|---|
| `wml.xsd` | WordprocessingML 主体（`w:`） |
| `shared-math.xsd` | OMML 数学（`m:`） |
| `shared-commonSimpleTypes.xsd` | 公共简单类型 |
| `shared-relationshipReference.xsd` | `r:id` 等关系引用 |
| `shared-customXmlSchemaProperties.xsd` | 自定义 XML 属性 |
| `dml-wordprocessingDrawing.xsd` | `wp:` 绘图 |
| `dml-main.xsd` / `dml-picture.xsd` / `dml-chart.xsd` / `dml-diagram.xsd` / `dml-chartDrawing.xsd` | `a:` / `pic:` / 图表绘图 |
| `xml.xsd` | **本项目补的最小 W3C XML 命名空间 schema**（见下） |

## 相对上游的两处调整

1. **`wml.xsd` / `shared-math.xsd` 各注入一条 import**
   （`<xsd:import id="xml" namespace="http://www.w3.org/XML/1998/namespace" schemaLocation="xml.xsd"/>`）。
   上游 wml 引用了 `xml:space`（经 `shared-commonSimpleTypes.xsd` 的 `ST_String`）
   却没 import XML 命名空间，lxml 会报
   `attribute 'ref': The QName value '{...}space' does not resolve`。
   可用 [`patch_xml_namespace.py`](patch_xml_namespace.py) 复现该补丁（幂等）。
2. **`xml.xsd` 是本项目写的最小版本**，只含 OOXML 需要的
   `xml:lang` / `xml:space` / `xml:base` / `xml:id`；
   官方完整版见 <https://www.w3.org/2001/xml.xsd>。

## 怎么用

```python
from docgen.render.ooxml_check import validate_with_schema

problems = validate_with_schema(document_xml_bytes)  # 空列表 = 合法
```

schema 编译约 0.1s，`lru_cache` 复用；单份文档校验约几十毫秒。

## 这套校验抓到过什么（都是肉眼与手写检查看不出的）

- `w:pgNumType` / `w:vAlign` 在 `w:sectPr` 里的位置错（`vAlign` 必须在 `docGrid` 之前）
- `w:tblLayout` / `w:tblBorders` 在 `w:tblPr` 里的位置错
- `w:left` 在 `w:tblBorders` 里排到了 `w:bottom` 之后
- `w:firstLineChars` 被误当成独立元素（它其实是 `w:ind` 的属性）
- 根元素上未声明前缀的 `mc:Ignorable`
