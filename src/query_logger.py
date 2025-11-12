"""查询日志模块

记录每次查询的完整信息，包括：
- 用户查询
- 识别的实体
- 检索的路径
- LLM 回答
- 参考的路径
- 时间戳
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QueryLogger:
    """
    查询日志记录器
    """

    def __init__(self, log_dir: str = "logs"):
        """
        初始化日志记录器

        Args:
            log_dir: 日志文件存储目录
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        # 按日期创建日志文件
        today = datetime.now().strftime("%Y-%m-%d")
        self.json_log_file = os.path.join(log_dir, f"queries_{today}.jsonl")
        self.text_log_file = os.path.join(log_dir, f"queries_{today}.log")

    def log_query(self,
                  query: str,
                  center_entity: Optional[str],
                  all_paths: Optional[List[str]],
                  answer: str,
                  referenced_paths: Optional[List[str]],
                  graph_id: Optional[str] = None,
                  execution_time: Optional[float] = None,
                  error: Optional[str] = None) -> Dict[str, Any]:
        """
        记录一次查询的完整信息

        Args:
            query: 用户查询文本
            center_entity: 识别的中心实体
            all_paths: 检索到的所有推理路径
            answer: LLM 生成的答案
            referenced_paths: LLM 参考的路径
            graph_id: 图谱 ID
            execution_time: 执行时间（秒）
            error: 错误信息（如果有）

        Returns:
            记录的日志条目字典
        """
        timestamp = datetime.now()
        log_entry = {
            "timestamp": timestamp.isoformat(),
            "query": query,
            "graph_id": graph_id,
            "center_entity": center_entity,
            "all_paths_count": len(all_paths) if all_paths else 0,
            "all_paths": all_paths,
            "answer": answer,
            "referenced_paths_count": len(referenced_paths) if referenced_paths else 0,
            "referenced_paths": referenced_paths,
            "execution_time_seconds": execution_time,
            "error": error,
            "success": error is None
        }

        # 写入 JSONL 文件（每行一个 JSON 对象，方便流式读取和分析）
        try:
            with open(self.json_log_file, 'a', encoding='utf-8') as f:
                json.dump(log_entry, f, ensure_ascii=False)
                f.write('\n')
        except Exception as e:
            logger.error(f"Failed to write JSON log: {e}")

        # 写入文本日志（人类可读）
        try:
            with open(self.text_log_file, 'a', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"图谱ID: {graph_id}\n")
                f.write(f"查询: {query}\n")
                f.write(f"识别实体: {center_entity}\n")
                f.write(f"检索路径数: {len(all_paths) if all_paths else 0}\n")

                if all_paths and len(all_paths) > 0:
                    f.write(f"\n检索到的路径（前5条）:\n")
                    for i, path in enumerate(all_paths[:5], 1):
                        f.write(f"  {i}. {path}\n")

                f.write(f"\n答案: {answer}\n")
                f.write(f"参考路径数: {len(referenced_paths) if referenced_paths else 0}\n")

                if referenced_paths and len(referenced_paths) > 0:
                    f.write(f"\n参考的路径:\n")
                    for i, path in enumerate(referenced_paths, 1):
                        f.write(f"  {i}. {path}\n")

                if execution_time:
                    f.write(f"\n执行时间: {execution_time:.2f}秒\n")

                if error:
                    f.write(f"\n错误: {error}\n")

                f.write("=" * 80 + "\n\n")
        except Exception as e:
            logger.error(f"Failed to write text log: {e}")

        logger.info(f"Query logged: '{query}' -> Entity: {center_entity}")
        return log_entry

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取当天的查询统计信息

        Returns:
            统计信息字典
        """
        if not os.path.exists(self.json_log_file):
            return {
                "total_queries": 0,
                "successful_queries": 0,
                "failed_queries": 0,
                "average_execution_time": 0,
                "most_common_entities": []
            }

        total = 0
        successful = 0
        failed = 0
        execution_times = []
        entities = {}

        try:
            with open(self.json_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        total += 1

                        if entry.get('success'):
                            successful += 1
                        else:
                            failed += 1

                        if entry.get('execution_time_seconds'):
                            execution_times.append(entry['execution_time_seconds'])

                        entity = entry.get('center_entity')
                        if entity:
                            entities[entity] = entities.get(entity, 0) + 1
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to read statistics: {e}")

        # 计算平均执行时间
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0

        # 最常查询的实体（Top 5）
        most_common = sorted(entities.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_queries": total,
            "successful_queries": successful,
            "failed_queries": failed,
            "average_execution_time": avg_time,
            "most_common_entities": [{
                "entity": entity,
                "count": count
            } for entity, count in most_common]
        }


# 全局单例
_query_logger: Optional[QueryLogger] = None


def get_query_logger(log_dir: str = "logs") -> QueryLogger:
    """
    获取全局查询日志记录器实例

    Args:
        log_dir: 日志目录

    Returns:
        QueryLogger 实例
    """
    global _query_logger
    if _query_logger is None:
        _query_logger = QueryLogger(log_dir=log_dir)
    return _query_logger
