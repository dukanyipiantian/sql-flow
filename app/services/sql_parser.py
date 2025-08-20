import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Comparison, Where
from sqlparse.tokens import Keyword, Name


def parse_sql(sql: str) -> dict:
    """增强版SQL解析器，修复字段和表提取问题"""
    parsed = sqlparse.parse(sql)[0]
    result = {
        "tables": set(),
        "columns": set(),
        "joins": [],
        "errors": []
    }

    # 提取所有标识符（表名和字段）
    for token in parsed.tokens:
        print(token)
        if isinstance(token, Identifier):
            _handle_identifier(token, parsed, result)
        elif token.is_keyword and token.value.upper() in ('FROM', 'JOIN', 'WHERE'):
            _handle_keyword_context(token, parsed, result)

    # 转换集合为列表
    result["tables"] = list(result["tables"])
    result["columns"] = list(result["columns"])
    return result


def _handle_identifier(token, statement, result):
    """处理标识符（表/字段）"""
    parent_keyword = token.parent and token.parent.value.upper()

    # 提取表名（FROM/JOIN 后的标识符）
    if parent_keyword in ('FROM', 'JOIN', 'INNER JOIN', 'LEFT JOIN'):
        table_name = token.get_real_name()
        if table_name and table_name.upper() not in ('SELECT', 'WHERE'):
            result["tables"].add(table_name)

    # 提取字段（SELECT/WHERE 后的标识符）
    elif parent_keyword in ('SELECT', 'WHERE', 'AND', 'OR'):
        if hasattr(token, 'get_real_name'):
            col = token.get_real_name()
            if col and '.' in col:  # 处理 u.id 形式的字段
                result["columns"].add(col.split('.')[-1])
            elif col:
                result["columns"].add(col)


def _handle_keyword_context(token, statement, result):
    """处理关键字上下文（WHERE/JOIN条件）"""
    if token.value.upper() == 'WHERE':
        for where_token in token.parent.tokens:
            if isinstance(where_token, Comparison):
                _extract_join_condition(where_token, result)


def _extract_join_condition(comparison, result):
    """从ON条件中提取JOIN关系"""
    if '=' in comparison.value:
        left, right = comparison.left, comparison.right
        if all(hasattr(t, 'get_real_name') for t in [left, right]):
            left_parts = left.value.split('.')
            right_parts = right.value.split('.')

            if len(left_parts) == 2 and len(right_parts) == 2:
                result["joins"].append({
                    "left_table": left_parts[0],
                    "left_column": left_parts[1],
                    "right_table": right_parts[0],
                    "right_column": right_parts[1]
                })