import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def create_lcel_retrieval_chain(retriever, llm, prompt):
    return (
        RunnablePassthrough.assign(
            context=(lambda x: x["input"]) | retriever
        )
        | RunnablePassthrough.assign(
            answer=(
                RunnablePassthrough.assign(context=lambda x: format_docs(x["context"]))
                | prompt
                | llm
                | StrOutputParser()
            )
        )
    )
from local_data_service import get_latest_device_data

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Local AI Fault Handling Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)# 1. Mở kết nối thư mục static để Frontend có thể lấy ảnh sơ đồ
import os
if not os.path.exists("static/images"):
    os.makedirs("static/images")
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. Khởi tạo Embeddings và LLM (Chạy Local 100%)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = Chroma(persist_directory="./chroma_db_v2", embedding_function=embeddings)
retriever = vector_db.as_retriever(search_kwargs={"k": 3})

# Gọi model qwen2.5:3b từ Ollama, temperature thấp để xuất JSON chuẩn
llm = ChatOllama(model="qwen2.5:3b", temperature=0.1)

# ---------------------------------------------------------
# CẤU TRÚC REQUEST
# ---------------------------------------------------------
class FaultRequest(BaseModel):
    fault_signal: str

class TrainingRequest(BaseModel):
    scenario_topic: str

# ---------------------------------------------------------
# API 1: TROUBLESHOOTING MODE (XỬ LÝ LỖI)
# ---------------------------------------------------------
troubleshoot_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are an expert technical assistant. Use the retrieved context to answer the fault query.\n"
     "You MUST return ONLY a valid JSON object with the following keys. Do not add markdown blocks like ```json:\n"
     "- 'fault_name': string\n"
     "- 'possible_causes': list of strings\n"
     "- 'recommended_actions': list of strings\n"
     "Context:\n{context}"),
    ("human", "Fault signal/query: {input}")
])

troubleshoot_chain = create_lcel_retrieval_chain(retriever, llm, troubleshoot_prompt)

@app.post("/api/v1/troubleshoot")
async def handle_fault(request: FaultRequest):
    try:
        response = troubleshoot_chain.invoke({"input": request.fault_signal})
        
        # Parse JSON từ câu trả lời của LLM
        raw_answer = response["answer"].strip()
        if raw_answer.startswith("```json"):
            raw_answer = raw_answer.replace("```json", "").replace("```", "").strip()
            
        result_json = json.loads(raw_answer)
        
        # Gắn thêm link ảnh sơ đồ mạch từ metadata của tài liệu tìm được
        diagram_urls = list(set([doc.metadata.get("diagram_image_url") for doc in response["context"] if "diagram_image_url" in doc.metadata]))
        result_json["relevant_drawings"] = diagram_urls

        return {"status": "success", "data": result_json}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error or JSON Parsing failed: {str(e)}")

# ---------------------------------------------------------
# API 2: TRAINING MODE (TẠO CÂU HỎI MÔ PHỎNG)
# ---------------------------------------------------------
training_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are an examiner generating technical test scenarios for engineers. "
     "Based on the context, generate a realistic fault scenario.\n"
     "Return ONLY a valid JSON object with keys:\n"
     "- 'scenario_question': A detailed hypothetical fault situation.\n"
     "- 'expected_answer': A list of correct steps to resolve it.\n"
     "Context:\n{context}"),
    ("human", "Topic: {input}")
])

training_chain = create_lcel_retrieval_chain(retriever, llm, training_prompt)

@app.post("/api/v1/training/generate-scenario")
async def generate_training_scenario(request: TrainingRequest):
    try:
        response = training_chain.invoke({"input": request.scenario_topic})
        
        raw_answer = response["answer"].strip()
        if raw_answer.startswith("```json"):
            raw_answer = raw_answer.replace("```json", "").replace("```", "").strip()
            
        result_json = json.loads(raw_answer)
        return {"status": "success", "data": result_json}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# COPILOT REQUEST MODELS
# ---------------------------------------------------------
from typing import Optional

class ExplainDecisionRequest(BaseModel):
    decision_event: str
    simulation_logs: Optional[str] = None

class RealtimeAlertRequest(BaseModel):
    alert_condition: str
    current_metrics: Optional[dict] = None

class LiveTrainingRequest(BaseModel):
    current_metrics: Optional[dict] = None

# ---------------------------------------------------------
# API 3: EXPLAIN DECISION (Giải thích quyết định của Rule Engine)
# ---------------------------------------------------------
explain_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are a Copilot assistant analyzing a Rule Engine decision in a PV-BESS system.\n"
     "Use the provided context (Rules) and the simulation logs to explain the decision.\n"
     "Return ONLY a valid JSON object with keys:\n"
     "- 'decision': string (the decision being explained)\n"
     "- 'explanation': string (detailed explanation based on logs and rules)\n"
     "Context:\n{context}\n\nSimulation Logs:\n{simulation_logs}"),
    ("human", "Decision to explain: {input}")
])

explain_chain = create_lcel_retrieval_chain(retriever, llm, explain_prompt)

@app.post("/api/v1/copilot/explain-decision")
async def explain_decision(request: ExplainDecisionRequest):
    try:
        # Lấy dữ liệu mô phỏng thật từ local_data_service nếu không truyền vào
        logs = request.simulation_logs if request.simulation_logs else get_latest_device_data()
        
        response = explain_chain.invoke({
            "input": request.decision_event,
            "simulation_logs": logs
        })
        
        raw_answer = response["answer"].strip()
        if raw_answer.startswith("```json"):
            raw_answer = raw_answer.replace("```json", "").replace("```", "").strip()
            
        result_json = json.loads(raw_answer)
        return {"status": "success", "data": result_json}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# API 4: REAL-TIME ALERT (Cảnh báo theo thời gian thực)
# ---------------------------------------------------------
alert_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are a Real-time Alert system for a PV-BESS plant. A critical condition has occurred.\n"
     "Based on the context, provide an alert message and recommended actions.\n"
     "Return ONLY a valid JSON object with keys:\n"
     "- 'alert_message': string (the warning to display)\n"
     "- 'recommended_actions': list of strings\n"
     "Context:\n{context}\n\nCurrent Metrics:\n{current_metrics}"),
    ("human", "Alert condition: {input}")
])

alert_chain = create_lcel_retrieval_chain(retriever, llm, alert_prompt)

@app.post("/api/v1/copilot/realtime-alert")
async def realtime_alert(request: RealtimeAlertRequest):
    try:
        if request.current_metrics:
            metrics_str = json.dumps(request.current_metrics)
        else:
            # Tự động truy xuất dữ liệu Inverter hiện tại để cảnh báo
            metrics_str = get_latest_device_data()
            
        response = alert_chain.invoke({
            "input": request.alert_condition,
            "current_metrics": metrics_str
        })
        
        raw_answer = response["answer"].strip()
        if raw_answer.startswith("```json"):
            raw_answer = raw_answer.replace("```json", "").replace("```", "").strip()
            
        result_json = json.loads(raw_answer)
        
        # Gắn thêm link ảnh sơ đồ mạch
        diagram_urls = list(set([doc.metadata.get("diagram_image_url") for doc in response["context"] if "diagram_image_url" in doc.metadata]))
        result_json["relevant_drawings"] = diagram_urls
        
        return {"status": "success", "data": result_json}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# API 5: LIVE TRAINING MODE (Đào tạo thực chiến)
# ---------------------------------------------------------
live_training_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are an examiner training engineers on a live PV-BESS system.\n"
     "Using the real-time simulation metrics, ask a 'What if' question to test their understanding.\n"
     "Return ONLY a valid JSON object with keys:\n"
     "- 'current_state_summary': string\n"
     "- 'what_if_question': string (the question to ask the trainee)\n"
     "- 'expected_answer_hints': list of strings (hints for the correct logic based on context)\n"
     "Context:\n{context}"),
    ("human", "Current Metrics: {input}")
])

live_training_chain = create_lcel_retrieval_chain(retriever, llm, live_training_prompt)

@app.post("/api/v1/copilot/live-training")
async def live_training(request: LiveTrainingRequest):
    try:
        if request.current_metrics:
            metrics_str = json.dumps(request.current_metrics)
        else:
            # Lấy data mô phỏng (Inverter) mới nhất để hỏi "What If"
            metrics_str = get_latest_device_data()
            
        response = live_training_chain.invoke({"input": metrics_str})
        
        raw_answer = response["answer"].strip()
        if raw_answer.startswith("```json"):
            raw_answer = raw_answer.replace("```json", "").replace("```", "").strip()
            
        result_json = json.loads(raw_answer)
        return {"status": "success", "data": result_json}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))