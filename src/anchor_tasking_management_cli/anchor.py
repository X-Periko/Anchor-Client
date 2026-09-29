import typer
import requests
import time
import readchar
import threading
from typing import Optional
from rich.prompt import Prompt, IntPrompt, Confirm
from . import session, qeue

app = typer.Typer()
SERVER_URL = "http://localhost:8000"

def session_exists() -> bool:
      session_data = session.load_session()
      return isinstance(session_data, dict) and "acces_token" in session_data

@app.command("sync")
def sync(): 
	list= qeue.load_qeue()
	if not list:
		typer.echo("Nothing to sync")
		return 
	
	remaining = []
	for i in list:
		try:
			response = requests.request(method=i["method"], url=SERVER_URL+i["endpoint"], json=i["payload"], headers={"Authorization": f"Bearer {session.load_session().get("acces_token")}"})
			typer.echo(response.json())
		except requests.exceptions.ConnectionError:
			remaining.append(i)
	qeue.save_qeue(remaining)
	typer.echo(f"{len(list) - len(remaining)} changes out of {len(list)} synchronized.")

@app.command("signup")
def signup():
	nick = Prompt.ask("Enter your name")
	mail = Prompt.ask("Enter your email")
	password = Prompt.ask("Enter your password", password=True)
	if "@" in nick:
		typer.echo("You can't use @ in your username")
		return
	USR_DATA = {
		"nick": nick,
		"mail": mail,
		"password": password
	}
	try:
		response = requests.post(SERVER_URL + "/signup", json=USR_DATA)
		response = requests.post(SERVER_URL + "/login", json={
			"name":nick,
			"password":password
		})
		if not response.ok:
			typer.echo(response.json().get("detail"))
		session.save_session(data=response.json())
		typer.echo("Account created and logged in")
	except:
		typer.echo("[!] Server connection error")

@app.command("login")
def	login():
	name = Prompt.ask("Enter your email or nick")
	password = Prompt.ask("Enter your password", password=True)
	response = requests.post(SERVER_URL + "/login", json={
		"name":name,
		"password":password
	})
	if not response.ok:
		typer.echo(response.json().get("detail"))
		return 
	if response.json().get("Succes"):
		session.save_session(data=response.json())
		typer.echo("Login succesful")
	else:
		typer.echo("Invalid nick or password")

@app.command("logout")
def logout():
	session.restore_session()

@app.command("add")
def add(name:str):
	if session_exists():
		try:
			description = Prompt.ask("Description", default=None)
			deadline = Prompt.ask("Deadline (YYYY-MM-DD)", default=None)
			priority = IntPrompt.ask("Priority", default=1)
			payload = {
				"name":name.title(),
				"description":description,
				"deadline":deadline,
				"priority":priority
			}
			response = requests.post(SERVER_URL + "/add", json=payload, headers={"Authorization": f"Bearer {session.load_session().get("acces_token")}"})
			typer.echo(response.json())
		except requests.exceptions.ConnectionError:
			typer.echo(f"Couldn't establish connection with server -> going to qeue (run anchor sync to execute commands in qeue)")
			qeue.enqeue(method="POST", endpoint="/add", payload=payload)
	else:
		typer.echo("\n\n[!] Run anchor signup/login to complete your authentication before using the system")

@app.command("list")
def list_tasks(simple:bool = typer.Option(False, "--simple", help="Simple listing with names"),
            sort:Optional[str] = typer.Option(False, "--sort", "-s", help="Sorting options (priority)"),
			pending:Optional[bool] = typer.Option(False, "--pending", help="Filter pending tasks"),
			done:Optional[bool] = typer.Option(False, "--done", help="Filter done tasks"),
			dynamic:Optional[bool] = typer.Option(False, "-d","--dynamic", help="Dynamic listing")):
	if session_exists():
		def escuchar_salida(stop_event: threading.Event):
			while not stop_event.is_set():
				key = readchar.readkey()
				if key.lower() == "q":
					stop_event.set()
		def print_list():
			try:
				response = requests.get(SERVER_URL+"/list", headers={"Authorization": f"Bearer {session.load_session().get("acces_token")}"})
				response_list = response.json()
				response.raise_for_status()
				if not isinstance(response_list, list):
					typer.echo(f"Error del servidor {response_list}")
				if sort == "priority":
					new_list = []
					prior_list = []
					for t in response_list:
						prior_list.append(t.get("priority"))
					for x in range(len(prior_list)):
						min_prior = max(prior_list)
						index = prior_list.index(min_prior)
						prior_list.remove(min_prior)
						new_list.append(response_list[index])
						response_list.pop(index)
					response_list = new_list
				if pending:
					response_list = [t for t in response_list if not t.get("done")]
				if done:
					response_list = [t for t in response_list if t.get("done")]
				if pending and done:
					typer.echo("Can't use --pending and --done flags in same command")
					return True
				if simple:
					out = ""
					for t in response_list:
						out += f"- {"☑" if t.get("done") else "☐"} {t.get("name")}\n\n"
					typer.echo(f"{out if out != "" else "Task list empty. Good job!"}")
				else:
					if response_list == []:
						typer.echo("Task list empty. Good job!")
					else:
						for t in response_list:
							typer.echo(f"-> {"☑" if t.get("done") else "☐"}   {t.get("id")}: {t.get("name")}")
							typer.echo(f"	· Description: {t.get("description") if t.get("description") != None else "No description was added"}")
							typer.echo(f"	· Deadline: {t.get("deadline") if t.get("deadline") != None else "No deadline was added"}")
							typer.echo(f"	· Priority: {t.get("priority")}\n")
			except requests.exceptions.ConnectionError:
				typer.echo("Couldn't establish connection with server")
			except requests.exceptions.HTTPError as e:
				typer.echo(f"Server error: \n{e}")
		if not dynamic:
			print_list()
		else:
			stop_event = threading.Event()
			listener = threading.Thread(target=escuchar_salida, args=(stop_event,), daemon=True)
			listener.start()
			while not stop_event.is_set():
				for _ in range(100):
					typer.echo("")
				print_list()
				typer.echo("\n\nPress q to exit dynamic listing")
				time.sleep(1)
	else:
		typer.echo("\n\n[!] Run anchor signup/login to complete your authentication before using the system")

@app.command("rm")
def delete(task_name):
	if session_exists():
		try:
			response = requests.post(SERVER_URL+"/del", json={"task_name":task_name}, headers={"Authorization": f"Bearer {session.load_session().get("acces_token")}"})
			typer.echo(response.json())
		except requests.exceptions.ConnectionError:
			typer.echo("Couldn't establish connection with server -> going to qeue (run anchor sync to execute commands in qeue)")
			qeue.enqeue(method="POST", endpoint="/del", payload={"task_name":task_name})
		except requests.exceptions.HTTPError as e:
			typer.echo(f"Server error: \n{e}")
		except Exception as e:
			typer.echo(e)
	else:
		typer.echo("\n\n[!] Run anchor signup/login to complete your authentication before using the system")

@app.command("check")
def check_task(task, uncheck:Optional[bool] = False):
	if session_exists():
		try:
			response = requests.post(SERVER_URL+"/check", json={"task_id":str(task),"uncheck":uncheck}, headers={"Authorization": f"Bearer {session.load_session().get("acces_token")}"})
			typer.echo(response.json())
		except requests.exceptions.ConnectionError:
			typer.echo("Couldn't establish connection with server -> going to qeue (run anchor sync to execute commands in qeue)")
			qeue.enqeue(method="POST", endpoint="/check", payload={"task_id":str(task),"uncheck":uncheck})
		except requests.exceptions.HTTPError as e:
			typer.echo(f"Server error: \n{e}")
		except Exception as e:
			typer.echo(e)
	else:
		typer.echo("\n\n[!] Run anchor signup/login to complete your authentication before using the system")

def progress_bar(done: int, total: int, width: int = 20) -> str:
    if total == 0:
        return f"[{'░' * width}] 0%"
    ratio = done / total
    filled = int(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    percent = int(ratio * 100)
    return f"[{bar}] {percent}%"

@app.command("status")
def status():
	if session_exists():
		try:
			response = requests.get(SERVER_URL+"/list", headers={"Authorization": f"Bearer {session.load_session().get("acces_token")}"})
			response_list = response.json()
			done = 0
			for t in response_list:
				if t.get("done"):
					done += 1
			if len(response_list) == 0:
				typer.echo("You don't have any task today.")
			else:
				typer.echo(progress_bar(done=done, total= len(response_list)))
				typer.echo(f"{done} tasks completed out of {len(response_list)}") 
				if done == len(response_list):
					typer.echo("Congratulations. You have no tasks left!")
		except requests.exceptions.ConnectionError:
			typer.echo("Couldn't establish connection with server")
		except requests.exceptions.HTTPError as e:
			typer.echo(f"Server error: \n{e}")
		except Exception as e:
			typer.echo(e)
	else:
		typer.echo("\n\n[!] Run anchor signup/login to complete your authentication before using the system")

@app.command("edit")
def edit_task(task_name):
	if session_exists():
		try:
			response = requests.get(SERVER_URL+"/list", headers={"Authorization": f"Bearer {session.load_session().get("acces_token")}"})
			task_list = response.json()
			current = None
			for t in task_list:
				if t.get("name").lower() == task_name.lower():
					current = t
			if current:
				description = Prompt.ask("Description", default=current.get("description") or "")
				deadline = Prompt.ask("Deadline (YYYY-MM-DD)", default=current.get("deadline") or "")
				priority = IntPrompt.ask("Priority", default=current.get("priority", 1))
				typer.echo(f"\nSummary:\n  Description: {description}\n  Deadline: {deadline}\n  Priority: {priority}")
				if Confirm.ask("¿Confirm changes?"):
					payload = {
						"task_name":task_name,
						"priority":priority,
						"deadline":deadline,
						"description":description
					}
					response = requests.post(SERVER_URL+"/edit", json=payload, headers={"Authorization": f"Bearer {session.load_session().get("acces_token")}"})
					typer.echo(response.json())
			else:
				typer.echo("No task was found with that name")
		except requests.exceptions.ConnectionError:
			typer.echo("Couldn't establish connection with server -> going to qeue (run anchor sync to execute commands in qeue)")
			qeue.enqeue(method="POST", endpoint="/edit", payload=payload)
		except requests.exceptions.HTTPError as e:
			typer.echo(f"Server error: \n{e}")
		except Exception as e:
			typer.echo(e)
	else:
		typer.echo("\n\n[!] Run anchor signup/login to complete your authentication before using the system")

if __name__ == "__main__":
	app()