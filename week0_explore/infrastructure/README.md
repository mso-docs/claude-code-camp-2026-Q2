# CircleMUD Docker Compose

This setup builds tbaMUD from the Git ref selected by `TBAMUD_REF` in the
Dockerfile (currently `master`) and runs it on port 4000. tbaMUD is a
CircleMUD derivative and includes DG Scripts and the quest engine used by
this repository's world data.

## Run

```sh
docker compose up --build
```

Connect with a MUD client, telnet, or netcat:

```sh
telnet localhost 4000
```

`docker-compose.yml` bind-mounts the repository's `lib` directory as the
container's game-data directory. Player files and mutable world state therefore
survive container recreation. `docker compose down -v` does not erase this bind
mount.

To erase player accounts while retaining the world files, run the repository's
reset helper from this directory:

```sh
./bin/reset
```

This is destructive: it deletes the files under `lib/plrfiles`, `lib/plrobjs`,
and `lib/plrvars`. The helper stops and restarts the CircleMUD service when it
was already running.
