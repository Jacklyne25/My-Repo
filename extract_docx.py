
import zipfile
import xml.etree.ElementTree as ET
import os

def extract_docx_text(docx_path):
    if not os.path.exists(docx_path):
        return f"File {docx_path} not found."
    
    try:
        with zipfile.ZipFile(docx_path, 'r') as zip_ref:
            xml_content = zip_ref.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            
            # Basic extraction - findings all 't' tags which contain text
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            texts = []
            for t in tree.findall('.//w:t', ns):
                if t.text:
                    texts.append(t.text)
            
            return "\n".join(texts)
    except Exception as e:
        return f"Error extracting text: {e}"

if __name__ == "__main__":
    path = r"c:\Users\jackie\Desktop\DSAMS\Proposed Authentication Flow for DSAMS.docx"
    output_path = r"c:\Users\jackie\Desktop\DSAMS\extracted_auth_flow.txt"
    text = extract_docx_text(path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Extracted text to {output_path}")
