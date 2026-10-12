# Local database container

This image packages the existing HuskyPoll database code. It does not start a
FastAPI server or provide browser URLs. Its default command prints database CLI
help and exits successfully without creating or modifying a database.

## Build

Docker must be installed and running. From the repository root:

```sh
docker build -t huskypoll-db:local Backend/DataBase_Code
```

The build downloads the Python 3.13 slim base image and installs the existing
`requirements.txt` dependencies. No new Python dependencies are added. The image
includes pytest because it is already in that dependency file and is needed to
test this preparation image. Dependency versions follow the existing ranges;
builds at different times can install different versions.

The build context is `Backend/DataBase_Code`, not the repository root.
`.dockerignore` excludes local environments, database files, CSV exports, and
environment files. The Dockerfile copies only the files needed by the database
package, migrations, tests, and demos.

## Check the command and run the existing tests

```sh
docker run --rm huskypoll-db:local
docker run --rm huskypoll-db:local python -m pytest -q -p no:cacheprovider
```

The first command should print the database CLI help. The second runs the existing
test suite, using temporary SQLite files inside the container. It does not mount
or access a host database. `--rm` removes the container after the command ends.

## Run the sample-data demonstration

```sh
docker run --rm huskypoll-db:local python scripts/demo_tour.py --no-pause
```

The demo creates a temporary sample database inside the container and walks through
courses, polls, responses, grading, exports, and access rules. Its archive/delete
examples operate only on that sample data. Nothing is written to the host project.

You can also test the existing seed command in a separate disposable container:

```sh
docker run --rm huskypoll-db:local python -m huskypoll_db seed-demo --roster samples/studentadmin-template.xlsx
```

`HUSKYPOLL_DB` defaults to `/tmp/huskypoll.db`, which the non-root container user
can write. This sample database disappears when the container is removed. These
commands do not configure persistent storage or connect to an external service.

## Integrate the future FastAPI application

Before turning this preparation image into the backend server image, confirm the
application's location, its dependency file, and its startup target with the
backend teammate. Then:

1. Add the actual application's files to the image's copy instructions, adjusting
   the build context if the application lives outside `DataBase_Code`.
2. Install the application's agreed dependencies, including its web server.
3. Replace the help command with the application's confirmed startup command.
   The server must listen on `0.0.0.0` inside the container for a published port
   to reach it. Do not assume a module name before the application exists.
4. Configure a writable persistent directory for SQLite, set `HUSKYPOLL_DB` to
   that directory's database path, and agree on initialization/migration steps.
   The container runs as UID 10001; the storage directory must allow that user to
   write. Avoid mounting an existing shared database during local testing.
5. Test startup, API routes, browser access, and database persistence against the
   official application. Passing the database suite alone does not verify an API.

Compose can be added once the official application's command, port, and storage
needs are known. No permanent FastAPI application or VM deployment is included
in this setup.

## Validation status

The following local Docker Desktop checks were completed successfully on the
project owner's Mac, as reported by the project owner:

| Check | Result |
| --- | --- |
| Build with `docker build -t huskypoll-db:local Backend/DataBase_Code` | Passed |
| Run the image's default database CLI help command | Passed |
| Run the existing database test suite inside Docker | 55 tests passed |
| Run `python scripts/demo_tour.py --no-pause` inside Docker | Completed successfully |

These results validate the database preparation image. FastAPI startup, API
routes, and persistent database storage remain future integration work. The
optional `seed-demo` command above was not included in the reported Docker checks.
