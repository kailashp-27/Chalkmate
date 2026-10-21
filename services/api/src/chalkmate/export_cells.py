"""Keep teacher-authored strings literal when opened by spreadsheet software."""


def safe_cell(value):
    return (
        "'" + value
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
        else value
    )
