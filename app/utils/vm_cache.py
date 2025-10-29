import threading
import time 

# 虚拟机状态缓存机制
class VMStatusCache:
    def __init__(self):
        self.cache = {}
        self.cache_lock = threading.Lock()
        self.cache_timeout = 300  # 5分钟缓存过期时间
        self.wuma_cache_timeout = 600  # 五码信息10分钟缓存
        self.ju_cache_timeout = 600  # JU值信息10分钟缓存

    def get_cache_key(self, vm_name, cache_type):
        return f"{vm_name}_{cache_type}"

    def is_cache_valid(self, cache_entry):
        if not cache_entry:
            return False
        return time.time() - cache_entry['timestamp'] < cache_entry['timeout']

    def get_cached_status(self, vm_name, cache_type='online_status'):
        with self.cache_lock:
            cache_key = self.get_cache_key(vm_name, cache_type)
            cache_entry = self.cache.get(cache_key)
            if self.is_cache_valid(cache_entry):
                # logger.debug(f"使用缓存的{cache_type}数据: {vm_name}")
                return cache_entry['data']
            return None

    def set_cached_status(self, vm_name, data, cache_type='online_status'):
        with self.cache_lock:
            cache_key = self.get_cache_key(vm_name, cache_type)
            timeout = self.cache_timeout
            if cache_type == 'wuma_info':
                timeout = self.wuma_cache_timeout
            elif cache_type == 'ju_info':
                timeout = self.ju_cache_timeout

            self.cache[cache_key] = {
                'data': data,
                'timestamp': time.time(),
                'timeout': timeout
            }
        # logger.debug(f"缓存{cache_type}数据: {vm_name}")

    def clear_cache(self, vm_name=None, cache_type=None):
        with self.cache_lock:
            if vm_name and cache_type:
                cache_key = self.get_cache_key(vm_name, cache_type)
                self.cache.pop(cache_key, None)
            elif vm_name:
                # 清除指定虚拟机的所有缓存
                keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{vm_name}_")]
                for key in keys_to_remove:
                    self.cache.pop(key, None)
            else:
                # 清除所有缓存
                self.cache.clear()

    def cleanup_expired_cache(self):
        """清理过期的缓存条目"""
        with self.cache_lock:
            expired_keys = []
            for key, entry in self.cache.items():
                if not self.is_cache_valid(entry):
                    expired_keys.append(key)

            for key in expired_keys:
                self.cache.pop(key, None)

            if expired_keys:
                logger.debug(f"清理了 {len(expired_keys)} 个过期缓存条目")


# 全局缓存实例
vm_cache = VMStatusCache()


# 定期清理过期缓存的后台任务
def cache_cleanup_task():
    while True:
        time.sleep(600)  # 每10分钟清理一次
        vm_cache.cleanup_expired_cache()


# 启动缓存清理线程
cache_cleanup_thread = threading.Thread(target=cache_cleanup_task, daemon=True)
cache_cleanup_thread.start()