# scripts/：按你的终端挑一个

六个入口，三组动作、两种 shell 风格、两个 PowerShell 版本。**行为一致**，
参数写法也一样（`--dev` / `--index` / `--proxy`）。

| 动作 | Git Bash / macOS / Linux | Windows PowerShell | cmd |
|---|---|---|---|
| 装依赖 | `bash scripts/setup.sh --dev` | `pwsh scripts/setup.ps1 --dev` 或<br>`powershell -File scripts\setup.ps1 --dev` | `scripts\setup.cmd --dev` |
| 打源码包 | `bash scripts/package.sh` | `pwsh scripts/package.ps1` 或<br>`powershell -File scripts\package.ps1` | `scripts\package.cmd` |

## PowerShell 版本

`.ps1` 同时支持 **Windows PowerShell 5.1**（Win10/11 自带）和 **PowerShell 7+**，
脚本开头用 `#Requires -Version 5.1` 声明了这个下限。差别只在细节：

- **编码**：`.ps1` 存成 **UTF-8 带 BOM**。5.1 读无 BOM 的脚本会按系统 ANSI
  代码页解码（中文 Windows 是 936），中文注释/输出会变乱码，甚至破坏引号导致语法错。
  `.cmd` 相反，**必须纯 ASCII、不能带 BOM**（cmd.exe 会把 BOM 当命令）。
- **tar.gz**：Windows 10+ 自带 `%SystemRoot%\System32\tar.exe`（bsdtar）。
  但 PATH 里只要 Git Bash / MSYS2 在前，`tar` 就会解析成 **GNU tar**——它把
  `C:\...` 当成远程主机名，报 `Cannot connect to C: resolve failed`。
  所以 `package.ps1` 总是优先用 System32 的 bsdtar，并用 `--version` 校验
  （含 `bsdtar`/`libarchive` 才用）。PowerShell 5.1 没有 .NET 的 `TarFile`，
  万一找不到 bsdtar 就只出 zip 并明确警告。
- **压缩**：`zip` 走 .NET 的 `System.IO.Compression.ZipFile`（5.1 需要 `Add-Type`，
  脚本里已显式加载）；tar.gz 见上。

## 为什么不用一个「legacy 专用」脚本

同一套逻辑维护两份，迟早会漂移（这个项目在三个平台变体上已经吃过一次亏：
`.cmd` 里的中文注释被 cmd.exe 按控制台代码页读成乱码当命令执行）。
所以做法是**让同一份脚本兼容两个版本**，并用测试守住两件容易回退的事：

- `tests/test_release.py`：`.ps1` 必须带 UTF-8 BOM、必须声明 `#Requires -Version 5.1`；
- 同上：`.cmd` 必须纯 ASCII（不能带 BOM）。
