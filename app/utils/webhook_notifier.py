"""Webhook notification helpers for task completion.

Design goals:
- Keep VideoProcessor logic simple: a single call when task completes.
- Be robust: misconfiguration or network errors must never break task flow.
- Support Bark and WeCom (enterprise WeChat) with a small, explicit config surface.

Config layout (from config.yaml or runtime api_config):

webhook:
  enabled: false
  base_url: ""              # optional, e.g. "https://your-domain.com"
  bark:
    enabled: false
    server: "https://api.day.app"
    key: ""               # Bark device key
    group: "VideoWhisper" # optional Bark group
  wecom:
    enabled: false
    webhook_url: ""        # full robot webhook URL
    mentioned_mobile_list: []
    mentioned_userid_list: []
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

_DEFAULT_BARK_SERVER = "https://api.day.app"


def _merge_dict(base: Optional[Dict[str, Any]], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Shallow merge with one-level nested dict support.

    Values in override win; nested dicts are merged recursively.
    None in override does not erase base values.
    """

    result: Dict[str, Any] = dict(base or {})
    if not override:
        return result

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            nested = dict(result[key])
            nested.update(value)
            result[key] = nested
        elif value is not None:
            result[key] = value
    return result


def _build_task_brief(task: Any) -> str:
    """Return a short, human readable summary for notifications."""

    task_id = getattr(task, "id", "?")
    title = ""
    src_url = ""

    video_info = getattr(task, "video_info", None)
    if video_info and getattr(video_info, "title", None):
        title = str(video_info.title)
        src_url = getattr(video_info, "url", "") or getattr(task, "video_url", "")
    else:
        # Fallback to uploaded filename or bare task id
        original_filename = getattr(task, "original_filename", "")
        if original_filename:
            title = original_filename
        else:
            title = f"任务 {task_id}"
        src_url = getattr(task, "video_url", "")

    parts = [f"任务ID: {task_id}", f"标题: {title}"]
    if src_url:
        parts.append(f"来源: {src_url}")

    return "\n".join(parts)


class WebhookNotifier:
    """Send task completion notifications to configured webhooks.

    This class is intentionally small and dumb: it takes a plain dict config and
    never raises outwards. All failures are logged at warning level.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config: Dict[str, Any] = dict(config or {})

    def notify_task_completed(self, task: Any) -> None:
        """Send notifications for a completed task if enabled.

        If webhook is disabled, misconfigured, or task is not completed, this
        is a no-op.
        """

        status = getattr(task, "status", "")
        if status != "completed":
            # Keep behaviour explicit: we only notify on completed tasks.
            logger.debug("skip webhook: task %s status=%s", getattr(task, "id", "?"), status)
            return

        cfg = self._config or {}
        if not cfg.get("enabled", False):
            return

        base_url = (cfg.get("base_url") or "").strip() or None
        task_url = None
        if base_url:
            # Best-effort: avoid double slashes.
            task_url = base_url.rstrip("/") + "/"
            task_url += f"?task_id={getattr(task, 'id', '')}"

        bark_cfg = cfg.get("bark") or {}
        wecom_cfg = cfg.get("wecom") or {}

        brief = _build_task_brief(task)
        title = bark_cfg.get("title") or "VideoWhisper 任务完成"

        if bark_cfg.get("enabled"):
            self._send_bark(bark_cfg, title=title, body=brief, task_url=task_url, task_id=getattr(task, "id", ""))

        if wecom_cfg.get("enabled"):
            self._send_wecom(wecom_cfg, title=title, body=brief, task_url=task_url, task_id=getattr(task, "id", ""))

    # Provider specific helpers -------------------------------------------------

    def _send_bark(
        self,
        cfg: Dict[str, Any],
        *,
        title: str,
        body: str,
        task_url: Optional[str],
        task_id: str,
    ) -> None:
        """Send Bark notification.

        Bark uses a simple HTTP endpoint; we always treat errors as non-fatal.
        """

        key = (cfg.get("key") or cfg.get("token") or "").strip()
        if not key:
            logger.warning("Bark webhook enabled but key is empty; skip")
            return

        server = (cfg.get("server") or _DEFAULT_BARK_SERVER).strip() or _DEFAULT_BARK_SERVER
        server = server.rstrip("/")

        try:
            from urllib.parse import quote

            # 大多数 Bark 部署支持 `/{key}/{body}` 形式，这里将标题合并进正文，避免路径
            # 段数不兼容导致 404。
            body_text = f"{title}\n\n{body}" if title else body
            encoded_body = quote(body_text)
            url = f"{server}/{key}/{encoded_body}"

            params: Dict[str, Any] = {}
            group = (cfg.get("group") or "").strip()
            if group:
                params["group"] = group
            if task_url:
                params["url"] = task_url

            timeout = float(cfg.get("timeout", 5))
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code >= 400:
                logger.warning(
                    "Bark webhook for task %s GET failed: %s %s", task_id, resp.status_code, resp.text[:200]
                )
                # 尝试兼容自建 bark-server 的 /push 接口
                try:
                    push_url = f"{server}/push"
                    payload: Dict[str, Any] = {
                        "body": body_text,
                        "device_key": key,
                    }
                    if group:
                        payload["group"] = group
                    if task_url:
                        payload["url"] = task_url
                    post_resp = requests.post(push_url, json=payload, timeout=timeout)
                    if post_resp.status_code >= 400:
                        logger.warning(
                            "Bark webhook for task %s POST /push failed: %s %s",
                            task_id,
                            post_resp.status_code,
                            post_resp.text[:200],
                        )
                except Exception as exc2:
                    logger.warning("Bark webhook for task %s POST /push raised error: %s", task_id, exc2)
        except Exception as exc:  # pragma: no cover - failure path is logged only
            logger.warning("Bark webhook for task %s raised error: %s", task_id, exc)

    def _send_wecom(
        self,
        cfg: Dict[str, Any],
        *,
        title: str,
        body: str,
        task_url: Optional[str],
        task_id: str,
    ) -> None:
        """Send Enterprise WeChat (WeCom) robot notification."""

        webhook_url = (cfg.get("webhook_url") or "").strip()
        if not webhook_url:
            logger.warning("WeCom webhook enabled but webhook_url is empty; skip")
            return

        lines = [title, "", body]
        if task_url:
            lines.extend(["", f"结果链接: {task_url}"])
        content = "\n".join(lines)

        payload: Dict[str, Any] = {
            "msgtype": "text",
            "text": {
                "content": content,
            },
        }

        mobiles = cfg.get("mentioned_mobile_list") or cfg.get("mobiles") or []
        userids = cfg.get("mentioned_userid_list") or cfg.get("userids") or []
        if mobiles:
            payload["text"]["mentioned_mobile_list"] = list(mobiles)
        if userids:
            payload["text"]["mentioned_userid_list"] = list(userids)

        try:
            timeout = float(cfg.get("timeout", 5))
            resp = requests.post(webhook_url, json=payload, timeout=timeout)
            if resp.status_code != 200:
                logger.warning(
                    "WeCom webhook for task %s failed: %s %s", task_id, resp.status_code, resp.text[:200]
                )
        except Exception as exc:  # pragma: no cover - failure path is logged only
            logger.warning("WeCom webhook for task %s raised error: %s", task_id, exc)


def send_task_completed_webhooks(
    task: Any,
    base_config: Optional[Dict[str, Any]] = None,
    runtime_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Convenience entrypoint used by VideoProcessor.

    base_config comes from config.yaml; runtime_config is passed from api_config
    (settings page). runtime_config overrides base_config in case of overlap.
    """

    merged = _merge_dict(base_config, runtime_config)
    notifier = WebhookNotifier(merged)
    notifier.notify_task_completed(task)
