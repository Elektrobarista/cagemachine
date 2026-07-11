"""Helper-Funktionen für die Anwendung"""
import html as _html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"_(.+?)_")


def _inline(text):
    """Escape + einfache Inline-Formatierung (**fett**, _kursiv_)"""
    out = _html.escape(text)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _ITALIC.sub(r"<em>\1</em>", out)
    return out


def render_help_markdown(md):
    """Winziger Markdown-Subset → HTML fürs Hilfe-Modal.
    '## Titel' = Abschnitt, '- Punkt' = Liste, '> Text' = dezenter Hinweis,
    Rest = Absatz. Roh-HTML wird escaped (nur erzeugte Tags sind aktiv)."""
    out = []
    in_list = False
    in_section = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in md.splitlines():
        line = raw.strip()
        if not line:
            close_list()
            continue
        if line.startswith("## "):
            close_list()
            if in_section:
                out.append("</div>")
            out.append('<div class="help-section">')
            out.append(f"<h3>{_inline(line[3:].strip())}</h3>")
            in_section = True
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(line[2:].strip())}</li>")
        elif line.startswith("> "):
            close_list()
            out.append(f'<p class="help-note">{_inline(line[2:].strip())}</p>')
        else:
            close_list()
            out.append(f"<p>{_inline(line)}</p>")

    close_list()
    if in_section:
        out.append("</div>")
    return "\n".join(out)


def format_duration(seconds):
    """
    Formatiert Sekunden zu einem lesbaren Zeitformat (MM:SS oder HH:MM:SS)
    
    Args:
        seconds: Dauer in Sekunden (float oder int)
    
    Returns:
        str: Formatierte Zeit als "MM:SS" oder "HH:MM:SS"
    """
    if seconds is None or seconds < 0:
        return "00:00"
    
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


