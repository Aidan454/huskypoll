"""Simulate a big lecture: N students answer one poll at the same moment.

    python scripts/simulate_lecture.py --students 500 --spread 20   # realistic: answers arrive over 20 s
    python scripts/simulate_lecture.py --students 500 --spread 0    # worst case: everyone at once
"""
import argparse
import random
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from huskypoll_db import init_db, make_engine, make_session_factory  # noqa: E402
from huskypoll_db import services as svc  # noqa: E402
from huskypoll_db.models import Poll, User  # noqa: E402
from huskypoll_db.roster import import_records  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--students", type=int, default=500)
ap.add_argument("--threads", type=int, default=50, help="concurrent request workers")
ap.add_argument("--spread", type=float, default=20.0, help="seconds over which answers arrive")
args = ap.parse_args()

path = Path(tempfile.mkdtemp()) / "load.db"
engine = make_engine(path)
init_db(engine)
Session = make_session_factory(engine)
with Session.begin() as db:
    prof, _ = svc.find_or_create_user(db, net_id="prof01")
    course = svc.create_course(db, prof, term="T", subject="CSE", catalog="1010", title="Load test")
    import_records(db, course, [{"net_id": f"s{i:05d}"} for i in range(args.students)])
    q = svc.create_question(db, prof, type="mc_single", body_md="?", options=[(c, c == "B") for c in "ABCD"])
    poll_id = svc.open_poll(db, course, q, prof).id
    option_ids = [o.id for o in q.options]
    student_ids = [u.id for u in db.query(User).filter(User.net_id.like("s%"))]

errors, latencies = [], []


T_START = time.perf_counter() + 0.5


def answer(arg):
    uid, delay = arg
    wait = T_START + delay - time.perf_counter()
    if wait > 0:
        time.sleep(wait)
    t0 = time.perf_counter()
    try:
        with Session.begin() as db:  # one request = one short transaction
            svc.submit_response(db, db.get(Poll, poll_id), db.get(User, uid), option_ids=[random.choice(option_ids)])
    except Exception as exc:  # noqa: BLE001
        errors.append(repr(exc))
    latencies.append(time.perf_counter() - t0)


t0 = T_START
with ThreadPoolExecutor(args.threads) as pool:
    list(pool.map(answer, sorted(((u, random.uniform(0, args.spread)) for u in student_ids), key=lambda a: a[1])))
wall = time.perf_counter() - t0
latencies.sort()
with Session() as db:
    n = len(db.get(Poll, poll_id).responses)
print(f"{n}/{args.students} responses stored, arriving over {args.spread:g}s (finished at {wall:.2f}s); "
      f"median {latencies[len(latencies)//2]*1000:.0f} ms, p99 {latencies[int(len(latencies)*.99)]*1000:.0f} ms, "
      f"errors: {len(errors)}")
if errors:
    print(errors[:3])
