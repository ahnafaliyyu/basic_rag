import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(url="http://localhost:6333")

# Buat collection jika belum ada
if not client.collection_exists("kic_hackaton"):
    client.create_collection(
        collection_name="kic_hackaton",
        vectors_config=VectorParams(
            size=1024,
            distance=Distance.COSINE
        )
    )

dummy_data = [
    "my name is ahnaf",
    "i am a software engineer",
    "i love programming",
    "i am learning python",
    "i am learning machine learning"
]

def generate_response(prompt):
    response= requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]

def main():
    # for i, text in enumerate(dummy_data):

    #     response = requests.post(
    #         "http://localhost:11434/api/embeddings",
    #         json={
    #             "model": "mxbai-embed-large",
    #             "prompt": text
    #         }
    #     )

    #     data = response.json()

    #     print(f"Response {i}:")
    #     print(data)

    #     embedding = data.get("embedding", [])

    #     if len(embedding) == 0:
    #         print(f"Embedding kosong untuk: {text}")
    #         continue

    #     client.upsert(
    #         collection_name="kic_hackaton",
    #         wait=True,
    #         points=[
    #             PointStruct(
    #                 id=i,
    #                 vector=embedding,
    #                 payload={
    #                     "text": text
    #                 }
    #             )
    #         ]
    #     )

    #     print(f"Inserted: {text}")
    
    prompt= input("Masukkan query: ")
    # response =  generate_response(prompt)
    # print(response)
    
    
    adjusted_prompt = f"Find similar texts to: {prompt}"

    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={
            "model": "mxbai-embed-large",
            "prompt": adjusted_prompt
        }
    )
    
    data = response.json()
    embedding = data.get("embedding", [])
    
    
    results = client.query_points(
    collection_name="kic_hackaton",
    query=embedding,
    limit=2,
    with_payload=True
)
    relevan_passages = "\n".join([f"- {point.payload['text']}" for point in results.points])
    
    augmented_prompt = f""" the following are relevant passages:
    <retrieved_data>
    {relevan_passages}.
    here the original query:
    <user_query>
    {prompt}
    </user_query>"""

    response = generate_response(augmented_prompt)
    print(response)
    
if __name__ == "__main__":
    main()