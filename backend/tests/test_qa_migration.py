"""Lecture migration preserves existing course discussion and replies."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_existing_course_discussion_survives_lecture_migration(tmp_path):
    path = tmp_path / 'legacy-qa.db'
    env = {**os.environ, 'HUSKYPOLL_DB': str(path)}

    def upgrade(revision):
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', revision],
                       cwd=ROOT, env=env, check=True, capture_output=True)

    upgrade('e6f7a8b9c0d1')
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO users (id, net_id, role, created_at) VALUES (1, 'abc12345', 'student', '2026-11-01 10:00:00')")
        db.execute("""INSERT INTO courses
            (id, term, subject, catalog, title, points_participation, points_correct, created_at)
            VALUES (1, 'Fall 2026', 'CSE', '2050', 'Test', 1, 0, '2026-11-01 10:00:00')""")
        db.execute("""INSERT INTO course_questions (id, course_id, author_id, body, created_at)
            VALUES (1, 1, 1, 'Keep my question', '2026-11-02 10:00:00')""")
        db.execute("""INSERT INTO course_replies (id, question_id, author_id, body, created_at)
            VALUES (1, 1, 1, 'Keep my reply', '2026-11-02 10:01:00')""")
    upgrade('head')
    with sqlite3.connect(path) as db:
        row = db.execute("""SELECT q.body, s.title, s.course_id FROM course_questions q
            JOIN lecture_sessions s ON s.id=q.session_id WHERE q.id=1""").fetchone()
        assert row == ('Keep my question', 'Earlier course Q&A', 1)
        assert db.execute('SELECT body FROM course_replies WHERE question_id=1').fetchone() == ('Keep my reply',)
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    # Applying the same migration again does not create extra legacy lectures.
    upgrade('head')
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM lecture_sessions').fetchone()[0] == 1
