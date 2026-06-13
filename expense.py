from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
import sqlite3
import bcrypt
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware

from typing import Optional

SECRET_KEY = "my_super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class users(BaseModel):
    username: str
    password: str

data_base = "ET.db"

def init_db():
    con = sqlite3.connect(data_base)
    cursor = con.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users_data(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    """)
    con.commit()
    con.close()
init_db()

@app.post("/register")
def register(user: users):
    con = sqlite3.connect(data_base)
    cursor = con.cursor()

    cursor.execute("SELECT id FROM users_data WHERE username=?", (user.username,))
    existing = cursor.fetchone()

    if existing:
        con.close()
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    hashed_password = bcrypt.hashpw(
        user.password.encode(),
        bcrypt.gensalt()
    ).decode()

    cursor.execute("INSERT INTO users_data (username, password) VALUES (?,?)", (user.username, hashed_password))
    con.commit()
    con.close()
    return {"message": "Registration Successful"}

@app.get("/login")
def login(username: str, password: str):
    con = sqlite3.connect(data_base)
    cursor = con.cursor()

    cursor.execute("SELECT id, username, password FROM users_data WHERE username=?", (username,))
    x = cursor.fetchone()
     
    if not x:
        raise HTTPException(status_code=401, detail="Invalid username")
    
    if not bcrypt.checkpw(password.encode(), x[2].encode()):
        raise HTTPException(status_code=401, detail="Invalid Password")
    
    token = create_access_token({"user_id": x[0]})
    return {"message": f"WELCOME {username}", "access_token": token}

class expense(BaseModel):
    Spent_on: str
    Price: float
    Category: str
    Month: str
    Date: int
    Year: int
    Time: str

d_b = "expenses.db"

def ex_int():
    con = sqlite3.connect(d_b)
    cursor = con.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            Spent_on TEXT,
            Price FLOAT,
            Category TEXT,
            Month TEXT,
            Date INTEGER,
            Year INTEGER,
            Time TEXT
        )
    """)
    con.commit()
    con.close()
ex_int()

@app.post("/Add-Expense")
def add_expense(i: expense, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    
    user_id = payload["user_id"]

    con = sqlite3.connect(data_base)
    cursor = con.cursor()
    cursor.execute("SELECT id FROM users_data WHERE id=?", (user_id,))
    user = cursor.fetchone()
    con.close()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid User")
    
    con = sqlite3.connect(d_b)
    cursor = con.cursor()
    cursor.execute("INSERT INTO expenses (user_id, Spent_on, Price, Category, Month, Date, Year, Time) VALUES (?,?,?,?,?,?,?,?)",
                   (user_id, i.Spent_on, i.Price, i.Category, i.Month, i.Date, i.Year, i.Time))
    con.commit()
    con.close()
    return {"m": "Expense Added Successfully!"}

@app.get("/View-Expenses")
def view_Expenses(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    
    user_id = payload["user_id"]

    con = sqlite3.connect(d_b)
    cursor = con.cursor()
    cursor.execute("SELECT id, Spent_on, Price, Category, Month, Date, Year, Time FROM expenses WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    con.close()

    fetch_expen = []
    for r in rows:
        fetch_expen.append({
            "id": r[0], "Spent_on": r[1], "Price": r[2], "Category": r[3],
            "Month": r[4], "Date": r[5], "Year": r[6], "Time": r[7]
        })
    return {'m': fetch_expen}

class Edit_Expen(BaseModel):
    Spent_on: Optional[str]=None
    Price: Optional[float]=None
    Category: Optional[str]=None
    Month: Optional[str]=None
    Date: Optional[int]=None
    Year: Optional[int]=None
    Time: Optional[str]=None

@app.put("/Edit-Expense")
def Edit_expen(id: int, section: Edit_Expen, credientials: HTTPAuthorizationCredentials = Depends(security)):
    token = credientials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        
    user_id = payload["user_id"]
    con = sqlite3.connect(d_b)
    cursor = con.cursor()

    cursor.execute("SELECT Spent_on, Price, Category, Month, Date, Year, Time FROM expenses WHERE id=? AND user_id=?", (id, user_id))
    row = cursor.fetchone()

    if not row:
        con.close()
        raise HTTPException(status_code=404, detail="Nothing to find!")
    new_spent = section.Spent_on if section.Spent_on is not None else row[0]
    new_price = section.Price if section.Price is not None else row[1]
    new_category = section.Category if section.Category is not None else row[2]
    new_month = section.Month if section.Month is not None else row[3]
    new_date = section.Date if section.Date is not None else row[4]
    new_year = section.Year if section.Year is not None else row[5]
    new_time = section.Time if section.Time is not None else row[6]
    
    cursor.execute("UPDATE expenses SET Spent_on=?, Price=?, Category=?, Month=?, Date=?, Year=?, Time=? WHERE id=? AND user_id=?",
                   (new_spent, new_price, new_category, new_month, new_date, new_year, new_time, id, user_id))
    con.commit()

    cursor.execute("SELECT Spent_on, Price, Category, Month, Date, Year, Time FROM expenses WHERE id=? AND user_id=?", (id, user_id))
    Updated_row = cursor.fetchone()
    con.close()

    return {
        "m": "Updated Successfully!",
        "Updated": {
            "Spent_on": Updated_row[0], "Price": Updated_row[1], "Category": Updated_row[2],
            "Month": Updated_row[3], "Date": Updated_row[4], "Year": Updated_row[5], "Time": Updated_row[6]
        },
        "id": id
    }

@app.delete("/Delete-Spent_on")
def delete_spenton(id: int, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        
    user_id = payload["user_id"]

    con = sqlite3.connect(d_b)
    cursor = con.cursor()
    cursor.execute("SELECT id FROM expenses WHERE id=? AND user_id=?", (id, user_id))
    x = cursor.fetchone()

    if not x:
        con.close()
        raise HTTPException(status_code=404, detail="Nothing Found!")
    
    cursor.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (id, user_id))
    con.commit()
    con.close()
    return {"m": "Deleted Successfully!"}

@app.get("/Category-filtering")
def Category_wise(Category: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        
    user_id = payload["user_id"]

    con = sqlite3.connect(d_b)
    cursor = con.cursor()
    cursor.execute("SELECT id,Spent_on, Price, Category, Month, Date, Year, Time FROM expenses WHERE user_id=? AND Category=?", (user_id, Category))
    X = cursor.fetchall()

    if not X:
        con.close()
        return {"Category-Wise": []}

    cate_wise = []
    for x in X:
        cate_wise.append({
            "id":x[0], "Spent_on": x[1], "Price": x[2], "Category": x[3],
            "Month": x[4], "Date": x[5], "Year": x[6], "Time": x[7]
        })
    return {"Category-Wise": cate_wise}

@app.get("/Monthly-Report")
def Monthly(month: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        
    user_id = payload["user_id"]

    con = sqlite3.connect(d_b)
    cursor = con.cursor()
    cursor.execute("SELECT Category, SUM(Price) FROM expenses WHERE user_id=? AND Month=? GROUP BY Category", (user_id, month))
    m = cursor.fetchall()

    if not m:
        con.close()
        return {"The Month": month, "Total Expenses": 0, "Category Wise": {}}

    Total_expense = sum(x[1] for x in m)
    Cate_wise_expen = {Category: Total for Category, Total in m}

    return {
        "The Month": month,
        "Total Expenses": Total_expense,
        "Category Wise": Cate_wise_expen
    }

@app.get("/Dashboard")
def Dashboard(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        
    user_id = payload["user_id"]

    con = sqlite3.connect(d_b)
    cursor = con.cursor()
    cursor.execute("SELECT SUM(Price) FROM expenses WHERE user_id=?", (user_id,))
    Total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM expenses WHERE user_id=?", (user_id,))
    Transactions = cursor.fetchone()[0] or 0

    cursor.execute("SELECT Category, SUM(Price) FROM expenses WHERE user_id=? GROUP BY Category", (user_id,))
    rows = cursor.fetchall()

    current_month=datetime.now().strftime("%B")
    cursor.execute("SELECT SUM(Price) FROM expenses WHERE user_id=? AND Month=?",(user_id,current_month))
    This_month=cursor.fetchone()[0] or 0

    current_day=datetime.now().day
    daily_avg=This_month/current_day if current_day > 0 else 0
    

    cate = {Category: Amount for Category, Amount in rows}
    return {"Total Expenses": Total, "Transactions": Transactions, "This Month":This_month,  "Category Summary": cate, "Daily Average":daily_avg}

@app.get("/Yearly-Report")
def year_report(year: int, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        
    user_id = payload["user_id"]

    con = sqlite3.connect(d_b)
    cursor = con.cursor()
    cursor.execute("SELECT Spent_on, Price, Category, Month, Date, Time FROM expenses WHERE user_id=? AND Year=?", (user_id, year))
    y_wise = cursor.fetchall()

    if not y_wise:
        return {"Year": year, "Expenses": [], "Category-Wise": {}}
    
    cursor.execute("SELECT Category, SUM(price) FROM expenses WHERE user_id=? AND Year=? GROUP BY Category", (user_id, year))
    y_c = cursor.fetchall()

    yee = {Category: total for Category, total in y_c}
    return {"Year": year, "Expenses": y_wise, "Category-Wise": yee}

@app.delete("/Delete-User")
def delete_my_account(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        
    user_id = payload["user_id"]

    con = sqlite3.connect(data_base)
    cursor = con.cursor()
    cursor.execute("DELETE FROM users_data WHERE id=?", (user_id,))
    con.commit()
    con.close()

    con = sqlite3.connect(d_b)
    cursor = con.cursor()
    cursor.execute("DELETE FROM expenses WHERE user_id=?", (user_id,))
    con.commit()
    con.close()
    return {"m": "Account and All Expenses Deleted Successfully"}