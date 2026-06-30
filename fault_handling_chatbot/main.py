import os

from dotenv import load_dotenv
load_dotenv()

import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lấy API Key từ biến môi trường (Ví dụ từ file .env)
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    logger.warning("GOOGLE_API_KEY không được tìm thấy. Vui lòng thiết lập biến môi trường!")
else:
    os.environ["GOOGLE_API_KEY"] = api_key

app = FastAPI(title="Fault Handling AI Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Biến toàn cục để lưu trữ RAG chain
rag_chain = None

def init_rag_chain():
    global rag_chain
    try:
        # Dùng HuggingFace Embeddings cho đồng bộ với file ingest
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        # Kiểm tra xem thư mục ChromaDB đã tồn tại chưa
        if not os.path.exists("./chroma_db"):
            logger.warning("Thư mục ./chroma_db không tồn tại. Vui lòng chạy file ingest_data.py trước!")
            return False

        vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
        retriever = vector_db.as_retriever(search_kwargs={"k": 5}) # Lấy 5 đoạn text liên quan nhất để có context tốt hơn

        # Dùng Google Gemini Flash (Miễn phí), để temperature = 0 cho câu trả lời bám sát kỹ thuật
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)

        # Xây dựng Prompt ép kiểu JSON đầu ra
        system_prompt = (
            "You are an expert AI assistant for fault handling in electrical and mechanical systems. "
            "Use the provided retrieved context to answer the user's fault query.\n"
            "You MUST extract the information and return ONLY a valid JSON object with the exact following keys:\n"
            "- 'fault_name': The exact name of the fault.\n"
            "- 'possible_causes': A list of strings detailing possible causes.\n"
            "- 'recommended_actions': A list of strings detailing corrective troubleshooting actions.\n"
            "- 'relevant_drawings': A string describing the related circuit diagrams or manual references, including the document name (e.g., from 'source_file' metadata or the text itself).\n\n"
            "If the information is not found in the context, output empty lists or 'Not found' for the respective fields. DO NOT hallucinate.\n\n"
            "Context:\n{context}"
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])

        # Tạo RAG Pipeline
        question_answer_chain = create_stuff_documents_chain(llm, prompt)
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)
        logger.info("Khởi tạo RAG Chain thành công!")
        return True
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo RAG Chain: {e}")
        return False

# Định nghĩa cấu trúc request đầu vào
class QueryRequest(BaseModel):
    fault_signal: str

@app.on_event("startup")
async def startup_event():
    init_rag_chain()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Fault Handling AI Assistant API", "status": "running"}

# Endpoint xử lý lỗi
@app.post("/api/v1/fault-handling")
async def handle_fault(request: QueryRequest):
    if rag_chain is None:
        # Thử khởi tạo lại
        if not init_rag_chain():
            raise HTTPException(status_code=503, detail="Hệ thống AI chưa sẵn sàng. Vui lòng kiểm tra Vector DB hoặc API Key.")

    try:
        # Chạy pipeline RAG
        logger.info(f"Đang xử lý tín hiệu lỗi: {request.fault_signal}")
        response = rag_chain.invoke({"input": request.fault_signal})
        
        # LLM trả về một chuỗi dạng JSON, ta parse nó thành dict của Python
        raw_answer = response["answer"]
        
        # Xóa markdown json block nếu LLM sinh ra (VD: ```json ... ```)
        raw_answer = raw_answer.strip()
        if raw_answer.startswith("```json"):
            raw_answer = raw_answer[7:]
        if raw_answer.endswith("```"):
            raw_answer = raw_answer[:-3]
        raw_answer = raw_answer.strip()
            
        try:
            ai_response_json = json.loads(raw_answer)
        except json.JSONDecodeError:
            logger.error(f"Lỗi parse JSON. LLM Response: {raw_answer}")
            # Xử lý fallback nếu LLM không trả về JSON chuẩn
            ai_response_json = {
                "fault_name": request.fault_signal,
                "possible_causes": ["Could not parse LLM response as JSON."],
                "recommended_actions": [],
                "relevant_drawings": "Unknown",
                "raw_response": raw_answer
            }

        # Format lại metadata
        sources = list(set([doc.metadata.get("source_file", "Unknown") for doc in response["context"]]))

        # Trả về kết quả hoàn chỉnh
        return {
            "status": "success",
            "data": ai_response_json,
            "sources": sources
        }
    except Exception as e:
        logger.error(f"Lỗi xử lý request: {e}")
        raise HTTPException(status_code=500, detail=str(e))