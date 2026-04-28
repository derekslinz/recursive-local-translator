import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from .translator_utils import is_russian
from .handlers_base import BaseHandler


class TextHandler(BaseHandler):
    def translate_text_inplace(self, path: Path) -> bool:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"  Warning: Read error: {path}: {e}")
            return False

        translated = self.translate_text_if_russian(content)
        if translated is None:
            return False

        try:
            path.write_text(translated, encoding="utf-8")
            return True
        except Exception as e:
            print(f"  Warning: Write error: {path}: {e}")
            return False

    def translate_csv_inplace(self, path: Path) -> bool:
        dialect = csv.excel
        rows = []
        changed = False

        try:
            with path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
                sample = fh.read(4096)
                fh.seek(0)
                if sample.strip():
                    try:
                        dialect = csv.Sniffer().sniff(sample)
                    except csv.Error:
                        pass
                reader = csv.reader(fh, dialect)
                for row in reader:
                    new_row = []
                    for cell in row:
                        translation = self.translate_text_if_russian(cell)
                        if translation is not None and translation != cell:
                            new_row.append(translation)
                            changed = True
                        else:
                            new_row.append(cell)
                    rows.append(new_row)
        except Exception as e:
            print(f"  Warning: CSV read error: {path}: {e}")
            return False

        if not changed:
            return False

        try:
            with path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh, dialect)
                writer.writerows(rows)
            return True
        except Exception as e:
            print(f"  Warning: CSV write error: {path}: {e}")
            return False

    def translate_json_inplace(self, path: Path) -> bool:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            data = json.loads(content)
        except Exception as e:
            print(f"  Warning: JSON parse error: {path}: {e}")
            return False

        translated_data, changed = self._translate_json_value(data)
        if not changed:
            return False

        try:
            serialized = json.dumps(translated_data, ensure_ascii=False, indent=2)
            path.write_text(serialized + "\n", encoding="utf-8")
            return True
        except Exception as e:
            print(f"  Warning: JSON write error: {path}: {e}")
            return False

    def _translate_json_value(self, value):
        if isinstance(value, str):
            translation = self.translate_text_if_russian(value)
            if translation is not None:
                return translation, translation != value
            return value, False

        if isinstance(value, list):
            new_list = []
            changed = False
            for item in value:
                translated_item, item_changed = self._translate_json_value(item)
                new_list.append(translated_item)
                changed = changed or item_changed
            return new_list, changed

        if isinstance(value, dict):
            new_dict = {}
            changed = False
            for k, item in value.items():
                translated_item, item_changed = self._translate_json_value(item)
                new_dict[k] = translated_item
                changed = changed or item_changed
            return new_dict, changed

        return value, False

    def translate_fb2_inplace(self, path: Path) -> bool:
        return self.translate_xml_inplace(path)

    def translate_xml_inplace(self, path: Path) -> bool:
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except Exception as e:
            print(f"  Warning: XML parse error: {path}: {e}")
            return False

        changed = self.translate_xml_root(root)
        if not changed:
            return False

        try:
            tree.write(path, encoding="utf-8", xml_declaration=True)
            return True
        except Exception as e:
            print(f"  Warning: XML write error: {path}: {e}")
            return False

    def translate_xml_root(self, root: ET.Element) -> bool:
        changed = False
        for node in root.iter():
            if node.text:
                new_text = self.translate_text_if_russian(node.text)
                if new_text is not None and new_text != node.text:
                    node.text = new_text
                    changed = True
            if node.tail:
                new_tail = self.translate_text_if_russian(node.tail)
                if new_tail is not None and new_tail != node.tail:
                    node.tail = new_tail
                    changed = True
        return changed
