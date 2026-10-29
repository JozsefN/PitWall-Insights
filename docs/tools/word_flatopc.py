"""Preserve Word's complete document package when reading an open DOCX."""

from base64 import b64decode
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

PACKAGE_NS = 'http://schemas.microsoft.com/office/2006/xmlPackage'
CONTENT_TYPES_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'


def flatopc_to_docx(xml_path: Path, docx_path: Path) -> None:
    package = etree.parse(str(xml_path))
    content_types = etree.Element(f'{{{CONTENT_TYPES_NS}}}Types', nsmap={None: CONTENT_TYPES_NS})
    with ZipFile(docx_path, 'w', ZIP_DEFLATED) as archive:
        for part in package.findall(f'{{{PACKAGE_NS}}}part'):
            name = part.get(f'{{{PACKAGE_NS}}}name')
            content_type = part.get(f'{{{PACKAGE_NS}}}contentType')
            xml_data = part.find(f'{{{PACKAGE_NS}}}xmlData')
            binary_data = part.find(f'{{{PACKAGE_NS}}}binaryData')
            if xml_data is not None:
                payload = etree.tostring(xml_data[0], encoding='UTF-8', xml_declaration=True)
            elif binary_data is not None:
                payload = b64decode(''.join(binary_data.itertext()))
            else:
                raise ValueError(f'Missing package data: {name}')
            archive.writestr(name.lstrip('/'), payload)
            etree.SubElement(content_types, f'{{{CONTENT_TYPES_NS}}}Override', PartName=name, ContentType=content_type)
        archive.writestr('[Content_Types].xml', etree.tostring(content_types, encoding='UTF-8', xml_declaration=True))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('xml_path', type=Path)
    parser.add_argument('docx_path', type=Path)
    args = parser.parse_args()
    flatopc_to_docx(args.xml_path, args.docx_path)
