# 分支说明

本仓库两条分支，**用途不同**。

| 分支 | 用途 |
|---|---|
| `main` | **发布线**：策展过的提交，同步到远程、给别人看 |
| `dev` | **协作线**：日常开发。定期 `git merge main` 同步别人对发布线的修改 |

另有归档 ref：

| ref | 内容 |
|---|---|
| `history/fine-grained` | 最早那批**细粒度**开发提交（每个小步骤一条），保留追溯用 |
| `v0.1` | 剪枝版 v0.1 基线 |
| `v0.1.0b1` | 测试版发布点 |

> ⚠️ **本文不写死提交数、SHA、版本号、测试条数**——它们随每次提交变化，
> 写进来必然过期（实测已经因此错过好几次）。要看当前值：

```bash
git log --oneline main          # 发布线
git log --oneline main..dev     # 协作线比发布线多出的提交
git diff --name-only main dev   # 两条线的差异文件
```

---

## 拓扑

```
(根)      骨架（main 与 dev 的共同起点）
└─ #2     剪枝版 v0.1                          ← v0.1 标签
   └─ #3  Word 后端 W0~W3
      └─ #4  W4~W5 表格/图片/脚注 + 分节/页眉页脚/封面
         └─ #5  排版缺陷修复 + 官方 schema 硬校验
            └─ #6  输出与日志系统
               └─ #7  标题缩进 / 脚注
                  └─ #8  发布点（工作区整理、打包、面向使用者的文档）
                     │              ← main 的 tip
                     └─ …（dev 上继续开发）    ← dev 的 tip
```

两条线的**代码内容一致或 dev 略新**；`dev` 上的差异主要是文档与版本号这类开发改动。

## `main` 的 8 个策展提交

| # | 提交 | 主题 |
|---|---|---|
| 1 | `chore: 初始化 docgen(e)骨架` | 骨架 |
| 2 | `feat: DocGen 剪枝版 v0.1（DFM + TOML -> HTML）` | 第一个可用版本 |
| 3 | `feat(word): Word 后端 W0~W3` | OOXML 基础 → 数学 → 编号题注 → 公式编号 |
| 4 | `feat(word): W4~W5` | 表格/图片/脚注 + 分节/页码/页眉页脚/封面 |
| 5 | `fix(render,ooxml): 排版缺陷修复 + 官方 schema 硬校验` | 抓「Word 静默忽略」的错误 |
| 6 | `feat(output): 输出与日志系统` | 级别阈值 / 分流 / logfile / bug-report |
| 7 | `fix(word): 标题缩进可配 + 脚注自动编号与文本格式修正` | 用户实测报告的问题 |
| 8 | `chore(release): 整理工作区 + 准备测试版 + 面向使用者的文档` | 发布准备 |

## `dev` 从 `main` 签出

所以同步发布线的改动很直接：

```bash
git checkout dev
git merge main        # 同步别人对发布线的改动 —— 可用、干净
```

> 早期版本里 `dev` 是一条与 `main` **历史无关**的平行线，`git merge main`
> 会直接报 `refusing to merge unrelated histories`。现在两条线共享根提交
> （上面那个骨架），merge 正常。`tests/test_release.py` 里有断言守住这一点。

## ⚠️ 中间提交的状态

**发布线只保证三个锚点是测试干净的**：根提交（骨架）、#2 剪枝版 v0.1、`main` 的 tip。

**中间提交（#4~#7）不保证能通过完整测试**。原因：它们是把细粒度开发提交按
*内容主题*重新分组的（squash），晚期才出现的测试文件可能与早期模块落进同一棵树
（例如 `tests/test_w4_media.py` 引用了当时尚未加入的 `TableCell`）。

- 想 **bisect** 或逐提交验证，请用 `history/fine-grained`（细粒度，天然自洽）；
- 只关心"能跑、能发"的话，根 / 剪枝版 / tip 三个锚点已足够。

要让**每个**中间提交都测试干净，就只能在"细粒度"和"策展"之间二选一——
这里选择保留策展后的可读发布线，并把代价写清楚。

## 同步到远程

```bash
# 只推发布线（推荐）
git push -u origin main --follow-tags

# 连协作线与归档历史一起留存
git push origin main dev
git push origin refs/tags/history/fine-grained
```

> 只推 `main` 的话，`dev` 与归档 ref 都只留在本地。多数情况这就够了；
> 想保留完整过程就一并推。

## 改完代码后怎么提交

- **日常开发**：提交到 `dev`（粒度随意）。要同步发布线上的新改动时 `git merge main`。
- **要发布**：把 `dev` 的改动整理进 `main`——`git merge --squash`（压成一个）
  或 `git cherry-pick`（挑个别提交）都可以。
