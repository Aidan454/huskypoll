"""Command line: python -m huskypoll_db <command> [options]

  init                     create a new, empty database
  seed-demo                create a database filled with a demo course
  import-roster COURSE_ID FILE.xlsx [--drop-missing]
  export COURSE_ID OUT.csv [--per-session]
  archive-course COURSE_ID --as NETID        hide a course, keep its data (undo with --undo)
  delete-course COURSE_ID --as NETID [--delete-logs] [--yes]   permanently delete a course
  set-role NETID ROLE      make someone admin / instructor / ta / student / guest
  users [--role ROLE]      list accounts and their roles
  schema                   print the CREATE statements (for reading / docs)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

from .database import DEFAULT_DB_PATH, init_db, make_engine, make_session_factory
from .models import Course


def _stamp_alembic_head(db_path: str) -> None:
    """Record that a freshly created database is at the latest migration,
    so future `alembic upgrade head` runs apply only newer changes."""
    ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    if not ini.exists():
        return
    import os

    from alembic import command
    from alembic.config import Config

    os.environ["DB"] = str(Path(db_path).resolve())
    command.stamp(Config(str(ini)), "head")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m huskypoll_db")
    p.add_argument("--db", default=str(DEFAULT_DB_PATH), help="database file (default: %(default)s)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    s = sub.add_parser("seed-demo")
    s.add_argument("--students", type=int, default=40)
    s.add_argument("--roster", type=Path, help="also import this StudentAdmin .xlsx")
    r = sub.add_parser("import-roster")
    r.add_argument("course_id", type=int)
    r.add_argument("file", type=Path)
    r.add_argument("--drop-missing", action="store_true")
    e = sub.add_parser("export")
    e.add_argument("course_id", type=int)
    e.add_argument("out", type=Path)
    e.add_argument("--per-session", action="store_true")
    a = sub.add_parser("archive-course")
    a.add_argument("course_id", type=int)
    a.add_argument("--as", dest="as_netid", required=True, help="NetID of an instructor of the course")
    a.add_argument("--undo", action="store_true", help="restore an archived course")
    d = sub.add_parser("delete-course")
    d.add_argument("course_id", type=int)
    d.add_argument("--as", dest="as_netid", required=True, help="NetID of the course owner (or an admin)")
    d.add_argument("--delete-logs", action="store_true", help="also delete the course's event-log entries")
    d.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    sr = sub.add_parser("set-role")
    sr.add_argument("net_id")
    sr.add_argument("role", choices=["admin", "instructor", "ta", "student", "guest"])
    ul = sub.add_parser("users")
    ul.add_argument("--role", choices=["admin", "instructor", "ta", "student", "guest"])
    sub.add_parser("schema")
    args = p.parse_args(argv)

    if args.cmd == "schema":
        engine = make_engine(":memory:")
        init_db(engine)
        with engine.connect() as c:
            for (sql,) in c.execute(text(
                    "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL "
                    "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 WHEN 'trigger' THEN 2 ELSE 3 END, rowid")):
                print(sql.strip() + ";\n")
        return 0

    engine = make_engine(args.db)
    Session = make_session_factory(engine)

    if args.cmd in ("init", "seed-demo"):
        if Path(args.db).exists() and Path(args.db).stat().st_size > 0:
            print(f"{args.db} already exists; delete it first or use Alembic to upgrade it.", file=sys.stderr)
            return 1
        init_db(engine)
        _stamp_alembic_head(args.db)
        if args.cmd == "seed-demo":
            from .seed import seed_demo
            with Session.begin() as db:
                info = seed_demo(db, students=args.students, roster_xlsx=args.roster)
                print(f"Demo course {info['course'].code} (id {info['course'].id}): "
                      f"{info['students']} students, {info['polls']} polls")
        print(f"Created {args.db}")
        return 0

    if args.cmd in ("set-role", "users"):
        from . import services as svc
        from .models import User
        with Session.begin() as db:
            if args.cmd == "users":
                q = db.query(User).order_by(User.role, User.last_name, User.net_id)
                if args.role:
                    q = q.filter(User.role == args.role)
                for u in q:
                    print(f"{u.role:<11} {u.net_id or '-':<9} {u.email or '-':<36} {u.display_name}")
                return 0
            try:
                user, created = svc.find_or_create_user(db, net_id=args.net_id)
                svc.set_role(db, user, args.role)
            except svc.HuskyPollError as exc:
                print(exc, file=sys.stderr)
                return 1
            note = " (account created; it links up at their first login)" if created else ""
            print(f"{user.net_id} is now {args.role}{note}")
        return 0

    with Session.begin() as db:
        course = db.get(Course, args.course_id)
        if course is None:
            print(f"no course with id {args.course_id}", file=sys.stderr)
            return 1
        if args.cmd in ("archive-course", "delete-course"):
            from . import services as svc
            actor = svc.find_user(db, net_id=args.as_netid)
            if actor is None:
                print(f"no user with NetID {args.as_netid}", file=sys.stderr)
                return 1
            try:
                if args.cmd == "archive-course":
                    (svc.unarchive_course if args.undo else svc.archive_course)(db, course, actor)
                    print(f"{course.code} {'restored' if args.undo else 'archived'}")
                    return 0
                if not args.yes:
                    answer = input(f"Permanently delete {course.code} and all its polls and answers? "
                                   f"Type the course id ({course.id}) to confirm: ")
                    if answer.strip() != str(course.id):
                        print("Cancelled.")
                        return 1
                summary = svc.delete_course(db, course, actor, delete_logs=args.delete_logs)
            except svc.HuskyPollError as exc:
                print(exc, file=sys.stderr)
                return 1
            print(f"Deleted {summary['course_code']}: {summary['students']} enrollments, {summary['sessions']} sessions, "
                  f"{summary['polls']} polls, {summary['responses']} responses. Question banks were kept.")
            return 0
        if args.cmd == "import-roster":
            from .roster import import_studentadmin_xlsx
            res = import_studentadmin_xlsx(db, course, args.file, drop_missing=args.drop_missing)
            print(res.summary())
            for row, why in res.skipped:
                print(f"  row {row}: {why}")
        elif args.cmd == "export":
            from .export import per_session_csv, write_huskyct_csv
            if args.per_session:
                args.out.write_text(per_session_csv(db, course), encoding="utf-8")
                print(f"Wrote {args.out}")
            else:
                n = write_huskyct_csv(db, course, args.out)
                print(f"Wrote {n} students to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
