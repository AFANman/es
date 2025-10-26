"""
Redis缓存工具模块
用于处理活动数据的缓存存储和读取
"""

import json
import redis
import logging
from typing import Dict, List, Optional, Any
from datetime import timedelta

# 配置日志
logger = logging.getLogger(__name__)

class RedisCache:
    """Redis缓存管理类"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0, 
                 decode_responses: bool = True, password: Optional[str] = None):
        """
        初始化Redis连接
        
        Args:
            host: Redis服务器地址
            port: Redis端口
            db: 数据库编号
            decode_responses: 是否自动解码响应
            password: Redis密码
        """
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=decode_responses,
                password=password,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 测试连接
            self.redis_client.ping()
            logger.info("Redis连接成功")
        except redis.ConnectionError as e:
            logger.error(f"Redis连接失败: {e}")
            self.redis_client = None
        except Exception as e:
            logger.error(f"Redis初始化失败: {e}")
            self.redis_client = None
    
    def is_connected(self) -> bool:
        """检查Redis连接状态"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def save_events_data(self, session_id: str, events_data: List[Dict[str, Any]], 
                        expire_seconds: int = 3600) -> bool:
        """
        保存活动数据到Redis
        
        Args:
            session_id: 会话ID，用作缓存键
            events_data: 活动数据列表
            expire_seconds: 过期时间（秒），默认1小时
            
        Returns:
            bool: 保存是否成功
        """
        if not self.is_connected():
            logger.warning("Redis未连接，无法保存活动数据")
            return False
        
        try:
            cache_key = f"events:{session_id}"
            events_json = json.dumps(events_data, ensure_ascii=False)
            
            # 保存数据并设置过期时间
            self.redis_client.setex(cache_key, expire_seconds, events_json)
            
            logger.info(f"活动数据已保存到Redis，会话ID: {session_id}, 活动数量: {len(events_data)}")
            return True
            
        except Exception as e:
            logger.error(f"保存活动数据到Redis失败: {e}")
            return False
    
    def get_events_data(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        从Redis获取活动数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            Optional[List[Dict[str, Any]]]: 活动数据列表，如果不存在或出错则返回None
        """
        if not self.is_connected():
            logger.warning("Redis未连接，无法获取活动数据")
            return None
        
        try:
            cache_key = f"events:{session_id}"
            events_json = self.redis_client.get(cache_key)
            
            if events_json is None:
                logger.info(f"Redis中未找到会话ID为 {session_id} 的活动数据")
                return None
            
            events_data = json.loads(events_json)
            logger.info(f"从Redis获取活动数据成功，会话ID: {session_id}, 活动数量: {len(events_data)}")
            return events_data
            
        except json.JSONDecodeError as e:
            logger.error(f"解析Redis中的活动数据失败: {e}")
            return None
        except Exception as e:
            logger.error(f"从Redis获取活动数据失败: {e}")
            return None
    
    def delete_events_data(self, session_id: str) -> bool:
        """
        删除Redis中的活动数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 删除是否成功
        """
        if not self.is_connected():
            logger.warning("Redis未连接，无法删除活动数据")
            return False
        
        try:
            cache_key = f"events:{session_id}"
            result = self.redis_client.delete(cache_key)
            
            if result > 0:
                logger.info(f"Redis中会话ID为 {session_id} 的活动数据已删除")
                return True
            else:
                logger.info(f"Redis中未找到会话ID为 {session_id} 的活动数据")
                return False
                
        except Exception as e:
            logger.error(f"删除Redis中的活动数据失败: {e}")
            return False
    
    def get_all_session_keys(self) -> List[str]:
        """
        获取所有活动数据的会话键
        
        Returns:
            List[str]: 会话键列表
        """
        if not self.is_connected():
            return []
        
        try:
            keys = self.redis_client.keys("events:*")
            return [key.replace("events:", "") for key in keys]
        except Exception as e:
            logger.error(f"获取会话键列表失败: {e}")
            return []
    
    def clear_expired_data(self) -> int:
        """
        清理过期的活动数据（手动清理，Redis会自动过期）
        
        Returns:
            int: 清理的数据条数
        """
        if not self.is_connected():
            return 0
        
        try:
            keys = self.redis_client.keys("events:*")
            expired_keys = []
            
            for key in keys:
                ttl = self.redis_client.ttl(key)
                if ttl == -1:  # 没有设置过期时间的键
                    expired_keys.append(key)
            
            if expired_keys:
                deleted_count = self.redis_client.delete(*expired_keys)
                logger.info(f"清理了 {deleted_count} 个未设置过期时间的活动数据")
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"清理过期数据失败: {e}")
            return 0


# 全局Redis缓存实例
redis_cache = RedisCache()


def generate_session_id() -> str:
    """
    生成会话ID
    
    Returns:
        str: 基于时间戳的会话ID
    """
    import time
    import hashlib
    
    timestamp = str(int(time.time() * 1000))  # 毫秒时间戳
    return hashlib.md5(timestamp.encode()).hexdigest()[:16]


def save_events_to_cache(events_data: List[Dict[str, Any]], 
                        session_id: Optional[str] = None) -> Optional[str]:
    """
    保存活动数据到缓存的便捷函数
    
    Args:
        events_data: 活动数据列表
        session_id: 可选的会话ID，如果不提供则自动生成
        
    Returns:
        Optional[str]: 会话ID，如果保存失败则返回None
    """
    if session_id is None:
        session_id = generate_session_id()
    
    if redis_cache.save_events_data(session_id, events_data):
        return session_id
    return None


def get_events_from_cache(session_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    从缓存获取活动数据的便捷函数
    
    Args:
        session_id: 会话ID
        
    Returns:
        Optional[List[Dict[str, Any]]]: 活动数据列表
    """
    return redis_cache.get_events_data(session_id)