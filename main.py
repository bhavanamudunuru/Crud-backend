from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="CRUD App API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "https://crud-frontend-three-xi.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = None
firebase_auth = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth as firebase_auth_module

    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": os.getenv("FIREBASE_TYPE"),
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
            "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
        })
        firebase_admin.initialize_app(cred)

    db = firestore.client()
    firebase_auth = firebase_auth_module
    logger.info("Firebase connected successfully!")

except Exception as e:
    logger.error(f"Firebase not connected: {e}")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        logger.warning("Authentication failed — no token provided")
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        decoded = firebase_auth.verify_id_token(token)
        logger.info(f"User authenticated: {decoded.get('email', 'unknown')}")
        return decoded
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token.")


class PersonCreate(BaseModel):
    name: str
    age: int
    phone: Optional[str] = None

class PersonUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    phone: Optional[str] = None

def serialize_person(doc):
    data = doc.to_dict()
    data["id"] = doc.id
    return data


@app.post("/persons", status_code=201)
def create_person(body: PersonCreate, current_user: dict = Depends(get_current_user)):
    user_email = current_user.get("email", "unknown")
    logger.info(f"User [{user_email}] adding person: name={body.name}, age={body.age}, phone={body.phone}")

    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    if body.age < 0 or body.age > 150:
        raise HTTPException(status_code=400, detail="Enter a valid age.")
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected.")

    ref = db.collection("persons").add({
        "name": body.name.strip(),
        "age": body.age,
        "phone": body.phone.strip() if body.phone else "",
    })
    doc = ref[1].get()
    logger.info(f"User [{user_email}] added person: {body.name}")
    return {"message": "Person created successfully.", "data": serialize_person(doc)}


@app.get("/persons")
def get_all_persons(current_user: dict = Depends(get_current_user)):
    user_email = current_user.get("email", "unknown")
    logger.info(f"User [{user_email}] fetching all persons")

    if not db:
        raise HTTPException(status_code=500, detail="Database not connected.")

    docs = db.collection("persons").stream()
    persons = [serialize_person(doc) for doc in docs]
    logger.info(f"User [{user_email}] fetched {len(persons)} persons")
    return {"data": persons}


@app.put("/persons/{person_id}")
def update_person(person_id: str, body: PersonUpdate, current_user: dict = Depends(get_current_user)):
    user_email = current_user.get("email", "unknown")
    logger.info(f"User [{user_email}] updating person ID: {person_id}")

    if not db:
        raise HTTPException(status_code=500, detail="Database not connected.")

    doc_ref = db.collection("persons").document(person_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Person not found.")

    update_data = {}
    if body.name is not None:
        update_data["name"] = body.name.strip()
    if body.age is not None:
        update_data["age"] = body.age
    if body.phone is not None:
        update_data["phone"] = body.phone.strip()

    doc_ref.update(update_data)
    logger.info(f"User [{user_email}] updated person ID: {person_id}")
    return {"message": "Person updated successfully.", "data": serialize_person(doc_ref.get())}


@app.delete("/persons/{person_id}")
def delete_person(person_id: str, current_user: dict = Depends(get_current_user)):
    user_email = current_user.get("email", "unknown")
    logger.info(f"User [{user_email}] deleting person ID: {person_id}")

    if not db:
        raise HTTPException(status_code=500, detail="Database not connected.")

    doc_ref = db.collection("persons").document(person_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Person not found.")

    doc_ref.delete()
    logger.info(f"User [{user_email}] deleted person ID: {person_id}")
    return {"message": "Person deleted successfully."}