import redis
from rq import Worker, Queue

redis_conn = redis.Redis(host="localhost", port=6379)
queue = Queue(connection=redis_conn)

if __name__ == "__main__":
    worker = Worker([queue], connection=redis_conn)
    worker.work()
