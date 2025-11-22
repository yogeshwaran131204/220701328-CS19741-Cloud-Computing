from flask import Flask, request, render_template
from azure.storage.blob import generate_blob_sas, BlobSasPermissions, BlobServiceClient
from datetime import datetime, timedelta
from io import BytesIO
from PyPDF2 import PdfReader
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

# ------------------------------
# 🔹 Azure Blob Storage Config
# ------------------------------
account_name = os.getenv("ACCOUNT_NAME")
container_name = os.getenv("CONTAINER_NAME")
account_key = os.getenv("AZURE_STORAGE_KEY") 

# ------------------------------
# 🔹 OpenAI API Config
# ------------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/", methods=["GET", "POST"])
def home():
    sas_url = None
    ai_output = None
    error = None

    if request.method == "POST":
        course_name = request.form["course"]
        blob_name = course_name.lower().replace(" ", "_") + ".pdf"

        try:
            # ✅ Connect to Blob Storage
            bsc = BlobServiceClient(account_url=f"https://{account_name}.blob.core.windows.net", credential=account_key)
            blob_client = bsc.get_blob_client(container_name, blob_name)

            # ✅ Check if blob exists
            if not blob_client.exists():
                error = f"❌ Sorry, the course '{course_name}' was not found."
            else:
                # ✅ Generate SAS URL (1-hour validity)
                sas_token = generate_blob_sas(
                    account_name=account_name,
                    container_name=container_name,
                    blob_name=blob_name,
                    account_key=account_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.utcnow() + timedelta(hours=1)
                )
                sas_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

                # ✅ Download PDF content
                pdf_data = blob_client.download_blob().readall()
                reader = PdfReader(BytesIO(pdf_data))
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                #print("Extracted characters:", len(text))


                # ✅ Generate quiz + flashcards using OpenAI
                prompt = f"""
                Create:
                1️⃣ A short 5-line summary of the course.
                2️⃣ 5 quiz questions with answers.
                3️⃣ 5 flashcards (Q&A format).
                Based on this course content:
                {text[:5000]}
                Return the output ONLY in this JSON format (no explanation text):
                Give me the respnse in json format below
                {{
                "summary": "value",
                "quizes": [
                    {{
                    "question": "value",
                    "op1": "value",
                    "op2": "value",
                    "op3": "value",
                    "op4": "value",
                    "answer": "value"
                    }}
                ],
                "flashcards": [
                    {{
                    "question": "value",
                    "flash": "value"
                    }}
                ]
                }}
                """

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}]
                )

                ai_output = response.choices[0].message.content
                print("✅ AI Output:", ai_output)

        except Exception as e:
            #print("OpenAI error:", e)
            error = f"⚠️ Error: {str(e)}"

    return render_template("index.html", sas_url=sas_url, ai_output=ai_output, error=error)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
