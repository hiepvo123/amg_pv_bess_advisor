import os

from dotenv import load_dotenv
load_dotenv()

import glob
from langchain_community.document_loaders import Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Lấy API Key từ Google AI Studio (Miễn phí)
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("Cảnh báo: GOOGLE_API_KEY không được tìm thấy. Vui lòng thiết lập biến môi trường!")
else:
    os.environ["GOOGLE_API_KEY"] = api_key

DATA_DIR = "./data"
CHROMA_DB_DIR = "./chroma_db"

def main():
    print("Bắt đầu đọc dữ liệu từ thư mục data...")
    
    # Tìm tất cả các file .docx trong thư mục data
    docx_files = glob.glob(os.path.join(DATA_DIR, "*.docx"))
    
    if not docx_files:
        print(f"Không tìm thấy file .docx nào trong thư mục {DATA_DIR}.")
        return

    documents = []
    
    for file_path in docx_files:
        print(f"Đang đọc: {file_path}")
        try:
            loader = Docx2txtLoader(file_path)
            docs = loader.load()
            # Thêm metadata là tên file để LLM dễ dàng tham chiếu
            for doc in docs:
                doc.metadata["source_file"] = os.path.basename(file_path)
            documents.extend(docs)
        except Exception as e:
            print(f"Lỗi khi đọc {file_path}: {e}")

    if not documents:
        print("Không có dữ liệu văn bản nào được trích xuất.")
        return

    print(f"Đã tải {len(documents)} document(s). Đang chia nhỏ (chunking)...")
    
    # Chia nhỏ văn bản để nhúng (embed) tốt hơn
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    
    chunks = text_splitter.split_documents(documents)
    print(f"Tạo được {len(chunks)} chunks.")

    print("Khởi tạo Embeddings và lưu vào ChromaDB...")
    # Dùng HuggingFace Embeddings (chạy offline trên máy, cực kỳ ổn định)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Tạo vector DB và lưu vào đĩa
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DB_DIR
    )
    
    # Ở các bản Chroma mới, dữ liệu tự động persist, không cần gọi persist() thủ công nữa, nhưng có thể gọi nếu cần tương thích.
    # vector_db.persist()
    
    print(f"Hoàn thành! Vector DB được lưu tại: {CHROMA_DB_DIR}")

if __name__ == "__main__":
    main()
