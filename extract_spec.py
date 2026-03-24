import zipfile
import xml.etree.ElementTree as ET
import os

def extract_docx_text(docx_path):
    if not os.path.exists(docx_path):
        return f"File {docx_path} not found."
    try:
        with zipfile.ZipFile(docx_path, 'r') as zip_ref:
            if 'word/document.xml' not in zip_ref.namelist():
                return "No document.xml found"
            xml_content = zip_ref.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            texts = []
            for t in tree.findall('.//w:t', ns):
                if t.text:
                    texts.append(t.text)
            return "\n".join(texts)
    except Exception as e:
        return f"Error extracting text: {e}"

if __name__ == "__main__":
    path = r"c:\Users\jackie\Desktop\DSAMS\project specification file.docx"
    output_path = r"c:\Users\jackie\Desktop\DSAMS\extracted_spec.txt"
    text = extract_docx_text(path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Extracted text to {output_path}")
