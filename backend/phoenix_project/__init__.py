
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except Exception:
    # SQLite 本地模式或依赖未安装时允许项目继续启动。
    pass
