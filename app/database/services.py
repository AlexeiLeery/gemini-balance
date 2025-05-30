"""
数据库服务模块
"""
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from sqlalchemy import func, desc, asc, select, insert, update, delete
import json
from app.database.connection import database
from app.database.models import Settings, ErrorLog, RequestLog
from app.log.logger import get_database_logger

logger = get_database_logger()


async def get_all_settings() -> List[Dict[str, Any]]:
    """
    获取所有设置
    
    Returns:
        List[Dict[str, Any]]: 设置列表
    """
    try:
        query = select(Settings)
        result = await database.fetch_all(query)
        return [dict(row) for row in result]
    except Exception as e:
        logger.error(f"Failed to get all settings: {str(e)}")
        raise


async def get_setting(key: str) -> Optional[Dict[str, Any]]:
    """
    获取指定键的设置
    
    Args:
        key: 设置键名
    
    Returns:
        Optional[Dict[str, Any]]: 设置信息，如果不存在则返回None
    """
    try:
        query = select(Settings).where(Settings.key == key)
        result = await database.fetch_one(query)
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"Failed to get setting {key}: {str(e)}")
        raise


async def update_setting(key: str, value: str, description: Optional[str] = None) -> bool:
    """
    更新设置
    
    Args:
        key: 设置键名
        value: 设置值
        description: 设置描述
    
    Returns:
        bool: 是否更新成功
    """
    try:
        # 检查设置是否存在
        setting = await get_setting(key)
        
        if setting:
            # 更新设置
            query = (
                update(Settings)
                .where(Settings.key == key)
                .values(
                    value=value,
                    description=description if description else setting["description"],
                    updated_at=datetime.now() # Use datetime.now()
                )
            )
            await database.execute(query)
            logger.info(f"Updated setting: {key}")
            return True
        else:
            # 插入设置
            query = (
                insert(Settings)
                .values(
                    key=key,
                    value=value,
                    description=description,
                    created_at=datetime.now(), # Use datetime.now()
                    updated_at=datetime.now() # Use datetime.now()
                )
            )
            await database.execute(query)
            logger.info(f"Inserted setting: {key}")
            return True
    except Exception as e:
        logger.error(f"Failed to update setting {key}: {str(e)}")
        return False


async def add_error_log(
    gemini_key: Optional[str] = None,
    model_name: Optional[str] = None,
    error_type: Optional[str] = None,
    error_log: Optional[str] = None,
    error_code: Optional[int] = None,
    request_msg: Optional[Union[Dict[str, Any], str]] = None
) -> bool:
    """
    添加错误日志
    
    Args:
        gemini_key: Gemini API密钥
        error_log: 错误日志
        error_code: 错误代码 (例如 HTTP 状态码)
        request_msg: 请求消息
    
    Returns:
        bool: 是否添加成功
    """
    try:
        # 如果request_msg是字典，则转换为JSON字符串
        if isinstance(request_msg, dict):
            request_msg_json = request_msg
        elif isinstance(request_msg, str):
            try:
                request_msg_json = json.loads(request_msg)
            except json.JSONDecodeError:
                request_msg_json = {"message": request_msg}
        else:
            request_msg_json = None
        
        # 插入错误日志
        query = (
            insert(ErrorLog)
            .values(
                gemini_key=gemini_key,
                error_type=error_type,
                error_log=error_log,
                model_name=model_name,
                error_code=error_code,
                request_msg=request_msg_json,
                request_time=datetime.now()
            )
        )
        await database.execute(query)
        logger.info(f"Added error log for key: {gemini_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to add error log: {str(e)}")
        return False


async def get_error_logs(
    limit: int = 20,
    offset: int = 0,
    key_search: Optional[str] = None,
    error_search: Optional[str] = None,
    error_code_search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    sort_by: str = 'id',        # 新增排序字段
    sort_order: str = 'desc'   # 新增排序顺序 ('asc' or 'desc')
) -> List[Dict[str, Any]]:
    """
    获取错误日志，支持搜索、日期过滤和排序

    Args:
        limit (int): 限制数量
        offset (int): 偏移量
        key_search (Optional[str]): Gemini密钥搜索词 (模糊匹配)
        error_search (Optional[str]): 错误类型或日志内容搜索词 (模糊匹配)
        error_code_search (Optional[str]): 错误码搜索词 (精确匹配)
        start_date (Optional[datetime]): 开始日期时间
        end_date (Optional[datetime]): 结束日期时间
        sort_by (str): 排序字段 (例如 'id', 'request_time')
        sort_order (str): 排序顺序 ('asc' or 'desc')

    Returns:
        List[Dict[str, Any]]: 错误日志列表
    """
    try:
        query = select(
            ErrorLog.id,
            ErrorLog.gemini_key,
            ErrorLog.model_name,
            ErrorLog.error_type,
            ErrorLog.error_log,
            ErrorLog.error_code,
            ErrorLog.request_time
        )
        
        # Apply filters
        if key_search:
            query = query.where(ErrorLog.gemini_key.ilike(f"%{key_search}%"))
        if error_search:
            query = query.where(
                (ErrorLog.error_type.ilike(f"%{error_search}%")) |
                (ErrorLog.error_log.ilike(f"%{error_search}%"))
            )
        if start_date:
            query = query.where(ErrorLog.request_time >= start_date)
        if end_date:
            # Use the datetime object directly for comparison
            query = query.where(ErrorLog.request_time < end_date)
        if error_code_search:
            try:
                # Attempt to convert search string to integer for exact match
                error_code_int = int(error_code_search)
                query = query.where(ErrorLog.error_code == error_code_int)
            except ValueError:
                # If conversion fails, log a warning and potentially skip this filter
                # or handle as needed (e.g., return no results for invalid code format)
                logger.warning(f"Invalid format for error_code_search: '{error_code_search}'. Expected an integer. Skipping error code filter.")
                # Optionally, force no results if the format is invalid:
                # query = query.where(False) # This ensures no rows are returned

        # 添加排序逻辑
        sort_column = getattr(ErrorLog, sort_by, ErrorLog.id) # 获取排序字段，默认为 id
        if sort_order.lower() == 'asc':
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        # Apply limit and offset
        query = query.limit(limit).offset(offset)

        result = await database.fetch_all(query)
        return [dict(row) for row in result]
    except Exception as e:
        logger.exception(f"Failed to get error logs with filters: {str(e)}") # Use exception for stack trace
        raise


async def get_error_logs_count(
    key_search: Optional[str] = None,
    error_search: Optional[str] = None,
    error_code_search: Optional[str] = None, # Added error code search
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> int:
    """
    获取符合条件的错误日志总数

    Args:
        key_search (Optional[str]): Gemini密钥搜索词 (模糊匹配)
        error_search (Optional[str]): 错误类型或日志内容搜索词 (模糊匹配)
        error_code_search (Optional[str]): 错误码搜索词 (精确匹配)
        start_date (Optional[datetime]): 开始日期时间
        end_date (Optional[datetime]): 结束日期时间

    Returns:
        int: 日志总数
    """
    try:
        query = select(func.count()).select_from(ErrorLog)

        # Apply the same filters as get_error_logs
        if key_search:
            query = query.where(ErrorLog.gemini_key.ilike(f"%{key_search}%"))
        if error_search:
            query = query.where(
                (ErrorLog.error_type.ilike(f"%{error_search}%")) |
                (ErrorLog.error_log.ilike(f"%{error_search}%"))
            )
        if start_date:
            query = query.where(ErrorLog.request_time >= start_date)
        if end_date:
            # Use the datetime object directly for comparison
            query = query.where(ErrorLog.request_time < end_date)
        if error_code_search:
            try:
                # Attempt to convert search string to integer for exact match
                error_code_int = int(error_code_search)
                query = query.where(ErrorLog.error_code == error_code_int)
            except ValueError:
                # If conversion fails, log a warning and potentially skip this filter
                logger.warning(f"Invalid format for error_code_search in count: '{error_code_search}'. Expected an integer. Skipping error code filter.")
                # Optionally, force count to 0 if the format is invalid:
                # return 0 # Or query = query.where(False) before fetching

        count_result = await database.fetch_one(query)
        return count_result[0] if count_result else 0
    except Exception as e:
        logger.exception(f"Failed to count error logs with filters: {str(e)}") # Use exception for stack trace
        raise


# 新增函数：获取单条错误日志详情
async def get_error_log_details(log_id: int) -> Optional[Dict[str, Any]]:
    """
    根据 ID 获取单个错误日志的详细信息

    Args:
        log_id (int): 错误日志的 ID

    Returns:
        Optional[Dict[str, Any]]: 包含日志详细信息的字典，如果未找到则返回 None
    """
    try:
        query = select(ErrorLog).where(ErrorLog.id == log_id)
        result = await database.fetch_one(query)
        if result:
            # 将 request_msg (JSONB) 转换为字符串以便在 API 中返回
            log_dict = dict(result)
            if 'request_msg' in log_dict and log_dict['request_msg'] is not None:
                # 确保即使是 None 或非 JSON 数据也能处理
                try:
                    log_dict['request_msg'] = json.dumps(log_dict['request_msg'], ensure_ascii=False, indent=2)
                except TypeError:
                    log_dict['request_msg'] = str(log_dict['request_msg']) # Fallback to string
            return log_dict
        else:
            return None
    except Exception as e:
        logger.exception(f"Failed to get error log details for ID {log_id}: {str(e)}")
        raise

# --- 异步删除函数 (使用 databases 库) ---

async def delete_error_logs_by_ids(log_ids: List[int]) -> int:
    """
    根据提供的 ID 列表批量删除错误日志 (异步)。

    Args:
        log_ids: 要删除的错误日志 ID 列表。

    Returns:
        int: 实际删除的日志数量。
    """
    if not log_ids:
        return 0
    try:
        # 使用 databases 执行删除
        query = delete(ErrorLog).where(ErrorLog.id.in_(log_ids))
        # execute 返回受影响的行数，但 databases 库的 execute 不直接返回 rowcount
        # 我们需要先查询是否存在，或者依赖数据库约束/触发器（如果适用）
        # 或者，我们可以执行删除并假设成功，除非抛出异常
        # 为了简单起见，我们执行删除并记录日志，不精确返回删除数量
        # 如果需要精确数量，需要先执行 SELECT COUNT(*)
        await database.execute(query)
        # 注意：databases 的 execute 不返回 rowcount，所以我们不能直接返回删除的数量
        # 返回 log_ids 的长度作为尝试删除的数量，或者返回 0/1 表示操作尝试
        logger.info(f"Attempted bulk deletion for error logs with IDs: {log_ids}")
        return len(log_ids) # 返回尝试删除的数量
    except Exception as e:
        # 数据库连接或执行错误
        logger.error(f"Error during bulk deletion of error logs {log_ids}: {e}", exc_info=True)
        raise # Re-raise the exception for the router to handle

async def delete_error_log_by_id(log_id: int) -> bool:
    """
    根据 ID 删除单个错误日志 (异步)。

    Args:
        log_id: 要删除的错误日志 ID。

    Returns:
        bool: 如果成功删除返回 True，否则返回 False。
    """
    try:
        # 先检查是否存在 (可选，但更明确)
        check_query = select(ErrorLog.id).where(ErrorLog.id == log_id)
        exists = await database.fetch_one(check_query)

        if not exists:
            logger.warning(f"Attempted to delete non-existent error log with ID: {log_id}")
            return False # 或者可以抛出 404 异常，由路由处理

        # 执行删除
        delete_query = delete(ErrorLog).where(ErrorLog.id == log_id)
        await database.execute(delete_query)
        logger.info(f"Successfully deleted error log with ID: {log_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting error log with ID {log_id}: {e}", exc_info=True)
        raise # Re-raise the exception for the router to handle

# --- RequestLog Services (保持异步) ---

# 新增函数：添加请求日志
async def add_request_log(
    model_name: Optional[str],
    api_key: Optional[str],
    is_success: bool,
    status_code: Optional[int] = None,
    latency_ms: Optional[int] = None,
    request_time: Optional[datetime] = None
) -> bool:
    """
    添加 API 请求日志

    Args:
        model_name: 模型名称
        api_key: 使用的 API 密钥
        is_success: 请求是否成功
        status_code: API 响应状态码
        latency_ms: 请求耗时(毫秒)
        request_time: 请求发生时间 (如果为 None, 则使用当前时间)

    Returns:
        bool: 是否添加成功
    """
    try:
        log_time = request_time if request_time else datetime.now()

        query = insert(RequestLog).values(
            request_time=log_time,
            model_name=model_name,
            api_key=api_key,
            is_success=is_success,
            status_code=status_code,
            latency_ms=latency_ms
        )
        await database.execute(query)
        # logger.debug(f"Added request log: key={api_key[:4]}..., success={is_success}, model={model_name}") # Use debug level
        return True
    except Exception as e:
        logger.error(f"Failed to add request log: {str(e)}")
        return False
