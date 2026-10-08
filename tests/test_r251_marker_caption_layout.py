from pathlib import Path
import re


def test_marker_caption_is_below_chord_band():
    css = Path('app/static/app.css').read_text()
    assert '.timeline-chord-lane' in css
    assert 'height:28px' in css
    assert re.search(r'\.project-marker-line \.project-marker-caption\s*\{[^}]*top:32px', css)
    assert '.project-marker-line .project-marker-handle' in css
