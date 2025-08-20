from flask import Blueprint, request, jsonify, current_app, render_template
from app.services.sql_parser import parse_sql
import traceback
import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Comparison


bp = Blueprint('api', __name__)


@bp.route('/')
def home():
    return render_template('index2.html')


@bp.route('/api/parse', methods=['POST'])
def parse_sql():
    data = request.get_json()
    if not data or 'sql' not in data:
        return jsonify({"success": False, "error": "需要提供SQL语句"}), 400

    try:
        sql = data['sql']
        parsed = sqlparse.parse(sql)[0]

        result = {
            "tables": set(),
            "columns": set(),
            "joins": [],
            "aliases": {}
        }

        # 提取表名和别名
        from_seen = join_seen = False
        current_tokens = []

        for token in parsed.tokens:
            print(f'token:{token}')
            if token.is_keyword:
                keyword = token.value.upper()
                if keyword in ('FROM', 'JOIN', 'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'CROSS JOIN', 'FULL JOIN'):
                    from_seen = (keyword == 'FROM')
                    join_seen = not from_seen
                    continue

            if from_seen or join_seen:
                if isinstance(token, Identifier):
                    # 处理表定义 (users u / orders AS o)
                    table_def = token.value
                    if " AS " in table_def.upper():
                        table, alias = [t.strip() for t in table_def.split(" AS ", 1)]
                    else:
                        parts = [p for p in table_def.split() if p]
                        table = parts[0]
                        alias = parts[1] if len(parts) > 1 else table

                    result["tables"].add(table)
                    result["aliases"][alias] = table
                    from_seen = join_seen = False

        # 提取JOIN条件
        for token in parsed.tokens:
            if isinstance(token, Comparison) and '=' in token.value:
                left, right = token.left, token.right
                if all(hasattr(t, 'value') for t in [left, right]):
                    left_parts = left.value.split('.')
                    right_parts = right.value.split('.')

                    if len(left_parts) == 2 and len(right_parts) == 2:
                        result["joins"].append({
                            "left_table": result["aliases"].get(left_parts[0], left_parts[0]),
                            "left_column": left_parts[1],
                            "right_table": result["aliases"].get(right_parts[0], right_parts[0]),
                            "right_column": right_parts[1]
                        })

        # 提取字段（包括SELECT *的情况）
        select_seen = False
        for token in parsed.tokens:
            if token.is_keyword and token.value.upper() == 'SELECT':
                select_seen = True
                continue

            if select_seen:
                if token.is_keyword:  # 遇到FROM等关键字结束SELECT部分
                    select_seen = False
                elif isinstance(token, IdentifierList):
                    for identifier in token.get_identifiers():
                        _process_column(identifier, result)
                elif isinstance(token, Identifier):
                    _process_column(token, result)

        # 处理SELECT * 的兜底逻辑（确保所有表都有.*字段）
        if '*' in sql.upper() and not any(col.endswith('.*') for col in result["columns"]):
            for table in result["tables"]:
                result["columns"].add(f"{table}.*")


        # 在 routes.py 中确保构建的 graph 数据一致
        def build_dependency_graph():
            graph = {"nodes": [], "links": []}

            # 添加节点（确保所有被引用的节点都存在）
            for table in result["tables"]:
                graph["nodes"].append({
                    "id": table,  # 确保这个ID与links中的引用一致
                    "type": "table",
                    "name": table
                })

            # 添加字段节点
            for column in result["columns"]:
                if '.' in column:
                    table, col = column.split('.')
                    graph["nodes"].append({
                        "id": column,  # 使用完整 table.column 作为ID
                        "type": "column",
                        "name": col,
                        "parent": table
                    })

            # 添加JOIN关系
            for join in result["joins"]:
                graph["links"].append({
                    "source": f"{join['left_table']}.{join['left_column']}",
                    "target": f"{join['right_table']}.{join['right_column']}",
                    "type": "join"
                })

            # 添加字段-表包含关系
            for table in result["tables"]:
                graph["links"].append({
                    "source": table,
                    "target": f"{table}.*",
                    "type": "contains"
                })

            return graph

        result["graph"] = build_dependency_graph()


        return jsonify({
            "code": 200,
            "success": True,
            "data": {
                "tables": list(result["tables"]),
                "columns": list(result["columns"]),
                "joins": result["joins"],
                "graph": result["graph"],
                "meta": {
                    "aliases": result["aliases"],
                    "has_wildcard": "*" in sql.upper()  # 标记是否包含SELECT *
                }
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"解析失败: {str(e)}",
            "traceback": traceback.format_exc() if current_app.config['DEBUG'] else None,
            "data": None
        }), 500


def _get_current_table_old(token, result):
    """获取字段所属的表名"""
    # 方法1：通过token的父节点分析
    parent = getattr(token, 'parent', None)
    while parent:
        if parent.is_keyword and parent.value.upper() in ('FROM', 'JOIN'):
            next_token = parent.next_token
            if isinstance(next_token, Identifier):
                table_def = next_token.value
                return result["aliases"].get(table_def.split()[-1], table_def.split()[0])
        parent = getattr(parent, 'parent', None)

    # 方法2：默认返回第一个表（保守策略）
    return list(result["tables"])[0] if result["tables"] else None


def _get_current_table(token, result):
    """精确获取字段所属表名"""
    # 情况1：字段带表别名前缀（如 u.id）
    if '.' in token.value:
        alias = token.value.split('.')[0]
        return result["aliases"].get(alias, alias)

    # 情况2：通过SQL解析树向上查找
    parent = getattr(token, 'parent', None)
    while parent:
        # 找到最近的FROM/JOIN子句
        if parent.is_keyword and parent.value.upper() in ('FROM', 'JOIN'):
            next_token = parent.next_token
            if isinstance(next_token, Identifier):
                table_def = next_token.value.split()
                return result["aliases"].get(table_def[-1], table_def[0])
        parent = getattr(parent, 'parent', None)

    # 情况3：通过WHERE条件关联判断
    if hasattr(token, 'parent') and isinstance(token.parent, Comparison):
        # 如果是JOIN条件中的字段（如 u.id = o.user_id）
        comparison = token.parent
        if '.' in comparison.left.value and '.' in comparison.right.value:
            left_table = comparison.left.value.split('.')[0]
            right_table = comparison.right.value.split('.')[0]
            return result["aliases"].get(left_table, left_table)

    # 保底方案：返回None由调用方处理
    return None


def _process_column_old(token, result):
    """处理字段提取，标准化为 表名.字段名 格式"""
    if hasattr(token, 'get_real_name'):
        col = token.get_real_name()

        # 处理通配符 *
        if col == '*':
            # 获取当前上下文中的表名（需先实现表上下文追踪）
            current_table = _get_current_table(token, result)
            if current_table:
                result["columns"].add(f"{current_table}.*")
            return

        # 处理普通字段
        if '.' in col:  # 已经是 table.column 格式
            table_alias, col_name = col.split('.')
            table = result["aliases"].get(table_alias, table_alias)
            result["columns"].add(f"{table}.{col_name}")
        else:  # 无表前缀的字段
            current_table = _get_current_table(token, result)
            if current_table:
                result["columns"].add(f"{current_table}.{col}")


def _process_column(token, result):
    """处理字段提取，确保表名准确性"""
    col = token.get_real_name()

    # 处理通配符 *
    if col == '*':
        current_table = _get_current_table(token, result)
        if current_table:
            result["columns"].add(f"{current_table}.*")
        return

    # 标准字段处理
    if '.' in col:  # 明确带表名的字段
        alias, col_name = col.split('.')
        table = result["aliases"].get(alias, alias)
        result["columns"].add(f"{table}.{col_name}")
    else:  # 无表名前缀的字段
        current_table = _get_current_table(token, result)
        if not current_table:
            # 尝试通过JOIN条件推断
            for join in result["joins"]:
                if f".{col}" in [join["left_column"], join["right_column"]]:
                    current_table = join["left_table"] if f".{col}" == join["left_column"] else join["right_table"]
                    break

        if current_table:
            result["columns"].add(f"{current_table}.{col}")
        else:
            # 最终保底：标记为未知来源
            result["columns"].add(f"unknown.{col}")