def test_shared_executor_allows_ten_concurrent_tasks():
    from app.services import executor as executor_module

    executor_module.shutdown_executor(wait=False)
    pool = executor_module.get_executor()

    try:
        assert pool._max_workers == 10
    finally:
        executor_module.shutdown_executor(wait=False)
