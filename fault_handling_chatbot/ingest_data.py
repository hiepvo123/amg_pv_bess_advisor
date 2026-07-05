import os
import sys
import docx2txt

sys.stdout.reconfigure(encoding='utf-8')
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

def extract_text_from_docx(file_path):
    """Đọc text từ file Word bằng docx2txt để tránh lỗi lxml XMLSyntaxError"""
    text = docx2txt.process(file_path)
    # Loại bỏ các dòng trống thừa
    return '\n'.join([line for line in text.split('\n') if line.strip()])

def process_and_ingest():
    # 1. Khai báo model Embeddings siêu nhẹ chạy Local
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # 2. Map tài liệu text với các bản vẽ sơ đồ trong file Appendix
    # Lưu ý: Các file ảnh như 'A1_circuit.png' phải được lưu sẵn trong thư mục static/images/
    files_mapping = {
        "data/CHAPTER 5 16-03.docx": "A1_circuit.png",
        "data/CHAPTER 7 17-03.docx": "A2_panel.png",
        "data/CHAPTER 10 13-03.docx": "A3_combiner_box.png"
    }
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    docs = []

    print("Đang đọc và cắt nhỏ tài liệu...")
    for text_file, image_file in files_mapping.items():
        if os.path.exists(text_file):
            text_content = extract_text_from_docx(text_file)
            chunks = text_splitter.split_text(text_content)
            
            for chunk in chunks:
                docs.append(Document(
                    page_content=chunk,
                    metadata={
                        "source": text_file,
                        # Tạo URL tĩnh để Frontend có thể lấy ảnh hiển thị
                        "diagram_image_url": f"http://127.0.0.1:8000/static/images/{image_file}"
                    }
                ))
        else:
            print(f"[Cảnh báo] Không tìm thấy file {text_file}")

    if not docs:
        print("Không có dữ liệu để xử lý.")
        return

    # 3. Khởi tạo và lưu vào ChromaDB
    print("Đang nhúng (Embedding) và tạo Vector Database...")
    vector_db = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory="./chroma_db_v2"
    )
    print(f"Hoàn tất! Đã nạp {len(docs)} chunks dữ liệu.")

if __name__ == "__main__":
    process_and_ingest()
