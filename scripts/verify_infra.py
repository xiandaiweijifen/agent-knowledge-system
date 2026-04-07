"""
Package 0 验证脚本：检查 Postgres 和 Redis 连接是否正常。
用法：python scripts/verify_infra.py
"""
import sys


def check_postgres():
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost", port=5432,
            user="postgres", password="password",
            dbname="agent_knowledge_system",
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        conn.close()
        print(f"[OK] Postgres: {version[:60]}")
        return True
    except Exception as e:
        print(f"[FAIL] Postgres: {e}")
        return False


def check_redis():
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0, socket_connect_timeout=3)
        r.ping()
        print("[OK] Redis: pong")
        return True
    except Exception as e:
        print(f"[FAIL] Redis: {e}")
        return False


if __name__ == "__main__":
    print("=== Package 0 基础设施验证 ===\n")
    pg_ok = check_postgres()
    redis_ok = check_redis()

    print()
    if pg_ok and redis_ok:
        print("全部通过，Package 0 完成！")
    else:
        print("有连接失败，请确认 docker-compose up -d 已运行。")
        sys.exit(1)
