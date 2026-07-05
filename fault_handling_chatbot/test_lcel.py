from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

def format_docs(docs):
    return "\n\n".join(docs)

chain = (
    RunnablePassthrough.assign(
        context=lambda x: ["doc1", "doc2"]
    )
    | RunnablePassthrough.assign(
        answer=(
            RunnablePassthrough.assign(context=lambda x: format_docs(x["context"]))
            | (lambda x: f"PROMPT: {x['context']}")
            | (lambda x: f"LLM: {x}")
            | StrOutputParser()
        )
    )
)

print(chain.invoke({"input": "test"}))
