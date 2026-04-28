import io
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Tuple

from .handlers_base import BaseHandler


class EbookHandler(BaseHandler):
    def translate_epub_inplace(self, path: Path) -> bool:
        try:
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                if "META-INF/container.xml" not in names:
                    return False
                container_xml = zf.read("META-INF/container.xml")
                opf_path = self._find_opf_path(container_xml)
                if not opf_path or opf_path not in names:
                    return False

                opf_xml = zf.read(opf_path)
                content_docs = self._find_epub_content_docs(opf_xml, opf_path)
                toc_docs = self._find_toc_docs(opf_xml, opf_path)
                targets = set(content_docs + toc_docs)
                if not targets:
                    return False

                files = []
                changed = False
                for info in zf.infolist():
                    data = zf.read(info.filename)
                    if info.filename in targets:
                        translated_data, did_change = self._translate_xhtml_bytes(data)
                        if did_change:
                            data = translated_data
                            changed = True
                    files.append((info, data))
        except Exception as e:
            print(f"  Warning: EPUB read error: {path}: {e}")
            return False

        if not changed:
            return False

        try:
            with tempfile.NamedTemporaryFile(
                suffix=path.suffix, dir=path.parent, delete=False
            ) as tmp_fh:
                tmp_path = Path(tmp_fh.name)
            try:
                with zipfile.ZipFile(tmp_path, "w") as out:
                    # EPUB spec: mimetype must be first and stored (no compression)
                    mimetype_entry = next(
                        (pair for pair in files if pair[0].filename == "mimetype"), None
                    )
                    if mimetype_entry:
                        _, data = mimetype_entry
                        mime_info = zipfile.ZipInfo("mimetype")
                        mime_info.compress_type = zipfile.ZIP_STORED
                        out.writestr(mime_info, data)
                    for info, data in files:
                        if info.filename == "mimetype":
                            continue
                        new_info = zipfile.ZipInfo(info.filename)
                        new_info.date_time = info.date_time
                        new_info.external_attr = info.external_attr
                        new_info.compress_type = info.compress_type
                        new_info.comment = info.comment
                        new_info.extra = info.extra
                        out.writestr(new_info, data)
                shutil.move(str(tmp_path), str(path))
            except Exception:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            return True
        except Exception as e:
            print(f"  Warning: EPUB write error: {path}: {e}")
            return False

    def _find_opf_path(self, container_xml: bytes) -> Optional[str]:
        try:
            root = ET.fromstring(container_xml)
        except Exception:
            return None
        for node in root.iter():
            if node.tag.endswith("rootfile"):
                full_path = node.attrib.get("full-path")
                if full_path:
                    return full_path
        return None

    def _find_epub_content_docs(self, opf_xml: bytes, opf_path: str) -> List[str]:
        try:
            root = ET.fromstring(opf_xml)
        except Exception:
            return []
        base = str(Path(opf_path).parent)
        docs = []
        for item in root.iter():
            if not item.tag.endswith("item"):
                continue
            media_type = (item.attrib.get("media-type") or "").lower()
            href = item.attrib.get("href")
            if not href:
                continue
            if media_type in {
                "application/xhtml+xml",
                "text/html",
                "application/x-dtbncx+xml",
            }:
                docs.append(str((Path(base) / href).as_posix()))
        return docs

    def _find_toc_docs(self, opf_xml: bytes, opf_path: str) -> List[str]:
        try:
            root = ET.fromstring(opf_xml)
        except Exception:
            return []
        base = str(Path(opf_path).parent)
        docs = []
        for item in root.iter():
            if not item.tag.endswith("reference"):
                continue
            href = item.attrib.get("href")
            if href:
                docs.append(str((Path(base) / href).as_posix()))
        return docs

    def _translate_xhtml_bytes(self, data: bytes) -> Tuple[bytes, bool]:
        try:
            root = ET.fromstring(data)
        except Exception:
            return data, False

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

        if not changed:
            return data, False

        out = io.BytesIO()
        ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
        return out.getvalue(), True
