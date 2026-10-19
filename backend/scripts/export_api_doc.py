"""从 FastAPI OpenAPI 导出接口参考文档。

运行后写入 docs/api-reference.md；接口改动后重新执行即可同步，
避免手写文档与代码脱节。运行时交互式文档仍以 /docs 为准。

用法：
    python backend/scripts/export_api_doc.py
    python backend/scripts/export_api_doc.py --out docs/api-reference.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

METHOD_ORDER = ["get", "post", "put", "patch", "delete", "head", "options"]
TAG_LABELS = {
    "auth": "登录与账号",
    "users": "用户",
    "notices": "通知公告",
    "notifications": "站内通知",
    "courses": "课程与课时",
    "service-products": "服务商品",
    "mall": "商城",
    "reminders": "提醒",
    "schedule": "课表与校历",
    "community": "社区",
    "friends": "好友与消息",
    "materials": "资料",
    "grades": "成绩",
    "links": "关联信息",
    "hospital": "医院对接",
    "ai": "AI 用药检测",
    "home": "首页",
    "admin": "管理中心",
}


def schema_name(schema: dict | None) -> str:
    if not schema:
        return "-"
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "items" in schema:
        return "array<" + schema_name(schema["items"]) + ">"
    if "anyOf" in schema:
        return " | ".join(schema_name(x) for x in schema["anyOf"])
    if "allOf" in schema:
        return " & ".join(schema_name(x) for x in schema["allOf"])
    kind = schema.get("type", "-")
    if kind == "array":
        return "array<" + schema_name(schema.get("items")) + ">"
    return kind


def type_label(prop: dict) -> str:
    text = schema_name(prop)
    if prop.get("format"):
        text += f" ({prop['format']})"
    if prop.get("enum"):
        text += " / " + "、".join(str(x) for x in prop["enum"])
    return text


def clean(text: str | None, limit: int = 120) -> str:
    if not text:
        return ""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def auth_label(operation: dict) -> str:
    security = operation.get("security")
    if not security:
        return "公开"
    return "需要登录"


def collect_operations(spec: dict):
    grouped: dict[str, list[tuple[str, str, dict]]] = {}
    schemas_used: set[str] = set()
    for path, methods in spec.get("paths", {}).items():
        for method, operation in methods.items():
            if method not in METHOD_ORDER:
                continue
            tag = (operation.get("tags") or ["其他"])[0]
            grouped.setdefault(tag, []).append((path, method, operation))
            for param in operation.get("parameters", []):
                if "$ref" in param.get("schema", {}):
                    schemas_used.add(param["schema"]["$ref"].rsplit("/", 1)[-1])
            body = operation.get("requestBody", {})
            for content in body.get("content", {}).values():
                name = schema_name(content.get("schema"))
                if name not in ("-", "object"):
                    schemas_used.add(name.removeprefix("array<").removesuffix(">"))
            for response in operation.get("responses", {}).values():
                for content in response.get("content", {}).values():
                    name = schema_name(content.get("schema"))
                    if name not in ("-", "object"):
                        schemas_used.add(name.removeprefix("array<").removesuffix(">"))
    for items in grouped.values():
        items.sort(key=lambda x: (x[0], METHOD_ORDER.index(x[1])))
    return grouped, schemas_used


def render_operation(path: str, method: str, operation: dict) -> list[str]:
    lines = []
    summary = clean(operation.get("summary") or operation.get("description"), 100)
    title = f"`{method.upper()} {path}`"
    lines.append(f"- {title}" + (f" — {summary}" if summary else ""))
    detail = clean(operation.get("description"), 200)
    if detail and detail != summary:
        lines.append(f"  - 说明：{detail}")
    lines.append(f"  - 认证：{auth_label(operation)}")
    params = []
    for param in operation.get("parameters", []):
        if "$ref" in param:
            continue
        schema = param.get("schema", {})
        required = "必填" if param.get("required") else "可选"
        params.append(
            f"`{param.get('in')}.{param.get('name')}`（{type_label(schema)}，{required}）"
        )
    if params:
        lines.append("  - 参数：" + "；".join(params))
    body = operation.get("requestBody", {})
    if body:
        for content_type, content in body.get("content", {}).items():
            required = "必填" if body.get("required") else "可选"
            lines.append(
                f"  - 请求体：`{content_type}` {schema_name(content.get('schema'))}（{required}）"
            )
    responses = []
    for code, response in sorted(operation.get("responses", {}).items()):
        name = "-"
        for content in response.get("content", {}).values():
            name = schema_name(content.get("schema"))
            break
        desc = clean(response.get("description"), 40)
        responses.append(f"`{code}` {name}" + (f"（{desc}）" if desc else ""))
    if responses:
        lines.append("  - 响应：" + "；".join(responses))
    return lines


def render_schemas(spec: dict, names: set[str]) -> list[str]:
    schemas = spec.get("components", {}).get("schemas", {})
    lines = []
    for name in sorted(names):
        schema = schemas.get(name)
        if not schema:
            continue
        required = set(schema.get("required", []))
        lines.append(f"### {name}")
        description = clean(schema.get("description"), 200)
        if description:
            lines.append("")
            lines.append(description)
        lines.append("")
        lines.append("| 字段 | 类型 | 必填 | 说明 |")
        lines.append("|------|------|------|------|")
        for field, prop in schema.get("properties", {}).items():
            note = clean(prop.get("description") or prop.get("title"), 80)
            default = prop.get("default")
            if default not in (None, "", [], {}):
                note = (note + "；" if note else "") + f"默认 `{default}`"
            lines.append(
                f"| `{field}` | {type_label(prop)} | {'是' if field in required else '否'} | {note} |"
            )
        lines.append("")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO / "docs" / "api-reference.md"))
    args = parser.parse_args()

    from app.main import app  # noqa: PLC0415  (需先加入 sys.path)

    spec = app.openapi()
    grouped, schemas_used = collect_operations(spec)
    total = sum(len(v) for v in grouped.values())

    lines = [
        "# 小医后端接口参考",
        "",
        "> 本文件由 `backend/scripts/export_api_doc.py` 根据 FastAPI OpenAPI",
        "> 自动生成，请勿手工编辑。接口变更后重新执行脚本即可同步。",
        "> 交互式文档（可试调用）以启动后的 `/docs` 为准。",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 接口总数：{total}",
        f"- OpenAPI 版本：{spec.get('openapi')}",
        "",
        "## 认证方式",
        "",
        "除标注为「公开」的接口外，均需在请求头携带登录返回的 JWT：",
        "",
        "```http",
        "Authorization: Bearer <access_token>",
        "```",
        "",
        "令牌通过 `POST /api/auth/login` 获取，有效期由",
        "`ACCESS_TOKEN_EXPIRE_MINUTES` 控制。",
        "",
        "## 模块索引",
        "",
    ]
    for tag in sorted(grouped):
        label = TAG_LABELS.get(tag, tag)
        lines.append(f"- [{label}（{len(grouped[tag])}）](#{tag})")
    lines.append("")

    for tag in sorted(grouped):
        label = TAG_LABELS.get(tag, tag)
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"<a id=\"{tag}\"></a>")
        lines.append("")
        for path, method, operation in grouped[tag]:
            lines.extend(render_operation(path, method, operation))
        lines.append("")

    lines.append("## 数据结构")
    lines.append("")
    lines.extend(render_schemas(spec, schemas_used))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"已生成 {out}：{total} 个接口，{len(schemas_used)} 个数据结构")


if __name__ == "__main__":
    main()
