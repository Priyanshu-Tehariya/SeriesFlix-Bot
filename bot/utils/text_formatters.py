from __future__ import annotations


def format_file_size(size_bytes: int) -> str:
    """1572864 -> '1.50 MB'"""
    if size_bytes <= 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    idx = 0
    size = float(size_bytes)
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.2f} {units[idx]}"


def escape_markdown_v2(text: str) -> str:
    """Escape reserved MarkdownV2 characters for safe caption/message rendering."""
    reserved = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{ch}" if ch in reserved else ch for ch in text)


def truncate(text: str, max_len: int = 200, suffix: str = "…") -> str:
    """Truncate text to max_len characters, appending suffix if truncated."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def bold(text: str) -> str:
    """Wrap text in HTML bold tags."""
    return f"<b>{text}</b>"


def italic(text: str) -> str:
    """Wrap text in HTML italic tags."""
    return f"<i>{text}</i>"


def code(text: str) -> str:
    """Wrap text in HTML code tags."""
    return f"<code>{text}</code>"


def clean_language_display(language_str: str) -> str:
    """Strip 'Dual Audio' and 'Dual Audio,' from language strings."""
    if not language_str:
        return language_str
    
    # Replace the strings and clean up extra spaces/commas
    cleaned = language_str.replace("Dual Audio,", "").replace("Dual Audio", "")
    
    # Clean up any leftover commas and spaces
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    return ", ".join(parts)


def build_episode_caption(ep: dict, auto_delete_seconds: int = 0) -> str:
    """Build the episode caption, optionally appending a self-destruct countdown notice."""
    import html
    ep_label = f"Episode {ep['episode_number']:02d}" if ep.get("episode_number", 1) > 0 else "Complete Season"
    caption = (
        f"📺 {ep_label} [{ep.get('quality', '')}]\n"
        f"🌐 Language: {clean_language_display(ep.get('language', ''))}\n"
        f"💾 Size: {format_file_size(ep.get('file_size', 0))}\n"
        f"📁 <b>Filename:</b> <code>{html.escape(ep.get('raw_filename', ''))}</code>"
    )
    if auto_delete_seconds > 0:
        minutes = auto_delete_seconds // 60
        caption += (
            f"\n\n⚠️ <b>Note:</b> This file will automatically self-destruct in {minutes} minutes "
            "to prevent channel copyright strikes. Please save or forward it to your Saved Messages!"
        )
    return caption
