from translator.translator_utils import is_russian, sanitize_name, needs_content_based_name

def test_is_russian():
    assert is_russian("Привет, мир!")
    assert is_russian("This has some русский text.")
    assert not is_russian("Hello world!")
    assert not is_russian("1234567890")
    assert not is_russian("")

def test_sanitize_name():
    assert sanitize_name("file/name?yes*no") == "file_name_yes_no"
    assert sanitize_name("  hello  ") == "hello"
    assert sanitize_name("a"*300) == "a"*255
    assert sanitize_name("a"*255) == "a"*255
    assert sanitize_name("a....b") == "a.b"  # assuming repeats are stripped

def test_needs_content_based_name():
    assert needs_content_based_name("12345678-1234-1234-1234-123456789012")
    assert needs_content_based_name("a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6")
    assert needs_content_based_name("image12345678")
    assert not needs_content_based_name("vacation_photos")
    assert not needs_content_based_name("meeting_notes")
