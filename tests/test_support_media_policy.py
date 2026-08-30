import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEEDBACK = ROOT / "handlers" / "feedback.py"


def _function_names(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_feedback_has_explicit_text_photo_pdf_and_rejection_handlers():
    names = _function_names(FEEDBACK)
    assert "process_feedback_text" in names
    assert "process_feedback_photo" in names
    assert "process_feedback_document" in names
    assert "reject_unsupported_feedback_input" in names


def test_feedback_has_strict_text_limit_and_metadata_only_pdf_boundary():
    source = FEEDBACK.read_text(encoding="utf-8")
    assert "MAX_TEXT_LENGTH = 200" in source
    assert "application/pdf" in source
    assert "MAX_UPLOAD_BYTES" in source
    assert "validate_image_payload" in source
    assert "validate_pdf_payload" not in source
    assert "message.document.file_size" in source


def test_feedback_does_not_use_unchecked_message_text_length():
    tree = ast.parse(FEEDBACK.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len":
            if node.args and isinstance(node.args[0], ast.Attribute):
                assert node.args[0].attr != "text"
