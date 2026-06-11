import sys
import os

# ── 必须在任何 hospital_gui 包代码之前执行 ─────────────────────────────────
import sys
import os

# python3 -m hospital_gui 从 hospital_gui/ 目录运行时，Python 把当前目录
# 加进 sys.path[0]，导致 "import hospital_gui.launch" 解析到
# 同目录下的 hospital_gui/ 子包（里面没有 launch.py）。
# 删掉这个误加的条目，让导入正确找到父目录下的包。
_cwd = os.getcwd()
_cwd_entry = os.path.join(_cwd, "hospital_gui")
if _cwd_entry in sys.path:
    sys.path.remove(_cwd_entry)

from .launch import main
main()
