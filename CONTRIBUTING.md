# Contributing to Recursive Local Translator

Thank you for your interest in contributing! This document provides information on how the project is structured and how to run tests.

## For Developers

### Project Structure
- `translate_all.py`: The CLI entry point.
- `translator/`:
    - `translator_workspace.py`: Main orchestration logic.
    - `translate_client.py`: CTranslate2 engine and SQLite caching.
    - `pass_rename.py`: Filesystem renaming logic.
    - `handlers_*.py`: Specialized content handlers (Text, Office, Media).
- `tests/`: Comprehensive unit test suite using `pytest`.

### Running Tests
The project includes a suite of unit tests that use a mock translation client for fast, deterministic validation. To run the tests, ensure you have `pytest` installed:

```bash
python3 -m pytest tests/
```

### Coding Standards
- Keep files modular and under 200 lines where possible.
- Use `kebab-case` for module filenames.
- Ensure all new features include corresponding unit tests.
- Maintain compatibility with Python 3.8 - 3.12.
