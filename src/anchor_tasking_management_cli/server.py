from fastapi import *
from pydantic import BaseModel
from typing import Optional
import sqlite3
from . import task, database, security

app = FastAPI()

task_list = []
database.create_table()

@app.get("/health")
def health_check():
    return {"Status":"Server running"}

class SignUp(BaseModel):
    nick: str
    mail: str
    password: str

@app.post("/signup")
def signup(data:SignUp):
    try:
        password_hash = security.hash_password(data.password)
        try: 
            database.create_user(data.nick, data.mail, password_hash)
        except sqlite3.IntegrityError:
            return "\n\n[!] Nick or email already in use"
        return "\n\nAccount creation succes. Login with 'anchor login'."
    except:
        raise HTTPException(status_code=403, detail="Error in account iniciation")

class Login(BaseModel):
    name: Optional[str]
    password: str

@app.post("/login")
def login(data:Login):
    found = database.get_user_by_nick(data.name)
    if not found:
        found = database.get_user_by_email(data.name)
    if not found:
        raise HTTPException(401, detail="Invalid nick or password")
    if security.verify_password(data.password, found.get("password_hash")):
        return {"Succes":True,
                "acces_token": security.create_access_token(found.get("id")),
                "token_type": "bearer"
                }
    else: 
        return {
            "Succes": False,
            "Details": "Invalid nick or password"}

class AddTask(BaseModel):
    name: str
    description: Optional[str] = None
    deadline: Optional[str] = None
    priority: int = 1

@app.post("/add")
def add(task_param:AddTask, current_user: dict = Depends(security.get_current_user)):    
    database.add_task(
        name=task_param.name,
        description=task_param.description,
        deadline=task_param.deadline,
        priority=task_param.priority,
        user_id=current_user["id"]
        )
    return "Task created succesfully"

@app.get("/list")
def list_tasks(current_user: dict = Depends(security.get_current_user)):
    task_list = database.list_tasks(user_id=current_user["id"])
    return task_list

class CheckTask(BaseModel):
    task_id:str 
    uncheck:bool = False

@app.post("/check")
def check_task(task_param:CheckTask, current_user: dict = Depends(security.get_current_user)):
    try:
        id = int(task_param.task_id)
        if database.get_task(user_id=current_user["id"], task_id=id) is None:
            return "No task was found with that name"
    except:
        tasks_founded = database.find_tasks_by_name(user_id=current_user["id"], name=task_param.task_id)
        if len(tasks_founded) == 0:
            return "No task was found with that name"
        elif len(tasks_founded) > 1:
            return "Various tasks where found with that name"
        id = tasks_founded[0].get("id")
    database.set_done(task_id=id, user_id=current_user["id"], done = not task_param.uncheck)
    return "Task checked succesfully"

class DelTask(BaseModel):
    task_name:str

@app.post("/del")
def del_task(task_param:DelTask, current_user: dict = Depends(security.get_current_user)):
    if task_param.task_name == ".":
        database.delete_task(task_id=1, all=True, user_id=current_user["id"])
        return "All tasks have been removed"
    try:
        id = int(task_param.task_name)
    except:
        id = database.find_tasks_by_name(user_id=current_user["id"], name=task_param.task_name)
        if len(id) > 1:
            return "More than one task was found with that name. Refer to the task by its id"
        if len(id) == 0:
            return "No task was found with that name"
        id = id[0].get("id")
    database.delete_task(task_id=id, user_id=current_user["id"])
    return "Task removed with succes"

class EditTask(BaseModel):
    task_name:str
    deadline:str
    priority:int
    description:str

@app.post("/edit")
def edit_task(task_param:EditTask, current_user: dict = Depends(security.get_current_user)):
    try:
        id = int(task_param.task_id)
    except:
        tasks_founded = database.find_tasks_by_name(user_id=current_user["id"], name=task_param.task_name)
        if len(tasks_founded) == 0:
            return "No task was found with that name"
        elif len(tasks_founded) > 1:
            return "Various tasks where found with that name"
        id = tasks_founded[0].get("id")
    database.edit_task(task_id=id,
                       description=task_param.description,
                       deadline=task_param.deadline,
                       priority=task_param.priority,
                       user_id=current_user["id"])
    return "Task eddited with succes"

@app.get("/users")
def users_list():
    return database.list_users()