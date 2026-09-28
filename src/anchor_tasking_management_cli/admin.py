"""anchor-admin: administración directa de la base de datos de anchor."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from argon2 import PasswordHasher
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import database

app = typer.Typer(
    help="Direct administration of the anchor database.",
    no_args_is_help=True,
)
console = Console()
_ph = PasswordHasher()


def fail(message: str):
    typer.secho(f"[!] {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def cell(value) -> str:
    """Texto seguro para una celda de rich (evita que [x] se interprete como estilo)."""
    return "-" if value is None else escape(str(value))


@contextmanager
def db():
    """Conexión con commit/rollback automático que además se cierra al salir.

    No crea la base si no existe (database.connect() la crearía vacía).
    """
    if not database.DB_PATH.exists():
        fail(f"Database not found: {database.DB_PATH}")
    conn = database.connect()  # ya activa PRAGMA foreign_keys = ON
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def find_user(conn: sqlite3.Connection, ref: str) -> sqlite3.Row:
    """Busca por nick, email o id numérico."""
    row = conn.execute(
        "SELECT * FROM users WHERE nick = ? OR email = ?", (ref, ref)
    ).fetchone()
    if row is None and ref.isdigit():
        row = conn.execute("SELECT * FROM users WHERE id = ?", (int(ref),)).fetchone()
    if row is None:
        fail(f"User not found: {ref}")
    return row


@app.command()
def info():
    """Show database location, size and row counts."""
    with db() as conn:
        n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        n_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        n_done = conn.execute("SELECT COUNT(*) FROM tasks WHERE done = 1").fetchone()[0]
    size_kb = database.DB_PATH.stat().st_size / 1024
    typer.echo(f"Path:  {database.DB_PATH}")
    typer.echo(f"Size:  {size_kb:.1f} KB")
    typer.echo(f"Users: {n_users}")
    typer.echo(f"Tasks: {n_tasks} ({n_done} done)")


@app.command()
def users():
    """List users with their task counts."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.nick, u.email, u.created_at,
                   COUNT(t.id) AS total,
                   COALESCE(SUM(t.done = 0), 0) AS pending
            FROM users u
            LEFT JOIN tasks t ON t.user_id = u.id
            GROUP BY u.id
            ORDER BY u.id
            """
        ).fetchall()
    if not rows:
        typer.echo("No users found.")
        return
    table = Table("ID", "Nick", "Email", "Created", "Tasks", "Pending")
    for r in rows:
        table.add_row(*(cell(r[k]) for k in ("id", "nick", "email", "created_at", "total", "pending")))
    console.print(table)


@app.command()
def tasks(
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Nick, email or id"),
    pending: bool = typer.Option(False, "--pending", help="Only tasks not done"),
):
    """List tasks, optionally for a single user."""
    with db() as conn:
        clauses, params = [], []
        if user:
            clauses.append("t.user_id = ?")
            params.append(find_user(conn, user)["id"])
        if pending:
            clauses.append("t.done = 0")
        sql = "SELECT t.*, u.nick FROM tasks t JOIN users u ON u.id = t.user_id"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY u.nick, t.done, t.priority DESC, t.id"
        rows = conn.execute(sql, params).fetchall()
    if not rows:
        typer.echo("No tasks found.")
        return
    table = Table("ID", "Owner", "Done", "Prio", "Name", "Deadline", "Description")
    for r in rows:
        table.add_row(
            cell(r["id"]), cell(r["nick"]), "yes" if r["done"] else "no",
            cell(r["priority"]), cell(r["name"]), cell(r["deadline"]), cell(r["description"]),
        )
    console.print(table)


@app.command("delete-user")
def delete_user(
    user: str = typer.Argument(..., help="Nick, email or id"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt"),
):
    """Delete a user and (by cascade) all of their tasks."""
    with db() as conn:
        u = find_user(conn, user)
        n = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (u["id"],)).fetchone()[0]
        if not yes and not typer.confirm(f"Delete '{u['nick']}' and their {n} tasks?"):
            raise typer.Exit()
        conn.execute("DELETE FROM users WHERE id = ?", (u["id"],))
    typer.echo(f"User '{u['nick']}' deleted ({n} tasks removed).")


@app.command("reset-password")
def reset_password(user: str = typer.Argument(..., help="Nick, email or id")):
    """Set a new password for a user (stored as an Argon2 hash)."""
    with db() as conn:
        u = find_user(conn, user)
        password = typer.prompt("New password", hide_input=True, confirmation_prompt=True)
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (_ph.hash(password), u["id"])
        )
    typer.echo(f"Password updated for '{u['nick']}'.")


@app.command()
def backup(
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Destination file"),
):
    """Make a consistent copy of the database (safe even while the server runs)."""
    if not database.DB_PATH.exists():
        fail(f"Database not found: {database.DB_PATH}")
    out = out or Path(f"anchor-backup-{datetime.now():%Y%m%d-%H%M%S}.db")
    if out.exists():
        fail(f"{out} already exists; refusing to overwrite it.")
    src = database.connect()
    dst = sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    typer.echo(f"Backup written to {out}")
    typer.echo("Note: it contains password hashes. Keep it out of Git.")


if __name__ == "__main__":
    app()