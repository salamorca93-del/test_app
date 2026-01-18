import os
import time
import uuid
import logging
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# --------------------
# Logging setup (FILE ONLY)
# --------------------
LOG_DIR = "/var/log"
LOG_FILE = f"{LOG_DIR}/app.log"

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,  # log EVERYTHING
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE)
    ],
)

logger = logging.getLogger("calculator-app")
logger.info("Application starting")

# --------------------
# MySQL config (K8s)
# --------------------
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "my-secret-pw")
MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql")
MYSQL_DB = os.getenv("MYSQL_DB", "calculator")

SERVER_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}"

# --------------------
# Wait for MySQL
# --------------------
logger.info("Waiting for MySQL to become available")

for i in range(30):
    try:
        logger.debug(f"MySQL connection attempt {i + 1}")
        server_engine = create_engine(SERVER_URL, pool_pre_ping=True)
        with server_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("MySQL is reachable")
        break
    except Exception as e:
        logger.warning(f"MySQL not ready: {e}")
        time.sleep(2)
else:
    logger.critical("MySQL not reachable after retries")
    raise RuntimeError("MySQL not reachable")

# --------------------
# Create DB if missing
# --------------------
try:
    logger.info(f"Ensuring database exists: {MYSQL_DB}")
    with server_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}"))
        conn.commit()
    logger.info("Database ensured successfully")
except Exception:
    logger.exception("Database creation failed")
    raise

# --------------------
# Connect to DB
# --------------------
DATABASE_URL = f"{SERVER_URL}/{MYSQL_DB}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# --------------------
# Table
# --------------------
class Calculation(Base):
    __tablename__ = "calculations"

    id = Column(Integer, primary_key=True)
    operation = Column(String(20))
    operand1 = Column(Float)
    operand2 = Column(Float)
    result = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
except Exception:
    logger.exception("Table creation failed")
    raise

# --------------------
# FastAPI app
# --------------------
app = FastAPI(title="K8s Calculator")

# --------------------
# Request logging middleware
# --------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        f"REQUEST_START id={request_id} "
        f"method={request.method} "
        f"path={request.url.path} "
        f"client={request.client.host}"
    )

    try:
        response = await call_next(request)
        return response
    finally:
        duration = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"REQUEST_END id={request_id} "
            f"status={getattr(response, 'status_code', 'N/A')} "
            f"duration_ms={duration}"
        )

# --------------------
# DB session logging
# --------------------
def get_db():
    logger.debug("DB_SESSION_OPENED")
    db = SessionLocal()
    try:
        yield db
        logger.debug("DB_SESSION_COMMIT")
    except Exception:
        logger.error("DB_SESSION_ROLLBACK", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()
        logger.debug("DB_SESSION_CLOSED")

# --------------------
# API: Add
# --------------------
@app.post("/add")
def add(a: float, b: float, db: Session = Depends(get_db)):
    logger.info(f"USER_ACTION add a={a} b={b}")

    try:
        result = a + b

        db.add(Calculation(
            operation="add",
            operand1=a,
            operand2=b,
            result=result
        ))
        db.commit()

        logger.info(f"ADD_SUCCESS result={result}")
        return {"result": result}

    except Exception:
        logger.exception("ADD_FAILED")
        raise HTTPException(status_code=500, detail="Internal server error")
