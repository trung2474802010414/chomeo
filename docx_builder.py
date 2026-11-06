import os
import sys
import zipfile
import html

def escape_xml(s):
    if s is None:
        return ""
    return html.escape(str(s))

class DocxBuilder:
    def __init__(self):
        self.body_xml = []
        
    def add_title(self, text, subtitle=None):
        self.body_xml.append(f'''
        <w:p>
          <w:pPr>
            <w:jc w:val="center"/>
            <w:spacing w:before="240" w:after="120"/>
          </w:pPr>
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
              <w:b/>
              <w:color w:val="1B365D"/>
              <w:sz w:val="40"/>
            </w:rPr>
            <w:t>{escape_xml(text)}</w:t>
          </w:r>
        </w:p>
        ''')
        if subtitle:
            self.body_xml.append(f'''
            <w:p>
              <w:pPr>
                <w:jc w:val="center"/>
                <w:spacing w:before="0" w:after="280"/>
              </w:pPr>
              <w:r>
                <w:rPr>
                  <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
                  <w:i/>
                  <w:color w:val="555555"/>
                  <w:sz w:val="24"/>
                </w:rPr>
                <w:t>{escape_xml(subtitle)}</w:t>
              </w:r>
            </w:p>
            ''')

    def add_meta_info(self, items):
        self.body_xml.append('''
        <w:tbl>
          <w:tblPr>
            <w:tblW w:w="9600" w:type="dxa"/>
            <w:tblBorders>
              <w:top w:val="single" w:sz="6" w:space="0" w:color="1B365D"/>
              <w:bottom w:val="single" w:sz="6" w:space="0" w:color="1B365D"/>
              <w:left w:val="none"/>
              <w:right w:val="none"/>
              <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
              <w:insideV w:val="none"/>
            </w:tblBorders>
          </w:tblPr>
        ''')
        for label, val in items:
            self.body_xml.append(f'''
            <w:tr>
              <w:tc>
                <w:tcPr>
                  <w:tcW w:w="3000" w:type="dxa"/>
                  <w:shd w:val="clear" w:color="auto" w:fill="F8FAFC"/>
                  <w:tcMar><w:top w:w="100" w:type="dxa"/><w:bottom w:w="100" w:type="dxa"/><w:left w:w="150" w:type="dxa"/></w:tcMar>
                </w:tcPr>
                <w:p><w:r><w:rPr><w:b/><w:color w:val="1B365D"/><w:sz w:val="22"/></w:rPr><w:t>{escape_xml(label)}</w:t></w:r></w:p>
              </w:tc>
              <w:tc>
                <w:tcPr>
                  <w:tcW w:w="6600" w:type="dxa"/>
                  <w:shd w:val="clear" w:color="auto" w:fill="FFFFFF"/>
                  <w:tcMar><w:top w:w="100" w:type="dxa"/><w:bottom w:w="100" w:type="dxa"/><w:left w:w="150" w:type="dxa"/></w:tcMar>
                </w:tcPr>
                <w:p><w:r><w:rPr><w:sz w:val="22"/><w:color w:val="222222"/></w:rPr><w:t>{escape_xml(val)}</w:t></w:r></w:p>
              </w:tc>
            </w:tr>
            ''')
        self.body_xml.append('</w:tbl>')
        self.add_spacer(160)

    def add_heading1(self, text):
        self.body_xml.append(f'''
        <w:p>
          <w:pPr>
            <w:spacing w:before="360" w:after="140"/>
            <w:pBdr>
              <w:bottom w:val="single" w:sz="12" w:space="4" w:color="1B365D"/>
            </w:pBdr>
          </w:pPr>
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
              <w:b/>
              <w:color w:val="1B365D"/>
              <w:sz w:val="30"/>
            </w:rPr>
            <w:t>{escape_xml(text)}</w:t>
          </w:r>
        </w:p>
        ''')

    def add_heading2(self, text):
        self.body_xml.append(f'''
        <w:p>
          <w:pPr>
            <w:spacing w:before="240" w:after="100"/>
          </w:pPr>
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
              <w:b/>
              <w:color w:val="D97706"/>
              <w:sz w:val="26"/>
            </w:rPr>
            <w:t>{escape_xml(text)}</w:t>
          </w:r>
        </w:p>
        ''')

    def add_heading3(self, text):
        self.body_xml.append(f'''
        <w:p>
          <w:pPr>
            <w:spacing w:before="180" w:after="60"/>
          </w:pPr>
          <w:r>
            <w:rPr>
              <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
              <w:b/>
              <w:color w:val="2C5282"/>
              <w:sz w:val="23"/>
            </w:rPr>
            <w:t>{escape_xml(text)}</w:t>
          </w:r>
        </w:p>
        ''')

    def add_paragraph(self, text, bold_prefix=None, italic=False, color="222222"):
        p_xml = ['<w:p><w:pPr><w:spacing w:before="60" w:after="80"/><w:jc w:val="both"/></w:pPr>']
        if bold_prefix:
            p_xml.append(f'<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:color w:val="1B365D"/><w:sz w:val="22"/></w:rPr><w:t>{escape_xml(bold_prefix)}</w:t></w:r>')
        
        i_tag = "<w:i/>" if italic else ""
        p_xml.append(f'<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>{i_tag}<w:color w:val="{color}"/><w:sz w:val="22"/></w:rPr><w:t>{escape_xml(text)}</w:t></w:r></w:p>')
        self.body_xml.append("".join(p_xml))

    def add_bullet(self, bold_label, text):
        self.body_xml.append(f'''
        <w:p>
          <w:pPr>
            <w:spacing w:before="40" w:after="60"/>
            <w:ind w:left="400" w:hanging="240"/>
          </w:pPr>
          <w:r>
            <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:color w:val="D97706"/><w:b/><w:sz w:val="22"/></w:rPr>
            <w:t>● </w:t>
          </w:r>
          <w:r>
            <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:color w:val="1B365D"/><w:sz w:val="22"/></w:rPr>
            <w:t>{escape_xml(bold_label)}: </w:t>
          </w:r>
          <w:r>
            <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:color w:val="333333"/><w:sz w:val="22"/></w:rPr>
            <w:t>{escape_xml(text)}</w:t>
          </w:r>
        </w:p>
        ''')

    def add_callout(self, text, bold_title="Điểm nhấn quan trọng"):
        self.body_xml.append(f'''
        <w:p>
          <w:pPr>
            <w:spacing w:before="120" w:after="140"/>
            <w:pBdr>
              <w:left w:val="single" w:sz="24" w:space="12" w:color="D97706"/>
            </w:pBdr>
            <w:shd w:val="clear" w:color="auto" w:fill="FFFBEB"/>
            <w:ind w:left="300" w:right="200"/>
          </w:pPr>
          <w:r>
            <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:color w:val="B45309"/><w:sz w:val="22"/></w:rPr>
            <w:t>📌 {escape_xml(bold_title)}: </w:t>
          </w:r>
          <w:r>
            <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:color w:val="451A03"/><w:sz w:val="22"/></w:rPr>
            <w:t>{escape_xml(text)}</w:t>
          </w:r>
        </w:p>
        ''')

    def add_table(self, headers, rows, col_widths=None):
        total_w = sum(col_widths) if col_widths else 9600
        self.body_xml.append(f'''
        <w:tbl>
          <w:tblPr>
            <w:tblW w:w="{total_w}" w:type="dxa"/>
            <w:tblBorders>
              <w:top w:val="single" w:sz="8" w:space="0" w:color="1B365D"/>
              <w:bottom w:val="single" w:sz="8" w:space="0" w:color="1B365D"/>
              <w:left w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
              <w:right w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
              <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
              <w:insideV w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
            </w:tblBorders>
            <w:tblCellMar>
              <w:top w:w="120" w:type="dxa"/>
              <w:left w:w="140" w:type="dxa"/>
              <w:bottom w:w="120" w:type="dxa"/>
              <w:right w:w="140" w:type="dxa"/>
            </w:tblCellMar>
          </w:tblPr>
        ''')

        # Header Row
        self.body_xml.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>')
        for idx, h in enumerate(headers):
            w = col_widths[idx] if col_widths and idx < len(col_widths) else 2400
            self.body_xml.append(f'''
            <w:tc>
              <w:tcPr>
                <w:tcW w:w="{w}" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="1B365D"/>
              </w:tcPr>
              <w:p>
                <w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="60"/></w:pPr>
                <w:r>
                  <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:color w:val="FFFFFF"/><w:sz w:val="22"/></w:rPr>
                  <w:t>{escape_xml(h)}</w:t>
                </w:r>
              </w:p>
            </w:tc>
            ''')
        self.body_xml.append('</w:tr>')

        # Data Rows
        for r_idx, r in enumerate(rows):
            bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            self.body_xml.append('<w:tr>')
            for c_idx, cell in enumerate(r):
                w = col_widths[c_idx] if col_widths and c_idx < len(col_widths) else 2400
                align = "center" if c_idx == 0 or c_idx == len(r)-1 else "left"
                self.body_xml.append(f'''
                <w:tc>
                  <w:tcPr>
                    <w:tcW w:w="{w}" w:type="dxa"/>
                    <w:shd w:val="clear" w:color="auto" w:fill="{bg_color}"/>
                  </w:tcPr>
                  <w:p>
                    <w:pPr><w:jc w:val="{align}"/><w:spacing w:before="40" w:after="40"/></w:pPr>
                    <w:r>
                      <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:color w:val="333333"/><w:sz w:val="21"/></w:rPr>
                      <w:t>{escape_xml(cell)}</w:t>
                    </w:r>
                  </w:p>
                </w:tc>
                ''')
            self.body_xml.append('</w:tr>')
        self.body_xml.append('</w:tbl>')
        self.add_spacer(140)

    def add_spacer(self, size_dxa=100):
        self.body_xml.append(f'''
        <w:p>
          <w:pPr><w:spacing w:before="{size_dxa}" w:after="0"/></w:pPr>
        </w:p>
        ''')

    def save(self, filepath):
        doc_xml_str = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {"".join(self.body_xml)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>'''

        content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

        root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

        word_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

        styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
        <w:sz w:val="22"/>
        <w:color w:val="222222"/>
      </w:rPr>
    </w:rPrDefault>
  </w:docDefaults>
</w:styles>'''

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('[Content_Types].xml', content_types)
            zf.writestr('_rels/.rels', root_rels)
            zf.writestr('word/_rels/document.xml.rels', word_rels)
            zf.writestr('word/styles.xml', styles_xml)
            zf.writestr('word/document.xml', doc_xml_str)
        print(f"Word document saved successfully to: {filepath}")

