"""小医 · 医疗独特商业框架后端。"""

from .env_loader import load_env_file

# 必须早于 database/auth 等模块读取环境变量
load_env_file()
